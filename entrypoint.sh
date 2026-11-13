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

# Ensure /dev/net/tun exists
mkdir -p /dev/net
if [ ! -c /dev/net/tun ]; then
  mknod /dev/net/tun c 10 200 || true
fi

# Enable IPv4 forwarding
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true

# Setup internal bridge and TAP device
ip link add br0 type bridge
ip addr add 172.24.0.1/16 dev br0
ip link set br0 up

ip tuntap add dev tap0 mode tap
ip link set tap0 master br0
ip link set tap0 up

# Detect default interface (typically eth0)
ETH_IF=$(ip -o -4 route show to default | awk '{print $5}' | head -n1)
ETH_IF=${ETH_IF:-eth0}

# Outbound NAT (guest internet access via default interface)
iptables -t nat -A POSTROUTING -s 172.24.0.0/16 -o "$ETH_IF" -j MASQUERADE
iptables -A FORWARD -i br0 -o "$ETH_IF" -j ACCEPT
iptables -A FORWARD -i "$ETH_IF" -o br0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

# Inbound port forwarding from default interface to guest 172.24.0.2
iptables -t nat -A PREROUTING -i "$ETH_IF" -j DNAT --to-destination 172.24.0.2
iptables -A FORWARD -i "$ETH_IF" -o br0 -j ACCEPT

# Configure and start udhcpd on br0 to lease 172.24.0.2 to the guest
mkdir -p /var/lib/misc
touch /var/lib/misc/udhcpd.leases
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

exec qemu-system-x86_64 \
  -m "${QEMU_RAM:-4096}" -smp "${QEMU_CPUS:-4}" \
  -drive file="$DISK",format=qcow2,if=virtio \
  -netdev tap,id=net0,ifname=tap0,script=no,downscript=no \
  -device virtio-net-pci,netdev=net0 \
  -nographic
