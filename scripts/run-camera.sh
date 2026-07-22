#!/usr/bin/env bash
set -euo pipefail

camera_name=${1:?camera name is required}
camera_config="/etc/frc8324-a075/${camera_name}.conf"
common_config=/etc/frc8324-a075/bridge.conf

source "$common_config"
source "$camera_config"
export PYTHONPATH=/opt/frc8324-a075/src

if [[ ! -e "$VIDEO_DEVICE" ]]; then
  echo "Missing virtual camera $VIDEO_DEVICE" >&2
  exit 1
fi

if ! ip netns list | awk '{print $1}' | grep -Fxq "$NAMESPACE"; then
  ip netns add "$NAMESPACE"
fi

if [[ -e "/sys/class/net/$INTERFACE" ]]; then
  ip link set "$INTERFACE" netns "$NAMESPACE"
fi

if ! ip netns exec "$NAMESPACE" ip link show dev "$INTERFACE" >/dev/null 2>&1; then
  echo "Interface $INTERFACE is not present in namespace $NAMESPACE" >&2
  exit 1
fi

ip netns exec "$NAMESPACE" ip address flush dev "$INTERFACE"
ip netns exec "$NAMESPACE" ip address add 192.168.233.2/24 dev "$INTERFACE"
ip netns exec "$NAMESPACE" ip link set lo up
ip netns exec "$NAMESPACE" ip link set "$INTERFACE" up

exec ip netns exec "$NAMESPACE" /usr/bin/python3 -m a075_bridge.main \
  --device "$VIDEO_DEVICE" --width "$WIDTH" --height "$HEIGHT" --fps "$FPS" \
  --hue-low "$HUE_LOW" --hue-high "$HUE_HIGH" \
  --saturation-low "$SATURATION_LOW" --value-low "$VALUE_LOW" \
  --min-area "$MIN_AREA" --min-circularity "$MIN_CIRCULARITY"
