
"""Ієрархія спеціалізованих винятків діагностичного конвеєра."""


class TelemetryError(Exception):
    """Базовий виняток прикладної телеметрії."""


class FrameIntegrityError(TelemetryError):
    """Рядок не відповідає формату або правилам цілісності кадру."""


class DuplicateFrameError(FrameIntegrityError):
    """Повторення CAN-ідентифікатора з тим самим часовим штампом."""


class InvalidDTCCodeError(TelemetryError):
    """Діагностичний регістр містить невизначені біти."""


class TelemetryFileError(TelemetryError):
    """Помилка читання або запису файлів телеметрії."""
