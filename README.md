# MikroTik CHR Containerized

MikroTik RouterOS (Cloud Hosted Router / CHR) running inside Docker via QEMU — a **plain vanilla** image built for reproducible deployments.

- **Vanilla by design:** The official RouterOS binary is downloaded directly from MikroTik at image build time and verified with a pinned SHA-256 checksum.
- **Nothing baked in:** The base disk contains no pre-configured users, passwords, or custom branding.
- **Post-boot provisioning:** Administrative users and branding packages (`.dpk`) are cleanly applied after boot via automated API provisioning.
- **Resource sizing:** Configured by default with 4 vCPUs, 4096 MB RAM, and a 1 GB disk — all tunable via environment variables (`QEMU_CPUS`, `QEMU_RAM`, `DISK_SIZE`).
- **Flexible hosting:** Built for the Dokploy template (RouterOS as a one-click deployment), but runs with Docker Compose or plain Docker on any host.

Full documentation is available in the [`docs/`](docs/) directory and served via GitHub Pages at:  
👉 **[https://ramezhany.github.io/mikrotik-chr-containerized/](https://ramezhany.github.io/mikrotik-chr-containerized/)**

---

## 1. Quickstart (Use Our Image)

The fastest path to running RouterOS CHR is pulling the published pre-built image. Most users start and stop here.

### Pull the Image

**GitHub Container Registry (Primary):**
```bash
docker pull ghcr.io/ramezhany/mikrotik-chr-containerized:7.20.4
```

**Docker Hub (Mirror):**
```bash
docker pull <dockerhub-username>/mikrotik-chr-containerized:7.20.4
```

*(Note for owner: Replace `<dockerhub-username>` with your Docker Hub account name).*

### Run with Docker Compose (Recommended)

1. Clone this repository:
   ```bash
   git clone https://github.com/RamezHany/mikrotik-chr-containerized.git
   cd mikrotik-chr-containerized
   ```

2. Start the router:
   ```bash
   docker compose up -d
   ```

*(Alternative: Run directly with `docker run`):*
```bash
docker run -d --name mikrotik --privileged \
  --cap-add NET_ADMIN --device /dev/net/tun \
  -v mikrotik_data:/routeros/data \
  -p 8291:8291 -p 8728:8728 -p 808:80 -p 322:22 -p 1010:443 \
  ghcr.io/ramezhany/mikrotik-chr-containerized:7.20.4
```

### First Login

A pristine CHR instance boots with factory default credentials:
- **Username:** `admin`
- **Password:** *(blank — press Enter)*

Connect immediately via:
- **WebFig (Browser):** `http://<host-ip>:808`
- **WinBox:** Connect to `<host-ip>:8291`
- **SSH:** `ssh -p 322 admin@<host-ip>`

Change the password immediately, or run the one-shot provisioning runner below.

### One-Shot Provisioning

Once your `branding.dpk` package is placed in the project root directory alongside `docker-compose.yml`, apply branding and create the dedicated administrator account with:

```bash
docker compose --profile provision run --rm provision
```

For detailed quickstart instructions, see **[docs/quickstart.md](docs/quickstart.md)**.

---

## 2. Build Your Own from Scratch

If you want to customize the image, inspect the internals, or build your own from source:

1. **The Vanilla Principle:** Pin the official RouterOS version and SHA-256 checksum (`7c1420075d27d1e72b132faf39805fc171e558b2ab8d54629bf4fc7bf7e44967` for `7.20.4`) and verify with `sha256sum -c` during image build.
2. **Build the Image:**
   ```bash
   docker build -t ghcr.io/ramezhany/mikrotik-chr-containerized:7.20.4 .
   ```
3. **Bridge/TAP Networking:** An internal bridge `br0` (`172.24.0.1/16`) and TAP interface `tap0` are created inside the container network namespace. A lightweight DHCP server (`udhcpd`) leases `172.24.0.2` to the RouterOS virtual NIC. Outbound NAT (`MASQUERADE`) provides internet access, and full inbound DNAT forwards exposed host traffic to `172.24.0.2`.
4. **Hardware Sizing:** Tunable via `QEMU_CPUS` (default 4), `QEMU_RAM` (default 4096), and `DISK_SIZE` (default 1G).

For the full step-by-step breakdown of the Dockerfile, entrypoint, and network plumbing, see **[docs/build-your-own.md](docs/build-your-own.md)**.

---

## 3. Provisioning & Branding

The image ships plain vanilla. Custom branding and initial administrative access are applied post-deploy by [`provision.py`](PROVISIONING.md):

1. **API Automation:** Logs in over the RouterOS API (`8728`) as `admin` (blank password).
2. **Account Creation:** Adds a full-access administrator (default `ramez` / `ramez`, group `full`) and verifies the new login on a second connection.
3. **Package Installation:** Serves `branding.dpk` via an ephemeral HTTP server, triggers `/tool/fetch` on the router, verifies file size, and issues `/system/reboot`.
4. **Hardening:** Disables the built-in `admin` account **LAST** after the new credentials and packages are confirmed.

### Factory Reset Survival (`defconfig.rsc`)

Branding packages created with MikroTik's Branding Maker (`mikrotik.com` → **Account** → **Other** → **Branding Maker**) can contain an ASCII console logo, system identity, and URLs.

> [!IMPORTANT]
> **Lesson learned:** If a `.dpk` is built without a default configuration script, running `/system reset-configuration` completely wipes custom users and returns the router to stock unauthenticated defaults.  
> By uploading [`defconfig.rsc`](defconfig.rsc) into the **"Default configuration"** field of the Branding Maker, the branded administrator, disabled default admin, and service hardening are embedded directly into the package. A factory reset automatically re-executes this configuration on reboot.

For details, see [PROVISIONING.md](PROVISIONING.md) and [docs/build-your-own.md](docs/build-your-own.md#7-branding--the-default-configuration).

---

## 4. Port Mapping Reference

RouterOS services keep their **default ports inside the container**; only host-side ports shift to avoid clashes with host daemons or web proxies:

| Host Port | RouterOS Port | Protocol | Service | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`8291`** | `8291` | TCP | WinBox | MikroTik desktop management client |
| **`8728`** | `8728` | TCP | RouterOS API | Plain API port used by `provision.py` |
| **`808`** | `80` | TCP | WebFig (HTTP) | Web management interface (host moves to `808` to free host port `80`) |
| **`322`** | `22` | TCP | SSH | Secure shell (host moves to `322` to avoid host SSH collision) |
| **`1010`** | `443` | TCP | SSTP Passthrough | Direct passthrough to RouterOS port `443` (host moves to `1010` to keep `443` open for reverse proxies) |

> [!NOTE]
> This project does **not** configure VPN services, PPP users, or certificates. Port 1010 is mapped directly to container port 443 solely as an available passthrough path if you choose to configure SSTP inside RouterOS.

---

## 5. Verification Summary

The implementation was built and validated on Windows using Docker Desktop (TCG software emulation):

- **Image Checksum Validation:** SHA-256 verified against official MikroTik release.
- **Hardware Specs Confirmed:** 4 vCPUs (`cpu-count: 4`), 4096 MB RAM (`total-memory: 4294967296`), 1 GB disk space (`total-hdd-space: 1027608576`).
- **All Ports Verified:** WebFig (808 HTTP 200), WinBox (8291 TCP), API (8728 TCP/Login), SSTP (1010 TCP), and SSH (322 TCP shell login).
- **Reset Survival:** `/system reset-configuration` confirmed to automatically restore the branded admin and service hardening from `defconfig.rsc`.
- **Restart Persistence:** `docker compose restart` confirmed volume `/routeros/data` persists disk state without reset.

See the complete test evidence in **[docs/build-your-own.md](docs/build-your-own.md#8-verification-checklist-windows-test-evidence)**.

---

## Notes & Licensing

- **Persistence:** RouterOS disk state is stored on the `mikrotik_data` volume (`/routeros/data/chr.vdi`). Container restarts preserve all configuration.
- **CHR Licensing:** Free CHR licenses are limited by MikroTik to 1 Mbit/s per interface. Attach a paid or trial 60-day license from your MikroTik account for full-speed operation.
- **Trademark Notice:** MikroTik and RouterOS are registered trademarks of SIA Mikrotīkls. This project is an independent community project and is not affiliated with or endorsed by SIA Mikrotīkls.
- **Project License:** Licensed under the [MIT License](LICENSE).
