"""Continuously publish one A075 RGB stream to a V4L2 loopback device."""

from __future__ import annotations

import argparse
import logging
import subprocess
import time
import urllib.error
import urllib.request

import cv2
import numpy as np

from .detection import DetectorSettings, annotate, find_fuel
from .protocol import FrameDecodeError, decode_frame, encode_config


LOG = logging.getLogger("a075-bridge")


def request(url: str, data: bytes | None = None, timeout: float = 2.0) -> bytes:
    method = "POST" if data is not None else "GET"
    req = urllib.request.Request(url, data=data, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise OSError(f"A075 returned HTTP {response.status}")
        return response.read()


def ffmpeg_process(device: str, width: int, height: int, fps: int) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            "/usr/bin/ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-f",
            "rawvideo",
            "-pixel_format",
            "bgr24",
            "-video_size",
            f"{width}x{height}",
            "-framerate",
            str(fps),
            "-i",
            "pipe:0",
            "-vf",
            f"fps={fps}",
            "-pix_fmt",
            "yuyv422",
            "-f",
            "v4l2",
            device,
        ],
        stdin=subprocess.PIPE,
    )


def run(args: argparse.Namespace) -> None:
    base_url = f"http://{args.host}:{args.port}"
    settings = DetectorSettings(
        hue_low=args.hue_low,
        hue_high=args.hue_high,
        saturation_low=args.saturation_low,
        value_low=args.value_low,
        min_area_px=args.min_area,
        min_circularity=args.min_circularity,
    )
    output = ffmpeg_process(args.device, args.width, args.height, args.fps)
    assert output.stdin is not None

    configured = False
    consecutive_failures = 0
    last_log = time.monotonic()
    frames = 0
    while output.poll() is None:
        try:
            if not configured:
                request(f"{base_url}/set_cfg", encode_config())
                configured = True
                LOG.info("camera configured at %s", base_url)
            raw = request(f"{base_url}/getdeep")
            decoded = decode_frame(raw)
            image = cv2.imdecode(np.frombuffer(decoded.jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise FrameDecodeError("OpenCV could not decode the camera JPEG")
            image = cv2.resize(image, (args.width, args.height), interpolation=cv2.INTER_AREA)
            boxes = find_fuel(image, settings)
            output.stdin.write(annotate(image, boxes).tobytes())
            frames += 1
            consecutive_failures = 0

            now = time.monotonic()
            if now - last_log >= 5.0:
                LOG.info("streaming %.1f fps; %d FUEL candidate(s)", frames / (now - last_log), len(boxes))
                frames = 0
                last_log = now
        except (OSError, urllib.error.URLError, TimeoutError, FrameDecodeError) as exc:
            configured = False
            consecutive_failures += 1
            LOG.warning("camera unavailable: %s; retrying", exc)
            if consecutive_failures >= 10:
                raise RuntimeError("camera remained unavailable; restarting interface setup") from exc
            time.sleep(1.0)
        except BrokenPipeError:
            break

    raise RuntimeError(f"ffmpeg exited with status {output.returncode}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True)
    parser.add_argument("--host", default="192.168.233.1")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--hue-low", type=int, default=20)
    parser.add_argument("--hue-high", type=int, default=40)
    parser.add_argument("--saturation-low", type=int, default=100)
    parser.add_argument("--value-low", type=int, default=100)
    parser.add_argument("--min-area", type=float, default=100.0)
    parser.add_argument("--min-circularity", type=float, default=0.55)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(parse_args())


if __name__ == "__main__":
    main()
