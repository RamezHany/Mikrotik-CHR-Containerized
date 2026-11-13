# Quickstart: Use Our Image Directly

This guide covers **Path 1**: pulling the published image, running it via Docker Compose, performing your first login, and applying automated branding and credentials using the one-shot provisioning runner.

---

## 1. Pull the Image

The published image is hosted on the GitHub Container Registry (GHCR) and mirrored on Docker Hub.

### GitHub Container Registry (Primary)

```bash
docker pull ghcr.io/ramezhany/mikrotik-chr-containerized:7.20.4
```

### Docker Hub (Mirror)

```bash
docker pull <dockerhub-username>/mikrotik-chr-containerized:7.20.4
```

> [!NOTE]
> `<dockerhub-username>` is a placeholder. When pulling from Docker Hub, replace it with the repository owner's Docker Hub account name or organization once published.

---

## 2. Start the Container with Docker Compose

The repository includes a ready-to-run [`docker-compose.yml`](https://github.com/RamezHany/mikrotik-chr-containerized/blob/main/docker-compose.yml) configured with persistent storage, hardware sizing, and port bindings.

1. Clone or download the repository:
   ```bash
   git clone https://github.com/RamezHany/mikrotik-chr-containerized.git
   cd mikrotik-chr-containerized
   ```

2. Start the router service in the background:
   ```bash
   docker compose up -d
   ```

### What Happens on Startup

1. Docker mounts the persistent volume `mikrotik_data` to `/routeros/data`.
2. On first run, the container entrypoint creates `/routeros/data/chr.vdi` from the base image and expands it to 1 GB (or `$DISK_SIZE`).
3. An internal bridge `br0` (`172.24.0.1/16`) and TAP interface `tap0` are created.
4. An internal DHCP daemon (`udhcpd`) leases `172.24.0.2` to the RouterOS virtual interface.
5. Inbound traffic on exposed ports is redirected via `iptables` DNAT directly to `172.24.0.2`.
6. QEMU boots RouterOS CHR with 4 vCPUs and 4096 MB RAM.

---

## 3. First Login (Pristine CHR)

Because this is a **plain vanilla** image, it opens with MikroTik's factory default credentials:
- **Username:** `admin`
- **Password:** *(blank / empty — press Enter)*

You can connect immediately through any of the following interfaces:

- **WebFig (Browser):** Navigate to `http://<host-ip>:808`
- **WinBox:** Connect to `<host-ip>:8291` with user `admin` and an empty password.
- **SSH:** Run `ssh -p 322 admin@<host-ip>`

> [!WARNING]
> A pristine CHR instance allows unauthenticated administrative access from any network client that can reach the host ports. Do not leave the router in this state. Change the password immediately via WinBox/WebFig, or run the automated provisioning workflow below.

---

## 4. One-Shot Provisioning (Branding & User Setup)

The repository provides an automated, out-of-band provisioning profile in Docker Compose that configures the router via its API.

### Prerequisites

1. Ensure your `branding.dpk` package file is placed in the project root directory alongside `docker-compose.yml`. (See [Build Your Own — Branding](build-your-own.md#7-branding--the-default-configuration) to learn how to create this package with the MikroTik Branding Maker).
2. The router container must already be running (`docker compose up -d`).

### Run the Provisioning Profile

Execute the following command:

```bash
docker compose --profile provision run --rm provision
```

### What Provisioning Does

The provision runner executes [`provision.py`](https://github.com/RamezHany/mikrotik-chr-containerized/blob/main/provision.py) through a temporary container attached to the `mikrotik` service network:

1. **API Handshake:** Waits for the RouterOS API on port `8728` to become responsive, then logs in as `admin` with a blank password (confirming pristine vanilla state).
2. **Admin Creation:** Creates the branded administrator user (`ramez` with group `full` and password `ramez`, or customized credentials passed to the script).
3. **Login Verification:** Establishes a second, independent API connection using the new administrator credentials to ensure the account works before touching anything else.
4. **Package Delivery:** Starts an ephemeral HTTP server inside the provisioning container, instructs RouterOS via `/tool/fetch` to download `branding.dpk`, and verifies the exact file size on the router.
5. **Reboot & Installation:** Reboots the router (`/system/reboot`), allowing RouterOS to unpack and apply the `.dpk` package during system startup.
6. **Verification & Hardening:** Re-authenticates over the API as the new admin user, checks installed packages via `/system/package/print`, and **disables the built-in `admin` account LAST**. Disabling `admin` only after the new user is verified guarantees you will never be locked out.

---

## Summary of Management Ports

| Method | Host Connection | Default State | Post-Provisioning State |
| :--- | :--- | :--- | :--- |
| **WinBox** | `<host-ip>:8291` | `admin` (blank password) | Branded user credentials |
| **WebFig** | `http://<host-ip>:808` | `admin` (blank password) | Branded user credentials |
| **SSH** | `ssh -p 322 <user>@<host-ip>` | `admin` (blank password) | Branded user credentials |
| **API** | `<host-ip>:8728` | Plain API access | Plain API access |

---

## Next Steps

- Need to customize the base image, explore the bridge networking internals, or build your own branding package? Read the full **[Build Your Own Guide](build-your-own.md)**.
- Return to the **[Documentation Index](index.md)**.
