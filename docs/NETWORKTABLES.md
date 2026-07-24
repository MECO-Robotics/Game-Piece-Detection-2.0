# Robot integration over NetworkTables

The Beelink publishes observations and normalized chassis intent. It does not address motor controllers or bypass the
robot program. The roboRIO remains the only authority that may move the robot.

This makes the interface independent of drivetrain type and robot language. Java, C++, and Python robot programs can
read the same NetworkTables 4 topics, apply local safety gates, and map normalized intent to their own hardware.

## Connection

The publisher connects as an NT4 client. Its default team is 8324:

```text
NT_TEAM=8324
NT_SERVER=
```

These values live in `/etc/frc8324-a075/bridge.conf` after installation. Set `NT_TEAM` for a different team. Set
`NT_SERVER` to an explicit roboRIO hostname or IP address when team-based discovery is not appropriate. Leave
`NT_SERVER` empty to use `NT_TEAM`.

The service runs in the Beelink's normal network namespace. Camera capture remains in the isolated USB namespaces, and
local Unix datagrams carry observations from each camera process to the publisher.

## Topic contract

Topics are under `/GamePieceVision/v1/<camera>/`, where `<camera>` is `left` or `right`.

| Topic | NT type | Meaning |
| --- | --- | --- |
| `schemaVersion` | integer | Interface schema; currently `1`. |
| `connected` | boolean | A valid camera frame arrived recently. |
| `hasTargets` | boolean | The current frame has at least one target. |
| `targetCount` | integer | Number of targets in the current frame. |
| `frameSequence` | integer | Per-camera frame counter, published after the other frame values. |
| `sourceTimeSeconds` | double | Beelink monotonic time for diagnostics only. Do not compare it to roboRIO time. |
| `best/centerX` | double | Horizontal center of the largest target, from `-1` at left to `+1` at right. |
| `best/centerY` | double | Vertical center of the largest target, from `-1` at top to `+1` at bottom. |
| `best/width` | double | Bounding-box width as a fraction of image width. |
| `best/height` | double | Bounding-box height as a fraction of image height. |
| `best/area` | double | Bounding-box area as a fraction of total image area. |
| `best/depthRaw` | double | Median valid A075 depth value inside the target box; `0` means unavailable. |
| `targets/centerX` | double array | Horizontal centers for every target. |
| `targets/centerY` | double array | Vertical centers for every target. |
| `targets/width` | double array | Normalized widths for every target. |
| `targets/height` | double array | Normalized heights for every target. |
| `targets/area` | double array | Normalized areas for every target. |
| `targets/depthRaw` | double array | Median raw depth values for every target. |
| `driveRequest/active` | boolean | The planner has a fresh target and is requesting pursuit. Published after its values. |
| `driveRequest/atGoal` | boolean | The target has reached the configured stopping area. |
| `driveRequest/forward` | double | Normalized robot-relative forward request in `[-1, 1]`. |
| `driveRequest/strafe` | double | Normalized robot-relative left/right request in `[-1, 1]`; currently `0`. |
| `driveRequest/turn` | double | Normalized turn request in `[-1, 1]`. |
| `driveRequest/frameSequence` | integer | Camera frame used to calculate this request. |

All target arrays use the same ordering. Index 0 is the largest detected target and matches the `best/*` topics. The
depth value is not calibrated distance and must not be treated as meters.

The publisher clears target data and sets `connected=false` after 0.25 seconds without a camera message. Robot code
should still enforce its own freshness timeout using the NT value timestamp returned by `getAtomic()`.

## Pursuit planner

Planner settings live in `/etc/frc8324-a075/control.conf`:

| Setting | Default | Meaning |
| --- | --- | --- |
| `CONTROL_ENABLED` | `1` | Enables publishing active drive requests. Set to `0` to publish observations only. |
| `CONTROL_MAX_FORWARD` | `0.55` | Maximum normalized forward request. |
| `CONTROL_TURN_KP` | `1.4` | Turn request per unit of horizontal image error. |
| `CONTROL_MAX_TURN` | `0.65` | Maximum normalized turn request. |
| `CONTROL_STOP_AREA` | `0.08` | Stop forward motion when the target box reaches this image-area fraction. |
| `CONTROL_SLOWDOWN_AREA_RANGE` | `0.05` | Area range over which forward motion slows toward the stop. |
| `CONTROL_MAX_FORWARD_CENTER_X` | `0.60` | Turn without advancing when the target is farther off center. |
| `CONTROL_CENTER_TOLERANCE` | `0.03` | Horizontal error treated as centered. |
| `CONTROL_FORWARD_SIGN` | `1` | Set to `-1` for robots whose forward adapter direction is reversed. |
| `CONTROL_TURN_SIGN` | `1` | Set to `-1` when the robot turns away from the target. |

The current planner follows the largest detected target. It advances only when that target is sufficiently centered,
slows as apparent area approaches the stop value, and continues publishing an active zero-forward request at the goal.
These outputs are dimensionless so the robot chooses its own physical speed limits.

Store different settings for different robots as `config/robots/<robot-name>.conf`. Install a selected profile with
`sudo A075_CONTROL_PROFILE=<robot-name> ./scripts/install.sh`. Without that environment variable, reinstalling preserves
the active profile and pit tuning.

## Required robot-side safety behavior

Reusable Java consumer and command code is included under `robot-integration/`. The robot project still needs a small
hardware adapter appropriate for its drivetrain. It should follow these rules:

1. Movement is allowed only while the Driver Station reports enabled and the robot's own driver-held assist or
   autonomous state explicitly requests pursuit.
2. Require `connected=true`, `hasTargets=true`, the expected `schemaVersion`, and a fresh NT timestamp before using a
   target.
3. If any requirement becomes false, command zero pursuit output immediately and cancel the pursuit command.
4. Manual drive must require the drivetrain subsystem too, so the command scheduler can interrupt pursuit cleanly.
5. Bind a driver control to cancel pursuit. A hold-to-run/dead-man binding is preferred: releasing the control returns
   to the normal manual-drive command.
6. Driver Station disable and emergency stop remain authoritative; the Beelink must never bypass them.

The normalized observations intentionally contain no drivetrain assumptions. A swerve, tank, mecanum, or other robot
can consume the normalized drive request and apply its own units, limits, and hardware calls.

## Verification

On the Beelink:

```bash
systemctl status a075-nt-publisher --no-pager
journalctl -u a075-nt-publisher -n 50 --no-pager
```

In AdvantageScope, OutlineViewer, or Glass, look for `/GamePieceVision/v1/left`. Move a ball through the camera image
and verify that `frameSequence` increases, `hasTargets` changes, and `best/centerX` moves from negative to positive.

Before enabling movement, test the robot consumer with drive motors disabled or the robot securely on blocks:

- release the assist control;
- cover or unplug the camera;
- stop `a075-nt-publisher.service`;
- disconnect the Beelink from the robot network;
- disable the robot from Driver Station.

Every case must stop pursuit and leave manual control available when the robot is enabled again.
