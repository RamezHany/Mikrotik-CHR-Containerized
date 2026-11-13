# MikroTik CHR Containerized

MikroTik RouterOS (Cloud Hosted Router / CHR) running inside Docker via QEMU.

This project delivers a **plain vanilla** RouterOS CHR environment:
- The RouterOS binary is downloaded directly from MikroTik's official distribution servers at image build time.
- The archive is verified against an immutable SHA-256 checksum before extraction.
- **Nothing is baked into the disk image** — no hardcoded credentials, no default accounts, and no pre-bundled branding.
- Custom branding and initial administrative credentials are applied cleanly **after deployment** using an automated API provisioning workflow.

---

## Choose Your Path

The project documentation is structured into two sequential paths depending on your goal:

1. **[Quickstart: Use Our Pre-built Image](quickstart.md)**  
   *The fast path.* Pull the published image from GitHub Container Registry or Docker Hub, run it with Docker Compose, and provision branding and credentials in a single command. **Most readers stop here.**

2. **[Build Your Own from Scratch](build-your-own.md)**  
   *The complete explanation.* How and why every piece works so you can reproduce the entire container architecture from scratch: the Dockerfile, TAP/bridge networking, DHCP allocation, port mapping philosophy, automated security provisioning, branding packages with factory reset survival, and verified test checklists.

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

RouterOS network services keep their standard, default ports inside the container. Only host-facing ports shift to avoid collisions with existing host services:

| Host Port | RouterOS Port | Protocol | Service | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`8291`** | `8291` | TCP | WinBox | MikroTik graphical desktop management client |
| **`8728`** | `8728` | TCP | RouterOS API | Plain API port used for management and automated provisioning |
| **`808`** | `80` | TCP | WebFig (HTTP) | Web management interface (host maps to `808` to keep host port `80` free) |
| **`322`** | `22` | TCP | SSH | Secure shell management (host maps to `322` to avoid host SSH collisions) |
| **`1010`** | `443` | TCP | SSTP Passthrough | Direct passthrough to RouterOS port `443` (host maps to `1010` to keep host `443` free for web proxies) |

---

## Port Philosophy Summary

### Why 443, 80, and 22 Move on the Host Side

RouterOS keeps its **default service ports inside the container** (SSH on 22, WebFig on 80, SSTP on 443). What changes is only the **host side** of the mapping.

On almost every Docker host or VPS, those standard ports are already occupied by host-level infrastructure:
- Port **22** belongs to the server's own SSH daemon.
- Ports **80** and **443** belong to the host's web stack or reverse proxy (Traefik, Nginx, Caddy).

Publishing the container on those same host ports would cause immediate binding collisions. Moving them (`22 → 322`, `80 → 808`, `443 → 1010`) avoids host conflicts and steps out of the most aggressive internet-wide port scans.

> [!NOTE]
> If your host is dedicated and is **not** using ports 22, 80, or 443, mapping them 1:1 works without issue. Moving them is about host coexistence, not internal RouterOS requirements.

### Why Ports 21 and 23 Are Disabled

Ports 21 (FTP) and 23 (Telnet) are not remapped — they are **disabled inside RouterOS** by [`defconfig.rsc`](https://github.com/RamezHany/mikrotik-chr-containerized/blob/main/defconfig.rsc). They are obsolete, unencrypted plaintext protocols that expose credentials over the wire.

Ports 8291 (WinBox) and 8728 (API) keep their standard numbers on both sides because host operating systems almost never run services on those numbers.

> [!IMPORTANT]
> **VPN Notice:** This project does **not** configure any VPN tunnels, certificates, or PPP profiles. RouterOS boots as a clean slate; port 1010 is mapped directly to RouterOS port 443 for optional SSTP passthrough if you decide to configure it inside RouterOS.

---

## Next Steps

- Proceed to the **[Quickstart Guide](quickstart.md)** to launch the container.
- Explore the **[Architecture & Build Walkthrough](build-your-own.md)** to see how the container is constructed.
