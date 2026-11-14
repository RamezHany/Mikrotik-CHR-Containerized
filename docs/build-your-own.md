# Build Your Own from Scratch

This guide covers **Path 2**: the architectural deep-dive and reproduction walkthrough for the MikroTik CHR Containerized project.

Every design choice, script, network setting, and verification step is documented here so you can reproduce or customize the entire setup from scratch.

---

## 1. The Vanilla Principle

The core principle of this project is strict software supply-chain integrity:
- The RouterOS disk image comes **only from MikroTik's official download servers** at image build time.
- The build process pins and verifies the official SHA-256 checksum before extracting the image.
- **Nothing is baked into the disk:** no modified filesystems, no pre-baked credentials, and no hardcoded configurations.

For version `7.20.4`, the pinned SHA-256 hash is:

```
7c1420075d27d1e72b132faf39805fc171e558b2ab8d54629bf4fc7bf7e44967
```

In the build workflow, the checksum is verified with `sha256sum -c` before the archive is unzipped:

```bash
printf '%s  /routeros/image.zip\n' "$ROUTEROS_SHA256" | sha256sum -c -
```

### Why Vanilla?

Pre-baking configuration into virtual disk images creates several critical failure modes:
1. **Supply-chain opacity:** Readers and auditors cannot easily inspect what has been altered inside a pre-built `.vdi` or `.qcow2` binary.
2. **Upgrade brittleness:** Minor RouterOS version upgrades can fail if disk structures or internal configuration databases conflict.
3. **Reset vulnerability:** A factory reset (`/system reset-configuration`) wipes disk modifications back to stock MikroTik defaults unless backed by an official branding package with an embedded default configuration script.

Keeping the base image vanilla and applying customizations via API automation after boot guarantees a pristine, repeatable foundation.

---

## 2. The Dockerfile, Section by Section

The container image is built from Alpine Linux (`alpine:3.24`) to minimize overhead and attack surface.

```dockerfile
FROM alpine:3.24

LABEL org.opencontainers.image.authors="Ramez Hany <ramzh06@gmail.com>"
LABEL org.opencontainers.image.source="https://github.com/RamezHany/mikrotik-chr-containerized"
LABEL org.opencontainers.image.description="MikroTik RouterOS CHR running inside Docker using QEMU"
```

### Build Arguments and Environment

```dockerfile
ARG ROUTEROS_VERSION=7.20.4
ARG ROUTEROS_SHA256=7c1420075d27d1e72b132faf39805fc171e558b2ab8d54629bf4fc7bf7e44967

ENV ROUTEROS_VERSION=$ROUTEROS_VERSION
ENV ROUTEROS_IMAGE=chr-$ROUTEROS_VERSION.vdi
ENV ROUTEROS_URL=https://download.mikrotik.com/routeros/$ROUTEROS_VERSION/chr-$ROUTEROS_VERSION.vdi.zip
```

### System Dependencies

```dockerfile
RUN apk add --no-cache \
    wget unzip \
    qemu-system-x86_64 qemu-img \
    iproute2 bridge-utils iptables \
    busybox-extras \
    bash
```

- `qemu-system-x86_64` & `qemu-img`: Virtualizes the x86_64 RouterOS CHR kernel and manages disk resizing.
- `iproute2`, `bridge-utils`, `iptables`: Provides Linux network plumbing (TAP devices, software bridge, NAT/DNAT).
- `busybox-extras`: Provides `udhcpd`, a lightweight DHCP server used to assign the guest router a static IP lease.
- `bash`, `wget`, `unzip`: Utility tooling for downloading and managing the runtime scripts.

### Fetching & Verifying the Disk Image

```dockerfile
RUN mkdir -p /routeros/data && \
    wget --timeout=60 --tries=3 "${ROUTEROS_URL}" -O /routeros/image.zip && \
    printf '%s  /routeros/image.zip\n' "$ROUTEROS_SHA256" | sha256sum -c - && \
    unzip /routeros/image.zip -d /routeros && \
    rm -f /routeros/image.zip
```

