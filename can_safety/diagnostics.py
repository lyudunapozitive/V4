
"""Побітова діагностика, пошук колізій та інкрементальна агрегація."""

from collections import Counter, deque
from dataclasses import dataclass, field

from .errors import DuplicateFrameError, FrameIntegrityError
from .frames import (
    ABS_CONTROLLER_FAULT,
    CAN_COMMUNICATION_LOSS,
    INVERTER_OVERHEAT,
    BaseTelemetryFrame,
    BrakeTelemetryFrame,
    RawCANFrame,
    TractionTelemetryFrame,
)

# Навчальний мапінг ECU ID, оскільки фізичну CAN-матрицю в білеті не наведено.
ECU_CLASSES = {0x101: TractionTelemetryFrame, 0x201: BrakeTelemetryFrame}

DTC_EVENTS = {
    INVERTER_OVERHEAT: "Перегрів тягового інвертора",
    ABS_CONTROLLER_FAULT: "Збій контролера ABS",
    CAN_COMMUNICATION_LOSS: "Втрата зв'язку CAN",
}


def create_frame(raw: RawCANFrame) -> BaseTelemetryFrame:
    frame_type = ECU_CLASSES.get(raw.ecu_id)
    if frame_type is None:
        raise FrameIntegrityError(f"Невідомий ECU ID: 0x{raw.ecu_id:X}")
    return frame_type(raw)


def detect_faults(frame: BaseTelemetryFrame) -> list[str]:
    """Побітова перевірка DTC."""
    return [
        event
        for mask, event in DTC_EVENTS.items()
        if frame.dtc_status & mask
    ]


def aggregate_measurements(
    subsystem: str,
    /,
    *frames: BaseTelemetryFrame,
    precision: int = 2,
    **options: float,
) -> dict[str, int | float | str]:
    """Агрегація показників із використанням *args та **kwargs."""
    minimum = float(options.get("minimum", float("-inf")))
    values = [
        frame.measurement
        for frame in frames
        if frame.process_signal() == subsystem
        and frame.measurement >= minimum
    ]

    if not values:
        return {
            "підсистема": subsystem,
            "кількість": 0,
            "середнє": 0.0,
        }

    return {
        "підсистема": subsystem,
        "кількість": len(values),
        "середнє": round(sum(values) / len(values), precision),
    }


@dataclass
class TelemetryAccumulator:
    """Лічильники та історія для потокового звіту."""

    valid_frames: int = 0
    invalid_frames: int = 0
    duplicate_frames: int = 0

    incidents: Counter[str] = field(default_factory=Counter)
    counts: Counter[str] = field(default_factory=Counter)
    totals: dict[str, float] = field(default_factory=dict)

    seen_keys: set[tuple[int, int]] = field(default_factory=set)

    recent_frames: deque[BaseTelemetryFrame] = field(
        default_factory=lambda: deque(maxlen=10)
    )

    def add_frame(self, frame: BaseTelemetryFrame) -> list[str]:
        # Виявлення повторного CAN ID з однаковим часом.
        key = (frame.ecu_id, frame.timestamp_ms)

        if key in self.seen_keys:
            self.duplicate_frames += 1
            raise DuplicateFrameError(
                f"Повтор ECU=0x{frame.ecu_id:X} у t={frame.timestamp_ms} мс"
            )

        self.seen_keys.add(key)
        self.valid_frames += 1

        subsystem = frame.process_signal()
        self.counts[subsystem] += 1

        self.totals[subsystem] = (
            self.totals.get(subsystem, 0.0) + frame.measurement
        )

        self.recent_frames.append(frame)

        faults = detect_faults(frame)
        self.incidents.update(faults)

        return faults

    def report_text(self) -> str:
        """Формування підсумкового текстового звіту."""
        means = {
            key: self.totals[key] / count
            for key, count in self.counts.items()
            if count
        }

        lines = [
            "ЗВІТ БЕЗПЕКИ БОРТОВОЇ CAN-ШИНИ — ВАРІАНТ 4",
            "=" * 66,
            f"Валідних унікальних кадрів: {self.valid_frames}",
            f"Некоректних кадрів:       {self.invalid_frames}",
            f"Колізій ID + timestamp:    {self.duplicate_frames}",
            f"Зафіксованих аварій:      {sum(self.incidents.values())}",
            "-" * 66,
            "СЕРЕДНІ ЗНАЧЕННЯ:",
        ]

        lines.extend(
            f"  {subsystem}: {value:.2f} "
            f"{'В' if subsystem == 'Тяговий контур' else 'бар'} "
            f"({self.counts[subsystem]} кадрів)"
            for subsystem, value in means.items()
        )

        lines.append("ДІАГНОСТИЧНІ ІНЦИДЕНТИ:")

        if self.incidents:
            lines.extend(
                f"  {label}: {count}"
                for label, count in self.incidents.items()
            )
        else:
            lines.append("  Не виявлено")

        lines.extend([
            "-" * 66,
            "ОСТАННІ КАДРИ В ХРОНОЛОГІЧНОМУ ПОРЯДКУ:",
        ])

        lines.extend(
            f"  {frame}"
            for frame in sorted(self.recent_frames)
        )

        lines.append("=" * 66)
        return "\n".join(lines)
