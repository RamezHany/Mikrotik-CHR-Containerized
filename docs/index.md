# MikroTik CHR Containerized

MikroTik RouterOS (Cloud Hosted Router / CHR) running inside Docker via QEMU.

This project delivers a **plain vanilla** RouterOS CHR environment:
- The RouterOS binary is downloaded directly from MikroTik's official distribution servers at build time.
- The download is verified against an immutable SHA-256 checksum before extraction.
- **Nothing is baked into the disk image** — no hardcoded credentials, no default accounts, and no pre-bundled branding.
- Custom branding and initial administrative credentials are applied cleanly **after deployment** using an automated API provisioning workflow.

---

## Choose Your Path

The project documentation is structured into two sequential paths depending on your goal:

1. **[Quickstart: Use Our Pre-built Image](quickstart.md)**  
   *The fast path.* Pull the official published image, run it with Docker Compose, and apply branding and administrative credentials in a single command. **Most readers stop here.**

2. **[Build Your Own from Scratch](build-your-own.md)**  
   *The complete explanation.* How and why every piece works so you can reproduce the entire container architecture from scratch: the Dockerfile, TAP/bridge networking, DHCP allocation, port mapping philosophy, API provisioning, branding packages with factory reset survival, and verified test checklists.

---

## Hardware Specifications & Defaults

The container allocates dedicated virtualized resources to the RouterOS QEMU guest. All resource boundaries are tunable at runtime via container environment variables:

| Resource | Default Allocation | Environment Variable | Notes |
| :--- | :--- | :--- | :--- |
| **CPU** | 4 vCPUs | `QEMU_CPUS` | Passed to QEMU via `-smp` |
| **Memory** | 4096 MB (4 GB) | `QEMU_RAM` | Passed to QEMU via `-m` |
| **Disk Size** | 1 GB | `DISK_SIZE` | Resized via `qemu-img resize` on first boot |
| **Storage Volume** | `/routeros/data` | N/A | Persistent volume holding `chr.vdi` |

---

## Port Mapping Reference

RouterOS network services keep their standard, default ports inside the container. Only host-facing ports are shifted to avoid collisions with host services or reverse proxies:

| Host Port | RouterOS Port | Protocol | Service | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`8291`** | `8291` | TCP | WinBox | MikroTik graphical desktop management client |
| **`8728`** | `8728` | TCP | RouterOS API | Plain API port used for management and automated provisioning |
| **`808`** | `80` | TCP | WebFig (HTTP) | Web management interface (moved to `808` on host to leave `80` free) |
| **`322`** | `22` | TCP | SSH | Secure shell management (moved to `322` on host to avoid host SSH conflicts) |
| **`1010`** | `443` | TCP | SSTP Passthrough | Direct passthrough to RouterOS port `443` (host uses `1010` so `443` remains available for Traefik, Caddy, or Nginx) |

> [!NOTE]
> This project does **not** pre-configure any VPN tunnels, certificates, or PPP profiles. RouterOS boots as a clean slate; port 1010 is mapped directly to RouterOS port 443 for optional SSTP passthrough if you decide to configure it inside RouterOS.

---

## Next Steps

- Proceed to the **[Quickstart Guide](quickstart.md)** to launch the container.
- Or explore the **[Architecture & Build Walkthrough](build-your-own.md)** to see how the container is constructed.
