
"""Потокове читання з попередньо скомпільованими регулярними виразами."""

import re
from collections.abc import Iterator
from pathlib import Path

from .errors import FrameIntegrityError, TelemetryFileError
from .frames import RawCANFrame

# Зафіксований формат: CAN_ID | DTC | Показник | Мілісекунди.
# Для 11-бітного ID — три hex-цифри, для 29-бітного — вісім.
CAN_PATTERN = re.compile(
    r"\s*(?P<ecu>0x(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{8}))\s*\|"
    r"\s*(?P<dtc>0x[0-9A-Fa-f]{1,4})\s*\|"
    r"\s*(?P<value>[+-]?[0-9]{1,4}(?:\.[0-9]{1,2})?)\s*\|"
    r"\s*(?P<timestamp>[0-9]{1,13})\s*",
    flags=re.ASCII,
)

NOISE_PATTERN = re.compile(r"\s*(?:#.*|NOISE:.*)?\s*", flags=re.ASCII)
MAX_LINE_LENGTH = 256


def parse_can_line(line: str) -> RawCANFrame:
    """Перетворити один текстовий кадр на незмінний кортеж."""
    if len(line) > MAX_LINE_LENGTH:
        raise FrameIntegrityError("Завелика довжина CAN-кадру")

    match = CAN_PATTERN.fullmatch(line)
    if match is None:
        raise FrameIntegrityError(
            "Невідповідність структурі CAN ID | DTC | VALUE | TIME"
        )

    ecu_id = int(match["ecu"], 16)
    if ecu_id > 0x1FFFFFFF:
        raise FrameIntegrityError("CAN ID перевищує максимальні 29 біт")

    return RawCANFrame(
        ecu_id=ecu_id,
        dtc_status=int(match["dtc"], 16),
        measurement=float(match["value"]),
        timestamp_ms=int(match["timestamp"]),
    )


def iter_can_records(
    path: Path,
) -> Iterator[tuple[int, RawCANFrame | FrameIntegrityError]]:
    """Читати кадри по одному, не завантажуючи файл цілком у пам'ять."""
    try:
        with path.open("r", encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                line = line.rstrip("\r\n")

                if NOISE_PATTERN.fullmatch(line):
                    continue

                try:
                    yield line_number, parse_can_line(line)
                except FrameIntegrityError as exc:
                    yield line_number, exc

    except OSError as exc:
        raise TelemetryFileError(
            f"Не вдалося прочитати '{path}': {exc}"
        ) from exc
