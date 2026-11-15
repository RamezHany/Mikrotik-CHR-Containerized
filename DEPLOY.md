# Deploying MikroTik CHR Containerized

Four ways to run the same image — pick by where you are deploying.

## 1. Plain `docker run` (any host)

No compose needed. Pull the published image and run it:

```bash
docker pull ghcr.io/ramezhany/mikrotik-chr-containerized:7.20.4

docker run -d \
  --name mikrotik-chr \
  --privileged \
  --cap-add NET_ADMIN \
  --device /dev/net/tun \
  -e QEMU_RAM=4096 \
  -e QEMU_CPUS=4 \
  -e DISK_SIZE=1G \
  -v mikrotik_data:/routeros/data \
  -p 8291:8291 \
  -p 8728:8728 \
  -p 808:80 \
  -p 322:22 \
  -p 1010:443 \
  --restart unless-stopped \
  ghcr.io/ramezhany/mikrotik-chr-containerized:7.20.4
```

Then connect: WinBox on port `8291`, WebFig at `http://<host>:808`,
SSH on port `322`. First login is `admin` with a blank password —
RouterOS makes you set a password immediately.

## 2. Docker Compose (any host) — `docker-compose.yml`

The default compose pulls the same published image; there is nothing
to build:

```bash
git clone https://github.com/RamezHany/Mikrotik-CHR-Containerized.git
cd Mikrotik-CHR-Containerized
docker compose up -d
```

## 3. Dokploy — `docker-compose.dokploy.yml`

The exact compose submitted as the official Dokploy template
([Dokploy/templates PR #1330](https://github.com/Dokploy/templates/pull/1330)).
In Dokploy, create a Compose service and paste this file — or deploy
the template from the catalog once the PR is merged. RouterOS services
are raw TCP, so the ports are published on the host (the
`# dokploy: allow-host-ports` header); WinBox, SSH, the API and SSTP
connect directly to the host ports, Traefik is not in their path.

## 4. Development — `docker-compose.dev.yml`

Builds the image from the local `Dockerfile` instead of pulling it,
and carries the one-shot `provision` profile that applies a default
user and a branding package to a fresh guest:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

## Ports (all methods)

| Host port | RouterOS service |
|-----------|------------------|
| 8291 | WinBox |
| 8728 | RouterOS API |
| 808 | WebFig (HTTP) |
| 322 | SSH |
| 1010 | SSTP (443 inside the container) |

Router data persists in the `mikrotik_data` volume across restarts and
redeploys; it is lost only if you delete the volume. To upgrade
RouterOS itself, use **System → Packages** inside RouterOS — see
"Updating RouterOS" in the README.
