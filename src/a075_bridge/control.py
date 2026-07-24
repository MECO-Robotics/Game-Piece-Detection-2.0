"""Robot-agnostic game-piece pursuit planner."""

from __future__ import annotations

from dataclasses import dataclass

from .targeting import DetectionFrame


@dataclass(frozen=True)
class ControlSettings:
    """Dimensionless pursuit settings shared by all drivetrain types."""

    enabled: bool = True
    max_forward: float = 0.55
    turn_kp: float = 1.4
    max_turn: float = 0.65
    stop_area: float = 0.08
    slowdown_area_range: float = 0.05
    max_forward_center_x: float = 0.6
    center_tolerance: float = 0.03
    forward_sign: float = 1.0
    turn_sign: float = 1.0


@dataclass(frozen=True)
class DriveIntent:
    """Normalized chassis request; values are always in the range [-1, 1]."""

    active: bool
    at_goal: bool
    forward: float
    strafe: float
    turn: float
    frame_sequence: int


def plan_drive(frame: DetectionFrame, settings: ControlSettings) -> DriveIntent:
    """Plan a safe normalized pursuit request for the largest visible target."""
    inactive = DriveIntent(False, False, 0.0, 0.0, 0.0, frame.sequence)
    if not settings.enabled or not frame.camera_connected or not frame.targets:
        return inactive

    target = frame.targets[0]
    horizontal_error = target.center_x
    absolute_error = abs(horizontal_error)

    turn = 0.0
    if absolute_error > max(0.0, settings.center_tolerance):
        turn = _clamp(
            horizontal_error * settings.turn_kp * _sign(settings.turn_sign),
            -abs(settings.max_turn),
            abs(settings.max_turn),
        )

    at_goal = target.area >= max(0.0, settings.stop_area)
    forward = 0.0
    if not at_goal and absolute_error <= max(0.0, settings.max_forward_center_x):
        slowdown_range = max(0.001, settings.slowdown_area_range)
        speed_scale = _clamp(
            (settings.stop_area - target.area) / slowdown_range, 0.0, 1.0
        )
        forward = (
            _clamp(abs(settings.max_forward), 0.0, 1.0)
            * speed_scale
            * _sign(settings.forward_sign)
        )

    return DriveIntent(
        active=True,
        at_goal=at_goal,
        forward=forward,
        strafe=0.0,
        turn=turn,
        frame_sequence=frame.sequence,
    )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _sign(value: float) -> float:
    return -1.0 if value < 0 else 1.0
