"""Publish camera observations to a robot over NetworkTables 4."""

from __future__ import annotations

import argparse
import logging
import selectors
import socket
import time
from pathlib import Path

import ntcore

from .control import ControlSettings, DriveIntent, plan_drive
from .targeting import DetectionFrame, TargetObservation, decode_detection_frame

LOG = logging.getLogger("a075-nt-publisher")
TABLE_ROOT = "GamePieceVision/v1"
CAMERA_TIMEOUT_SECONDS = 0.25
CAMERAS = ("left", "right")


class CameraPublishers:
    """Typed NetworkTables publishers for a single camera."""

    def __init__(
        self,
        instance: ntcore.NetworkTableInstance,
        camera: str,
        control_settings: ControlSettings,
    ):
        table = instance.getTable(TABLE_ROOT).getSubTable(camera)
        best = table.getSubTable("best")
        targets = table.getSubTable("targets")
        drive_request = table.getSubTable("driveRequest")
        self.control_settings = control_settings

        self.schema_version = table.getIntegerTopic("schemaVersion").publish()
        self.connected = table.getBooleanTopic("connected").publish()
        self.has_targets = table.getBooleanTopic("hasTargets").publish()
        self.target_count = table.getIntegerTopic("targetCount").publish()
        self.source_time = table.getDoubleTopic("sourceTimeSeconds").publish()

        self.best_center_x = best.getDoubleTopic("centerX").publish()
        self.best_center_y = best.getDoubleTopic("centerY").publish()
        self.best_width = best.getDoubleTopic("width").publish()
        self.best_height = best.getDoubleTopic("height").publish()
        self.best_area = best.getDoubleTopic("area").publish()
        self.best_depth = best.getDoubleTopic("depthRaw").publish()

        self.center_x = targets.getDoubleArrayTopic("centerX").publish()
        self.center_y = targets.getDoubleArrayTopic("centerY").publish()
        self.width = targets.getDoubleArrayTopic("width").publish()
        self.height = targets.getDoubleArrayTopic("height").publish()
        self.area = targets.getDoubleArrayTopic("area").publish()
        self.depth = targets.getDoubleArrayTopic("depthRaw").publish()

        self.drive_active = drive_request.getBooleanTopic("active").publish()
        self.drive_at_goal = drive_request.getBooleanTopic("atGoal").publish()
        self.drive_forward = drive_request.getDoubleTopic("forward").publish()
        self.drive_strafe = drive_request.getDoubleTopic("strafe").publish()
        self.drive_turn = drive_request.getDoubleTopic("turn").publish()
        self.drive_sequence = drive_request.getIntegerTopic(
            "frameSequence"
        ).publish()

        # Publish sequence last; consumers may use it as the frame commit marker.
        self.frame_sequence = table.getIntegerTopic("frameSequence").publish()

    def publish(self, frame: DetectionFrame) -> None:
        targets = frame.targets
        best = targets[0] if targets else TargetObservation(0, 0, 0, 0, 0, 0)

        self.schema_version.set(frame.schema_version)
        self.connected.set(frame.camera_connected)
        self.has_targets.set(frame.camera_connected and bool(targets))
        self.target_count.set(len(targets) if frame.camera_connected else 0)
        self.source_time.set(frame.source_time_seconds)

        self.best_center_x.set(best.center_x)
        self.best_center_y.set(best.center_y)
        self.best_width.set(best.width)
        self.best_height.set(best.height)
        self.best_area.set(best.area)
        self.best_depth.set(best.depth_raw)

        self.center_x.set([target.center_x for target in targets])
        self.center_y.set([target.center_y for target in targets])
        self.width.set([target.width for target in targets])
        self.height.set([target.height for target in targets])
        self.area.set([target.area for target in targets])
        self.depth.set([target.depth_raw for target in targets])
        self._publish_drive_intent(plan_drive(frame, self.control_settings))
        self.frame_sequence.set(frame.sequence)

    def publish_stale(self) -> None:
        self.connected.set(False)
        self.has_targets.set(False)
        self.target_count.set(0)
        self.best_center_x.set(0.0)
        self.best_center_y.set(0.0)
        self.best_width.set(0.0)
        self.best_height.set(0.0)
        self.best_area.set(0.0)
        self.best_depth.set(0.0)
        self.center_x.set([])
        self.center_y.set([])
        self.width.set([])
        self.height.set([])
        self.area.set([])
        self.depth.set([])
        self._publish_drive_intent(DriveIntent(False, False, 0, 0, 0, 0))

    def _publish_drive_intent(self, intent: DriveIntent) -> None:
        self.drive_at_goal.set(intent.at_goal)
        self.drive_forward.set(intent.forward)
        self.drive_strafe.set(intent.strafe)
        self.drive_turn.set(intent.turn)
        self.drive_sequence.set(intent.frame_sequence)
        # Publish active last so consumers never see active before its values.
        self.drive_active.set(intent.active)


