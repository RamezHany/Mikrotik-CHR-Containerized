# Mikrotik CHR Containerized

MikroTik RouterOS (CHR) running inside Docker via QEMU — a **plain vanilla**
image: the RouterOS binary is downloaded from MikroTik's official server at
build time and checksum-verified. Nothing is baked in — no users, no
branding. Branding and the default login are applied **after** deploy by
[`provision.py`](PROVISIONING.md).

Built for the Dokploy template (RouterOS as a one-click deploy), but works
with plain Docker anywhere.

## Build

```bash
docker build -t ghcr.io/ramezhany/mikrotik-chr-containerized:7.20.4 .
```

## Run

```bash
docker run -d --name mikrotik --privileged \
  --cap-add NET_ADMIN --device /dev/net/tun \
  -v mikrotik_data:/routeros/data \
  -p 8291:8291 -p 8728:8728 -p 808:80 -p 322:22 -p 1010:443 \
  ghcr.io/ramezhany/mikrotik-chr-containerized:7.20.4
```

| Host port | RouterOS port | Service |
| --- | --- | --- |
| 8291 | 8291 | WinBox |
| 8728 | 8728 | RouterOS API |
| 808 | 80 | WebFig (HTTP) |
| 322 | 22 | SSH |
| 1010 | 443 | SSTP (RouterOS keeps its default port 443 inside — the host port is 1010 because 443 usually belongs to the web stack) |

First login is `admin` with a blank password (pristine CHR) — set a password
immediately, or run the provisioning script below.

## Docker Compose

Prefer Compose? `docker compose up -d` in this repo does the same thing on any Docker host.
Once you have your `branding.dpk` (see below), apply branding + the default user with:

```bash
docker compose --profile provision run --rm provision
```

## Provisioning (branding + default user)

See [PROVISIONING.md](PROVISIONING.md). In short: after the container boots,
`provision.py` logs in via the RouterOS API, creates the branded admin user,
delivers the MikroTik Branding Maker package (`.dpk`) for the router to
install on reboot, verifies the new login, and disables the built-in `admin`
account last.

## Notes

- RouterOS state lives on the `/routeros/data` volume — restarts keep your
  configuration.
- CHR licensing is MikroTik's: the free CHR license limits each interface to
  1 Mbit/s; attach a paid/ trial license for full speed.
- This project is not affiliated with MikroTik. RouterOS and MikroTik are
  trademarks of SIA Mikrotīkls.
