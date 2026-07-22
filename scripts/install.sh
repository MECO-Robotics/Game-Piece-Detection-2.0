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
if [[ -z "$left_iface" && -z "$right_iface" ]]; then
  if [[ ${#usb_net_interfaces[@]} -lt 1 || ${#usb_net_interfaces[@]} -gt 2 ]]; then
    echo "Expected one or two USB RNDIS/CDC network interfaces; found ${#usb_net_interfaces[@]}." >&2
    printf 'Candidates: %s\n' "${usb_net_interfaces[*]:-(none)}" >&2
    echo "Set A075_LEFT_IFACE, optionally set A075_RIGHT_IFACE, and rerun." >&2
    exit 1
  fi
  left_iface=${usb_net_interfaces[0]}
  if [[ ${#usb_net_interfaces[@]} -eq 2 ]]; then
    right_iface=${usb_net_interfaces[1]}
  fi
elif [[ -z "$left_iface" ]]; then
  echo "A075_RIGHT_IFACE cannot be used without A075_LEFT_IFACE." >&2
  exit 1
fi

if [[ -n "$right_iface" && "$left_iface" == "$right_iface" ]]; then
  echo "Left and right camera interfaces must be different." >&2
  exit 1
fi
camera_interfaces=("$left_iface")
if [[ -n "$right_iface" ]]; then
  camera_interfaces+=("$right_iface")
fi
for iface in "${camera_interfaces[@]}"; do
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
if [[ -n "$right_iface" ]]; then
  cat > /etc/frc8324-a075/right.conf <<EOF
INTERFACE=$right_iface
NAMESPACE=a075-right
VIDEO_DEVICE=/dev/video21
EOF
else
  systemctl disable a075-bridge@right.service 2>/dev/null || true
  rm -f /etc/frc8324-a075/right.conf
fi

if [[ -n "$right_iface" ]]; then
  cat > /etc/modprobe.d/frc8324-a075.conf <<'EOF'
options v4l2loopback devices=2 video_nr=20,21 card_label="FRC8324-A075-Left,FRC8324-A075-Right" exclusive_caps=1 max_buffers=4
EOF
else
  cat > /etc/modprobe.d/frc8324-a075.conf <<'EOF'
options v4l2loopback devices=1 video_nr=20 card_label="FRC8324-A075-Left" exclusive_caps=1 max_buffers=4
EOF
fi
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
systemctl enable --now a075-bridge@left.service

if [[ -n "$right_iface" ]]; then
  systemctl enable --now a075-bridge@right.service
  echo "Installed A075 bridges: left=$left_iface -> /dev/video20, right=$right_iface -> /dev/video21"
  echo "Wait 15 seconds, restart PhotonVision, then activate both FRC8324-A075 cameras in its UI."
else
  echo "Installed A075 bridge: left=$left_iface -> /dev/video20"
  echo "Wait 15 seconds, restart PhotonVision, then activate FRC8324-A075-Left in its UI."
fi
