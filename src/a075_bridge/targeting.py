"""Robot-independent game-piece observation messages."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

import cv2
import numpy as np

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TargetObservation:
    """One detected target in normalized image coordinates."""

    center_x: float
    center_y: float
    width: float
    height: float
    area: float
    depth_raw: float


@dataclass(frozen=True)
class DetectionFrame:
    """All observations produced by one camera frame."""

    schema_version: int
    camera: str
    camera_connected: bool
    sequence: int
    source_time_seconds: float
    targets: tuple[TargetObservation, ...]


def build_detection_frame(
    camera: str,
    sequence: int,
    boxes: list[tuple[int, int, int, int]],
    image_width: int,
    image_height: int,
    depth: np.ndarray | None,
    *,
    source_time_seconds: float | None = None,
) -> DetectionFrame:
    """Convert detector boxes into a resolution-independent observation frame."""
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")

    aligned_depth = None
    if depth is not None:
        aligned_depth = cv2.resize(
            depth, (image_width, image_height), interpolation=cv2.INTER_NEAREST
        )

    targets: list[TargetObservation] = []
    for x, y, width, height in boxes:
        center_x = (x + width / 2.0) / image_width * 2.0 - 1.0
        center_y = (y + height / 2.0) / image_height * 2.0 - 1.0
        depth_raw = _median_depth(aligned_depth, x, y, width, height)
        targets.append(
            TargetObservation(
                center_x=center_x,
                center_y=center_y,
                width=width / image_width,
                height=height / image_height,
                area=(width * height) / (image_width * image_height),
                depth_raw=depth_raw,
            )
        )

    return DetectionFrame(
        schema_version=SCHEMA_VERSION,
        camera=camera,
        camera_connected=True,
        sequence=sequence,
        source_time_seconds=(
            time.monotonic()
            if source_time_seconds is None
            else source_time_seconds
        ),
        targets=tuple(targets),
    )


def unavailable_frame(
    camera: str, sequence: int, *, source_time_seconds: float | None = None
) -> DetectionFrame:
    return DetectionFrame(
        schema_version=SCHEMA_VERSION,
        camera=camera,
        camera_connected=False,
        sequence=sequence,
        source_time_seconds=(
            time.monotonic()
            if source_time_seconds is None
            else source_time_seconds
        ),
        targets=(),
    )


def encode_detection_frame(frame: DetectionFrame) -> bytes:
    return json.dumps(asdict(frame), separators=(",", ":")).encode("utf-8")


def decode_detection_frame(payload: bytes) -> DetectionFrame:
    value = json.loads(payload.decode("utf-8"))
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema version {value.get('schema_version')}")
    return DetectionFrame(
        schema_version=value["schema_version"],
        camera=str(value["camera"]),
        camera_connected=bool(value["camera_connected"]),
        sequence=int(value["sequence"]),
        source_time_seconds=float(value["source_time_seconds"]),
        targets=tuple(TargetObservation(**target) for target in value["targets"]),
    )


def _median_depth(
    depth: np.ndarray | None, x: int, y: int, width: int, height: int
) -> float:
    if depth is None:
        return 0.0
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(depth.shape[1], x + width)
    y1 = min(depth.shape[0], y + height)
    if x0 >= x1 or y0 >= y1:
        return 0.0
    values = depth[y0:y1, x0:x1]
    valid = values[values > 0]
    return float(np.median(valid)) if valid.size else 0.0
