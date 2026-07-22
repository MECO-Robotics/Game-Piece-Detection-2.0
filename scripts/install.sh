#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

# Return interfaces from namespaces created by a previous installation.
systemctl stop a075-bridge@left.service a075-bridge@right.service 2>/dev/null || true
ip netns delete a075-left 2>/dev/null || true
ip netns delete a075-right 2>/dev/null || true

usb_net_interfaces=()
for path in /sys/class/net/*; do
  iface=${path##*/}
  driver_path=$(readlink -f "$path/device/driver" 2>/dev/null || true)
  driver=${driver_path##*/}
  case "$driver" in
    rndis_host|cdc_ether|cdc_ncm) usb_net_interfaces+=("$iface") ;;
  esac
done

left_iface=${A075_LEFT_IFACE:-}
right_iface=${A075_RIGHT_IFACE:-}
if [[ -z "$left_iface" || -z "$right_iface" ]]; then
  if [[ ${#usb_net_interfaces[@]} -ne 2 ]]; then
    echo "Expected exactly two USB RNDIS/CDC network interfaces; found ${#usb_net_interfaces[@]}." >&2
    printf 'Candidates: %s\n' "${usb_net_interfaces[*]:-(none)}" >&2
    echo "Set A075_LEFT_IFACE and A075_RIGHT_IFACE and rerun." >&2
    exit 1
  fi
  left_iface=${left_iface:-${usb_net_interfaces[0]}}
  right_iface=${right_iface:-${usb_net_interfaces[1]}}
fi

if [[ "$left_iface" == "$right_iface" ]]; then
  echo "Left and right camera interfaces must be different." >&2
  exit 1
fi
for iface in "$left_iface" "$right_iface"; do
  if [[ ! -e "/sys/class/net/$iface" ]]; then
    echo "Network interface $iface does not exist." >&2
    exit 1
  fi
done

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-numpy python3-opencv ffmpeg v4l2loopback-dkms v4l-utils iproute2

install -d /opt/frc8324-a075 /etc/frc8324-a075
cp -a "$repo_dir/src" "$repo_dir/scripts" /opt/frc8324-a075/
chmod 0755 /opt/frc8324-a075/scripts/*.sh
cp "$repo_dir/config/bridge.conf" /etc/frc8324-a075/bridge.conf

cat > /etc/frc8324-a075/left.conf <<EOF
INTERFACE=$left_iface
NAMESPACE=a075-left
VIDEO_DEVICE=/dev/video20
EOF
cat > /etc/frc8324-a075/right.conf <<EOF
INTERFACE=$right_iface
NAMESPACE=a075-right
VIDEO_DEVICE=/dev/video21
EOF

cat > /etc/modprobe.d/frc8324-a075.conf <<'EOF'
options v4l2loopback devices=2 video_nr=20,21 card_label="FRC8324-A075-Left,FRC8324-A075-Right" exclusive_caps=1 max_buffers=4
EOF
echo v4l2loopback > /etc/modules-load.d/frc8324-a075.conf

if lsmod | grep -q '^v4l2loopback '; then
  modprobe -r v4l2loopback || {
    echo "v4l2loopback is busy. Stop applications using virtual cameras and rerun." >&2
    exit 1
  }
fi
modprobe v4l2loopback

install -m 0644 "$repo_dir/systemd/a075-bridge@.service" /etc/systemd/system/a075-bridge@.service
systemctl daemon-reload
systemctl enable --now a075-bridge@left.service a075-bridge@right.service

echo "Installed A075 bridges: left=$left_iface -> /dev/video20, right=$right_iface -> /dev/video21"
echo "Wait 15 seconds, restart PhotonVision, then activate both FRC8324-A075 cameras in its UI."
