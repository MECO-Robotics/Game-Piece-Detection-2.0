#!/usr/bin/env bash
set -euo pipefail

common_config=/etc/frc8324-a075/bridge.conf
control_config=/etc/frc8324-a075/control.conf
source "$common_config"
source "$control_config"
export PYTHONPATH=/opt/frc8324-a075/src

args=(--team "${NT_TEAM:-8324}" --socket-dir /run/frc8324-a075)
if [[ -n "${NT_SERVER:-}" ]]; then
  args+=(--server "$NT_SERVER")
fi
if [[ "${CONTROL_ENABLED:-0}" == 1 ]]; then
  args+=(--control-enabled)
fi
args+=(
  --max-forward "$CONTROL_MAX_FORWARD"
  --turn-kp "$CONTROL_TURN_KP"
  --max-turn "$CONTROL_MAX_TURN"
  --stop-area "$CONTROL_STOP_AREA"
  --slowdown-area-range "$CONTROL_SLOWDOWN_AREA_RANGE"
  --max-forward-center-x "$CONTROL_MAX_FORWARD_CENTER_X"
  --center-tolerance "$CONTROL_CENTER_TOLERANCE"
  --forward-sign "$CONTROL_FORWARD_SIGN"
  --turn-sign "$CONTROL_TURN_SIGN"
)

exec /opt/frc8324-a075/venv/bin/python -m a075_bridge.nt_publisher "${args[@]}"