The download is saved to a temporary zip archive, verified against `$ROUTEROS_SHA256`, extracted into `/routeros/`, and cleaned up in a single layer.

### Entrypoint and Storage Setup

```dockerfile
WORKDIR /routeros
COPY entrypoint.sh /routeros/entrypoint.sh
RUN chmod +x /routeros/entrypoint.sh

VOLUME ["/routeros/data"]
ENTRYPOINT ["/routeros/entrypoint.sh"]
```

The persistent storage lives under `/routeros/data`.

---

## 3. Entrypoint Networking Architecture

QEMU user-mode (SLIRP) networking suffers from high latency and cannot easily provide bidirectional L2 packet processing. To give RouterOS a native virtual Ethernet interface, the container entrypoint builds an internal bridge and TAP network architecture.

```
+-------------------------------------------------------------------+
| Docker Container Network Namespace                                |
|                                                                   |
|   Host Traffic (eth0)                                             |
|        |                                                          |
|        v  [iptables PREROUTING DNAT to 172.24.0.2]                |
|   Linux Bridge (br0) --- 172.24.0.1/16                            |
|        |           |                                              |
|        |           +---> udhcpd (leases 172.24.0.2 to guest)      |
|        v                                                          |
|   TAP Device (tap0)                                               |
|        |                                                          |
|        v  [QEMU -net nic,model=virtio -net tap,ifname=tap0]       |
|   RouterOS Guest (ether1) --- 172.24.0.2                          |
|                                                                   |
|   Outbound Traffic:                                               |
|   172.24.0.2 -> br0 -> iptables MASQUERADE -> eth0 -> Internet    |
+-------------------------------------------------------------------+
```

### Why the Guest Needs its Own Address

RouterOS expects to manage a real network interface via DHCP. By assigning the bridge `br0` the IP `172.24.0.1/16` and having `udhcpd` lease `172.24.0.2` to the guest, both the host container and the guest router have known, deterministic IP addresses.

### Network Plumbing Steps in `entrypoint.sh`

1. **TUN Device Node Creation:**
   ```bash
   mkdir -p /dev/net
   if [ ! -c /dev/net/tun ]; then
     mknod /dev/net/tun c 10 200 || true
   fi
   ```

2. **IPv4 Forwarding:**
   ```bash
   sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
   ```

3. **Bridge and TAP Setup:**
   ```bash
   ip link add br0 type bridge
   ip addr add 172.24.0.1/16 dev br0
   ip link set br0 up

   ip tuntap add dev tap0 mode tap
   ip link set tap0 master br0
   ip link set tap0 up
   ```

4. **Outbound NAT (Internet Access):**
   ```bash
   ETH_IF=$(ip -o -4 route show to default | awk '{print $5}' | head -n1)
   ETH_IF=${ETH_IF:-eth0}

   iptables -t nat -A POSTROUTING -s 172.24.0.0/16 -o "$ETH_IF" -j MASQUERADE
   iptables -A FORWARD -i br0 -o "$ETH_IF" -j ACCEPT
   iptables -A FORWARD -i "$ETH_IF" -o br0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
   ```

5. **Inbound Port Forwarding (Full DNAT):**
   ```bash
   iptables -t nat -A PREROUTING -i "$ETH_IF" -j DNAT --to-destination 172.24.0.2
   iptables -A FORWARD -i "$ETH_IF" -o br0 -j ACCEPT
   ```
   Traffic arriving on container interface `eth0` from any published host port is automatically forwarded to guest IP `172.24.0.2`.

6. **DHCP Leasing via `udhcpd`:**
   ```bash
   cat <<EOF > /tmp/udhcpd.conf
   start 172.24.0.2
   end 172.24.0.2
   interface br0
   max_leases 1
   option subnet 255.255.0.0
   option router 172.24.0.1
   option dns 8.8.8.8 8.8.4.4
   lease_file /var/lib/misc/udhcpd.leases
   EOF

   udhcpd /tmp/udhcpd.conf
   ```

### Required Privileges

Because the container configures Linux bridges, TAP devices, and `iptables` routing tables, the following permissions are required:
- `cap_add: [NET_ADMIN]`
- `devices: [/dev/net/tun]`
- `privileged: true` (or appropriate capability sets in production Docker environments)

