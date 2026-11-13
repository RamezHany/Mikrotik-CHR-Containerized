#!/bin/bash
# SKELETON — Friday build material. Networking/QEMU details follow the proven
# CHR-in-Docker pattern (bridge + tap inside the container netns, guest gets
# the container-facing address, published compose ports DNAT/bridge to it).
# MUST be verified live on the VPS Friday: WinBox 8291, API 8728, SSH 22,
# SSTP 1010 reachability + persistence across container restart.
set -e

IMG="/routeros/chr-${ROUTEROS_VERSION}.vdi"
DISK="/routeros/data/chr.qcow2"

# First run: seed the persistent guest disk from the pristine CHR image.
if [ ! -f "$DISK" ]; then
  qemu-img convert -f vdi -O qcow2 "$IMG" "$DISK"
  qemu-img resize "$DISK" "${DISK_SIZE:-1G}"
fi

# --- Networking (to finalize Friday against the reference implementation) ---
# Container netns addressing plan (same shape as reference projects):
#   bridge br0 = 172.24.0.1/16, guest tap = 172.24.0.2
#   eth0 (container) joins br0; default route/NAT so guest reaches internet;
#   published ports arrive on eth0 and are forwarded to the guest.
# ip link add br0 type bridge
# ip addr add 172.24.0.1/16 dev br0
# ip link set br0 up
# ip tuntap add dev tap0 mode tap
# ip link set tap0 master br0
# ip link set tap0 up
# ip link set eth0 master br0
# ... NAT/forwarding rules as in reference projects ...

exec qemu-system-x86_64 \
  -m "${QEMU_RAM:-4096}" -smp "${QEMU_CPUS:-4}" \
  -drive file="$DISK",format=qcow2,if=virtio \
  -netdev tap,id=net0,ifname=tap0,script=no,downscript=no \
  -device virtio-net-pci,netdev=net0 \
  -nographic