def _open_socket(path: Path) -> socket.socket:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    receiver.bind(str(path))
    receiver.setblocking(False)
    return receiver


def run(args: argparse.Namespace) -> None:
    instance = ntcore.NetworkTableInstance.getDefault()
    instance.startClient4(args.identity)
    if args.server:
        instance.setServer(args.server)
        LOG.info("connecting to NetworkTables server %s", args.server)
    else:
        instance.setServerTeam(args.team)
        LOG.info("connecting to NetworkTables for team %d", args.team)

    selector = selectors.DefaultSelector()
    sockets: dict[socket.socket, tuple[str, Path]] = {}
    control_settings = ControlSettings(
        enabled=args.control_enabled,
        max_forward=args.max_forward,
        turn_kp=args.turn_kp,
        max_turn=args.max_turn,
        stop_area=args.stop_area,
        slowdown_area_range=args.slowdown_area_range,
        max_forward_center_x=args.max_forward_center_x,
        center_tolerance=args.center_tolerance,
        forward_sign=args.forward_sign,
        turn_sign=args.turn_sign,
    )
    publishers = {
        camera: CameraPublishers(instance, camera, control_settings)
        for camera in CAMERAS
    }
    last_received = {camera: float("-inf") for camera in CAMERAS}
    stale_published = {camera: False for camera in CAMERAS}

    for camera in CAMERAS:
        path = Path(args.socket_dir) / f"{camera}.sock"
        receiver = _open_socket(path)
        sockets[receiver] = (camera, path)
        selector.register(receiver, selectors.EVENT_READ)

    try:
        while True:
            for key, _ in selector.select(timeout=0.1):
                receiver = key.fileobj
                assert isinstance(receiver, socket.socket)
                payload = receiver.recv(65535)
                try:
                    frame = decode_detection_frame(payload)
                except (UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
                    LOG.warning("discarding invalid detection frame: %s", exc)
                    continue
                if frame.camera not in publishers:
                    LOG.warning("discarding frame for unknown camera %s", frame.camera)
                    continue
                publishers[frame.camera].publish(frame)
                last_received[frame.camera] = time.monotonic()
                stale_published[frame.camera] = False

            now = time.monotonic()
            for camera in CAMERAS:
                if (
                    now - last_received[camera] > CAMERA_TIMEOUT_SECONDS
                    and not stale_published[camera]
                ):
                    publishers[camera].publish_stale()
                    stale_published[camera] = True
            instance.flush()
    finally:
        for receiver, (_, path) in sockets.items():
            selector.unregister(receiver)
            receiver.close()
            path.unlink(missing_ok=True)
        selector.close()
        instance.stopClient()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", type=int, default=8324)
    parser.add_argument("--server", default="")
    parser.add_argument("--identity", default="frc8324-a075")
    parser.add_argument("--socket-dir", default="/run/frc8324-a075")
    parser.add_argument("--control-enabled", action="store_true")
    parser.add_argument("--max-forward", type=float, default=0.55)
    parser.add_argument("--turn-kp", type=float, default=1.4)
    parser.add_argument("--max-turn", type=float, default=0.65)
    parser.add_argument("--stop-area", type=float, default=0.08)
    parser.add_argument("--slowdown-area-range", type=float, default=0.05)
    parser.add_argument("--max-forward-center-x", type=float, default=0.6)
    parser.add_argument("--center-tolerance", type=float, default=0.03)
    parser.add_argument("--forward-sign", type=float, default=1.0)
    parser.add_argument("--turn-sign", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    run(parse_args())


if __name__ == "__main__":
    main()