---

## 4. Sizing via Environment Variables

All virtual hardware parameters are controllable at container start through environment variables:

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `QEMU_RAM` | `4096` | Guest RAM in megabytes (passed to QEMU `-m`) |
| `QEMU_CPUS` | `4` | Virtual CPU cores (passed to QEMU `-smp`) |
| `DISK_SIZE` | `1G` | Disk capacity (expanded with `qemu-img resize`) |

### Persistent Disk Resizing

On first container startup, `entrypoint.sh` checks for `/routeros/data/chr.vdi`:

```bash
DISK=/routeros/data/chr.vdi
if [ ! -f "$DISK" ]; then
  cp "/routeros/${ROUTEROS_IMAGE}" "$DISK"
  qemu-img resize "$DISK" "${DISK_SIZE:-1G}"
fi
```

On subsequent starts, existing disk data is preserved without re-copying or re-sizing.

### QEMU Execution & Container Limits

QEMU is launched with serial console output redirected to `mon:stdio` for Docker log visibility:

```bash
exec qemu-system-x86_64 \
  -m "${QEMU_RAM:-4096}" -smp "${QEMU_CPUS:-4}" \
  -hda "$DISK" \
  -net nic,model=virtio,macaddr=52:54:00:12:34:56 \
  -net tap,ifname=tap0,script=no,downscript=no \
  -nographic -serial mon:stdio
```

When defining memory limits or CPU allocations in `docker-compose.yml`, ensure `mem_limit` and `cpus` are set equal to or greater than the QEMU requirements (at least 4 GB RAM and 4 CPUs) so the virtual machine does not experience memory exhaustion.

---

## 5. The Port Philosophy

A central design rule of this project is: **RouterOS services keep their default ports inside the container.**

- WinBox listens on port `8291`.
- RouterOS API listens on port `8728`.
- WebFig listens on port `80`.
- SSH listens on port `22`.
- SSTP listens on port `443`.

What changes is only the **host side** of the mapping:

| Host Port | Guest Port | Reason |
| :--- | :--- | :--- |
| `8291` | `8291` | Standard WinBox port; rarely conflicts on host servers. |
| `8728` | `8728` | Standard RouterOS API port; used by `provision.py`. |
| `808` | `80` | WebFig stays on port 80 inside; host port moves to 808 so the host's port 80 remains available for reverse proxies. |
| `322` | `22` | RouterOS SSH stays on port 22 inside; host port moves to 322 so it never clashes with the host machine's own SSH daemon. |
| `1010` | `443` | RouterOS SSTP server listens on standard port 443 inside; host port moves to 1010 because host port 443 belongs to Traefik, Caddy, or Nginx. |

### The Truth About Port Moving

Let us be completely transparent: if your Docker host is dedicated exclusively to RouterOS and is **not** running its own SSH on port 22 or Traefik/Nginx on ports 80 and 443, mapping them 1:1 works perfectly.

Moving the host ports is strictly about **avoiding collisions with the host server** (and stepping outside the most heavily automated port scans on the internet). The guest router requires no internal port changes.

### Why Ports 21 and 23 Are Disabled

Ports 21 (FTP) and 23 (Telnet) are a completely different case: they are **not remapped — they are explicitly disabled inside RouterOS**. They are insecure, plaintext legacy protocols that transmit administrative credentials unencrypted over the network.

> [!IMPORTANT]
> **Project Scope Notice:** This project does **not** configure or enable any VPN server, certificates, or PPP profiles. RouterOS boots with default service states. Port 1010 is mapped directly to container port 443 as an open passthrough path for operators who choose to configure SSTP inside RouterOS. Do not treat SSTP as a pre-configured service of this project.

---

## 6. Automated Provisioning (`provision.py`)

