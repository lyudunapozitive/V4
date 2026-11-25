
"""Інкапсульовані CAN-кадри і класи тягової та гальмівної підсистем."""

from abc import ABC, abstractmethod
from typing import NamedTuple

from .errors import FrameIntegrityError, InvalidDTCCodeError

# Навчальне припущення: карта DTC не задана у білеті.
INVERTER_OVERHEAT = 0x01
ABS_CONTROLLER_FAULT = 0x02
CAN_COMMUNICATION_LOSS = 0x04
SUPPORTED_DTC_MASK = (
    INVERTER_OVERHEAT | ABS_CONTROLLER_FAULT | CAN_COMMUNICATION_LOSS
)


class RawCANFrame(NamedTuple):
    """Незмінне представлення розібраного CAN-повідомлення."""

    ecu_id: int
    dtc_status: int
    measurement: float
    timestamp_ms: int


class BaseTelemetryFrame(ABC):
    """Абстрактний фрейм із перевірюваними властивостями."""

    __slots__ = ("__ecu_id", "__dtc_status", "__measurement", "__timestamp_ms")
    value_min = float("-inf")
    value_max = float("inf")
    signal_unit = ""

    def __init__(self, raw: RawCANFrame) -> None:
        self.ecu_id = raw.ecu_id
        self.dtc_status = raw.dtc_status
        self.measurement = raw.measurement
        self.timestamp_ms = raw.timestamp_ms

    @property
    def ecu_id(self) -> int:
        return self.__ecu_id

    @ecu_id.setter
    def ecu_id(self, value: int) -> None:
        if type(value) is not int or not (0 <= value <= 0x1FFFFFFF):
            raise FrameIntegrityError("CAN ID повинен бути 11- або 29-бітним числом")
        self.__ecu_id = value

    @property
    def dtc_status(self) -> int:
        return self.__dtc_status

    @dtc_status.setter
    def dtc_status(self, value: int) -> None:
        if type(value) is not int or not 0 <= value <= 0xFF:
            raise InvalidDTCCodeError("DTC має бути 8-бітним регістром")
        if value & ~SUPPORTED_DTC_MASK:
            raise InvalidDTCCodeError(f"Невизначені біти DTC: 0x{value:02X}")
        self.__dtc_status = value

    @property
    def measurement(self) -> float:
        return self.__measurement

    @measurement.setter
    def measurement(self, value: float) -> None:
        from math import isfinite

        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise FrameIntegrityError("Показник повинен бути числом")
        if not isfinite(value) or not self.value_min <= value <= self.value_max:
            raise FrameIntegrityError(
                f"Показник {value} поза межами "
                f"[{self.value_min}; {self.value_max}] {self.signal_unit}"
            )
        self.__measurement = float(value)

    @property
    def timestamp_ms(self) -> int:
        return self.__timestamp_ms

    @timestamp_ms.setter
    def timestamp_ms(self, value: int) -> None:
        if type(value) is not int or value < 0:
            raise FrameIntegrityError("Таймстемп має бути невід'ємним цілим числом")
        self.__timestamp_ms = value

    @abstractmethod
    def process_signal(self) -> str:
        """Повернути інженерний опис стану підсистеми."""

    def snapshot(self) -> RawCANFrame:
        return RawCANFrame(
            self.ecu_id, self.dtc_status, self.measurement, self.timestamp_ms
        )

    def __str__(self) -> str:
        return (
            f"{self.process_signal()}: ECU=0x{self.ecu_id:03X}, "
            f"DTC=0x{self.dtc_status:02X}, "
            f"значення={self.measurement:.2f} {self.signal_unit}, "
            f"t={self.timestamp_ms} мс"
        )

    def __repr__(self) -> str:
        return f"{type(self).__name__}(raw={self.snapshot()!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseTelemetryFrame):
            return NotImplemented
        return type(self) is type(other) and self.snapshot() == other.snapshot()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, BaseTelemetryFrame):
            return NotImplemented
        return (self.timestamp_ms, self.ecu_id) < (
            other.timestamp_ms, other.ecu_id
        )


class TractionTelemetryFrame(BaseTelemetryFrame):
    """Телеметрія високовольтної батареї тягового контуру."""

    value_min = 200.0
    value_max = 850.0
    signal_unit = "В"

    def process_signal(self) -> str:
        return "Тяговий контур"


class BrakeTelemetryFrame(BaseTelemetryFrame):
    """Телеметрія тиску гідравлічної гальмівної системи."""

    value_min = 0.0
    value_max = 250.0
    signal_unit = "бар"

    def process_signal(self) -> str:
        return "Гальмівна система"
