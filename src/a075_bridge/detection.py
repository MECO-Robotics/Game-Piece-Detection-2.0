"""Fast HSV/circularity detector used to annotate the PhotonVision feed."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class DetectorSettings:
    hue_low: int = 20
    hue_high: int = 40
    saturation_low: int = 100
    value_low: int = 100
    min_area_px: float = 100.0
    min_circularity: float = 0.55


def find_fuel(frame: np.ndarray, settings: DetectorSettings) -> list[tuple[int, int, int, int]]:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower = np.array((settings.hue_low, settings.saturation_low, settings.value_low))
    upper = np.array((settings.hue_high, 255, 255))
    mask = cv2.inRange(hsv, lower, upper)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    boxes: list[tuple[int, int, int, int]] = []
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < settings.min_area_px:
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        circularity = 4.0 * np.pi * area / (perimeter * perimeter)
        x, y, width, height = cv2.boundingRect(contour)
        aspect = width / height if height else 0.0
        if circularity >= settings.min_circularity and 0.6 <= aspect <= 1.5:
            boxes.append((x, y, width, height))
    return sorted(boxes, key=lambda box: box[2] * box[3], reverse=True)


def annotate(frame: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    for index, (x, y, width, height) in enumerate(boxes, start=1):
        cv2.rectangle(frame, (x, y), (x + width, y + height), (255, 0, 255), 2)
        cv2.putText(
            frame,
            f"FUEL {index}",
            (x, max(18, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 0, 255),
            2,
            cv2.LINE_AA,
        )
    return frame