The provisioning script [`provision.py`](https://github.com/RamezHany/mikrotik-chr-containerized/blob/main/provision.py) is implemented using Python standard library modules only (`socket`, `hashlib`, `http.server`, `threading`, `argparse`). It does not require any third-party dependencies.

### How it Communicates

The script speaks the binary RouterOS API protocol on port `8728`:
- Words are framed with variable-length encoded byte prefixes (`enc_len`).
- Responses are received as sentence blocks ending with `!done`, `!re`, or `!trap`.
- Both modern plain authentication and legacy MD5 challenge/response authentication are handled automatically.

### Provisioning Steps in Detail

1. **Wait for API Readiness:**
   Polls `172.24.0.2:8728` with retries. Once responsive, authenticates as `admin` with a blank password. Successfully authenticating proves the image is pristine.
2. **Create Administrative User:**
   Executes `/user/add name=<user> group=full password=<password> comment="branding default admin"`.
3. **Verify New Credentials:**
   Opens a new, separate TCP connection and authenticates as the newly created user. If authentication fails, provisioning aborts immediately before modifying any other accounts.
4. **Serve and Fetch Branding Package:**
   Spins up an in-process HTTP server (`http.server.ThreadingHTTPServer`) on port `18080`. Triggers the router command:
   ```
   /tool/fetch url=http://172.24.0.1:18080/branding.dpk dst-path=branding.dpk
   ```
   Polls `/file/print` on RouterOS to confirm the file size on disk matches the local package byte count exactly.
5. **Reboot to Install Package:**
   Sends `/system/reboot`. RouterOS automatically inspects its root storage on boot, installs any `.dpk` packages, and reboots cleanly.
6. **Disable Default `admin` Account LAST:**
   After the router reboots and `provision.py` verifies the custom administrator login again, it queries `/user/print` and disables the built-in `admin` account:
   ```
   /user/set numbers=<admin-id> disabled=yes
   ```

### Why Disable Admin Last?

Disabling the default `admin` account only as the very last step guarantees that if user creation, network fetching, or package installation fails at any point, the router is never left in an unrecoverable lockout state.

---

## 7. Branding & The Default Configuration

Branding packages (`.dpk`) for RouterOS are generated using MikroTik's official web tool:

1. Log in to [mikrotik.com](https://mikrotik.com).
2. Go to **Account** → **Other** → **Branding Maker**.
3. Configure your visual branding:
   - **ASCII Logo:** Text logo (maximum 8 lines) displayed in SSH and serial console sessions.
   - **Identity:** System router identity name.
   - **Company URL:** Organization website displayed in management screens.
4. Download the generated `.dpk` file.

### The Hard-Learned Lesson: Reset Survival

If you generate a branding package containing only visual assets (logo and identity), the package contains **no default configuration**.

When an operator or automated system runs `/system reset-configuration`:
- The custom user database is wiped.
- The router reverts to factory defaults.
- The administrator user created during initial provisioning is destroyed, and the router reverts to unauthenticated `admin` / blank.

### The Solution: Embed `defconfig.rsc`

To ensure configuration survives a full system reset, upload [`defconfig.rsc`](https://github.com/RamezHany/mikrotik-chr-containerized/blob/main/defconfig.rsc) under the **"Default configuration"** field in the Branding Maker before generating the package.

Here is what [`defconfig.rsc`](https://github.com/RamezHany/mikrotik-chr-containerized/blob/main/defconfig.rsc) executes:

```routeros
/system identity set name=RouterOS

# The branded default admin
/user add name=ramez group=full password="ramez" comment="branding default admin"
/user set admin disabled=yes

# Service hardening for a fresh deployment
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www disabled=no
/ip service set ssh disabled=no
/ip service set api disabled=no
/ip service set api-ssl disabled=yes
```

### Why it Works

Per MikroTik specification, when a branding package includes a default configuration script:
- It executes automatically when the package is installed.
- **After any `/system reset-configuration`, RouterOS applies ONLY this embedded script**, replacing the stock MikroTik default script.

With `defconfig.rsc` embedded in `branding.dpk`, the provisioned administrator, disabled `admin` account, and hardened service profile are permanently preserved across factory resets.

---

## 8. Security: Why Credentials Change the Moment the Router Boots

Changing the default credentials immediately upon startup is not a matter of aesthetics or cosmetic cleanup — it is the **primary security requirement** of running RouterOS in cloud and container environments.

### The Threat Model: Automated Internet Scanners

The public IPv4 address space is continuously scanned by automated botnets seeking unauthenticated RouterOS instances. A fresh MikroTik router listening on its factory defaults (`admin` with an empty password) is typically indexed by scanning engines within minutes of exposure.

The automated playbook executed by these bots is well known:
1. Connect over port 8291 (WinBox), port 80 (WebFig), or port 8728 (API).
2. Authenticate as `admin` with a blank password.
3. Immediately change the administrative password or install rogue scripts.
4. **Lock the legitimate owner out of their own router.**
5. Enlist the appliance into a DDoS botnet, malware proxy pool, or DNS amplification network.

### The Defense: Disabling `admin` and Closing the Window

Our automated provisioning workflow neutralizes this threat:
- **Zero Public Defaults:** The provisioning script leaves exactly one door open: the operator's own administrative user, created with credentials defined in their own branding package and provisioning execution. Because each operator generates their own package with their own credentials, there is no shared or published default password that bots can brute-force.
- **Disabling Built-In Admin:** The stock `admin` user is fully disabled (`disabled=yes`). Even if an attacker attempts dictionary attacks against `admin`, RouterOS rejects the connection immediately.
- **Service Hardening in `defconfig.rsc`:**
  - `telnet` (port 23): **Disabled** (unencrypted plaintext).
  - `ftp` (port 21): **Disabled** (unencrypted plaintext).
  - `api-ssl`: **Disabled** unless explicitly configured with trusted certificates.
  - Only `www` (WebFig), `ssh`, and `api` remain enabled.

### Branding as Attribution

In this project, custom branding is **attribution, not mystery**:
- It signs the deployment with the identity of the operator who built and manages it (in our default image: identity/platform `RMZ`, the terminal ASCII logo, and `ramez-hany.com`).
- A branded router visibly signals that the node is under deliberate, active administrative control — not an unmonitored, neglected default appliance.

---

## 9. Verification Checklist (Windows Test Evidence)

The container architecture was built and validated on Windows using Docker Desktop (TCG software emulation without KVM). The following checklist documents the verified test results:

### 1. Build & Checksum Verification
- Image build command: `docker build -t ghcr.io/ramezhany/mikrotik-chr-containerized:7.20.4 .`
- Checksum validation verified: `/routeros/image.zip: OK`

### 2. Hardware Resource Verification
Verified directly from inside RouterOS via `/system/resource/print`:
- **vCPUs:** `cpu-count: 4`
- **Memory:** `total-memory: 4294967296` (4 GB)
- **Storage:** `total-hdd-space: 1027608576` (1 GB)

### 3. Port Reachability Verification
All published ports were tested for TCP reachability and application responses:
- **WebFig (Port 808 → 80):** HTTP 200 OK received; WebFig login page rendered.
- **WinBox (Port 8291 → 8291):** TCP connection established; WinBox management client connected.
- **RouterOS API (Port 8728 → 8728):** TCP open; API protocol sentences and authentication succeeded.
- **SSTP Passthrough (Port 1010 → 443):** TCP handshake succeeded; traffic forwarded to container port 443.
- **SSH (Port 322 → 22):** TCP connection open; MikroTik terminal banner displayed; authenticated command execution confirmed.

### 4. Factory Reset Survival Verification
- Triggered `/system reset-configuration` from within RouterOS.
- Router rebooted and automatically re-executed the embedded `defconfig.rsc`.
- Confirmed user `ramez` retained `full` group access.
- Confirmed account `admin` remained disabled (`disabled=yes`).
- Confirmed unencrypted management services (`telnet`, `ftp`) remained disabled.

### 5. Container Restart Persistence Verification
- Triggered `docker compose restart`.
- Verified that volume `mikrotik_data` mounted `/routeros/data/chr.vdi` intact.
- Confirmed all RouterOS configurations, logs, and account states persisted across container restarts.

---

## Navigation

- Back to **[Quickstart Guide](quickstart.md)**
- Return to **[Documentation Index](index.md)**
