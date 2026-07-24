"""Minimal decoder for the A075 HTTP RGBD frame format."""

from __future__ import annotations

import struct
from dataclasses import dataclass


CONFIG_FORMAT = "<BBBBBBBBi"
CONFIG_SIZE = struct.calcsize(CONFIG_FORMAT)
HEADER_SIZE = 16


class FrameDecodeError(ValueError):
    """Raised when an A075 response is incomplete or inconsistent."""


@dataclass(frozen=True)
class A075Frame:
    frame_id: int
    timestamp_ms: int
    jpeg: bytes
    depth: bytes
    depth_width: int
    depth_height: int
    depth_bytes_per_pixel: int


def encode_config() -> bytes:
    """Request 8-bit depth/IR and JPEG RGB at 640x480."""
    return struct.pack(CONFIG_FORMAT, 1, 1, 255, 1, 2, 7, 1, 0, 0)


def decode_frame(data: bytes) -> A075Frame:
    """Extract the 320x240 depth map and JPEG image from `/getdeep`."""
    minimum = HEADER_SIZE + CONFIG_SIZE + 8
    if len(data) < minimum:
        raise FrameDecodeError(f"frame has {len(data)} bytes; need at least {minimum}")

    frame_id, timestamp_ms = struct.unpack_from("<QQ", data, 0)
    config = struct.unpack_from(CONFIG_FORMAT, data, HEADER_SIZE)
    if config[6] != 1:
        raise FrameDecodeError("camera did not return JPEG RGB data")

    sizes_offset = HEADER_SIZE + CONFIG_SIZE
    depth_size, rgb_size = struct.unpack_from("<ii", data, sizes_offset)
    if depth_size < 0 or rgb_size <= 0:
        raise FrameDecodeError("camera returned invalid payload sizes")

    depth_bytes_per_pixel = 2 if config[1] == 0 else 1
    depth_width = 320
    depth_height = 240
    depth_image_size = depth_width * depth_height * depth_bytes_per_pixel
    if depth_size < depth_image_size:
        raise FrameDecodeError(
            f"depth payload has {depth_size} bytes; need at least {depth_image_size}"
        )

    payload_start = sizes_offset + 8
    depth = data[payload_start : payload_start + depth_image_size]
    rgb_start = payload_start + depth_size
    rgb_end = rgb_start + rgb_size
    if rgb_end > len(data):
        raise FrameDecodeError(
            f"truncated RGB payload: ends at {rgb_end}, frame has {len(data)} bytes"
        )

    jpeg = data[rgb_start:rgb_end]
    if not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9"):
        raise FrameDecodeError("RGB payload is not a complete JPEG image")
    return A075Frame(
        frame_id=frame_id,
        timestamp_ms=timestamp_ms,
        jpeg=jpeg,
        depth=depth,
        depth_width=depth_width,
        depth_height=depth_height,
        depth_bytes_per_pixel=depth_bytes_per_pixel,
    )
