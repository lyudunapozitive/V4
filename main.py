
"""
Екзаменаційний білет № 4.
Автоматизована діагностика CAN-шини автономного електротранспорту.
Головний модуль програми.
"""

import sys
import time
from pathlib import Path

from can_safety.errors import (
    DuplicateFrameError,
    FrameIntegrityError,
    InvalidDTCCodeError,
    TelemetryFileError,
)
from can_safety.parser import iter_can_records
from can_safety.diagnostics import (
    TelemetryAccumulator,
    create_frame,
    aggregate_measurements,
)


def run_pipeline(
    input_path: Path,
    report_path: Path,
    log_path: Path,
) -> TelemetryAccumulator:
    """Виконує потоковий аналіз CAN-повідомлень."""

    accumulator = TelemetryAccumulator()

    try:
        # Відкриття журналу за допомогою контекстного менеджера
        with log_path.open("w", encoding="utf-8") as log_file:

            # Обробка потоку кадрів через генератор
            for line_number, result in iter_can_records(input_path):

                if isinstance(result, FrameIntegrityError):
                    accumulator.invalid_frames += 1
                    log_file.write(
                        f"Рядок {line_number}: помилка кадру: {result}\n"
                    )
                    continue

                try:
                    frame = create_frame(result)
                    faults = accumulator.add_frame(frame)

                except DuplicateFrameError as error:
                    log_file.write(
                        f"Рядок {line_number}: дублікат: {error}\n"
                    )

                except (FrameIntegrityError, InvalidDTCCodeError) as error:
                    accumulator.invalid_frames += 1
                    log_file.write(
                        f"Рядок {line_number}: помилка: {error}\n"
                    )

                else:
                    print(f"[OK] {frame}")

                    for fault in faults:
                        message = (
                            f"Час {frame.timestamp_ms} мс | "
                            f"ECU 0x{frame.ecu_id:X} | {fault}"
                        )
                        print(f"[АВАРІЯ] {message}")
                        log_file.write(message + "\n")

        # Формування та збереження підсумкового звіту
        report = accumulator.report_text()

        with report_path.open("w", encoding="utf-8") as report_file:
            report_file.write(report + "\n")

    except OSError as error:
        raise TelemetryFileError(
            f"Помилка файлової системи: {error}"
        ) from error

    return accumulator


def main() -> None:
    """Головна точка входу програми."""

    print("=" * 75)
    print("ДІАГНОСТИКА CAN-ШИНИ АВТОНОМНОГО ЕЛЕКТРОТРАНСПОРТУ")
    print("БІЛЕТ № 4")
    print("=" * 75)

    input_path = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else Path("can_dump.txt")
    )

    report_path = Path("safety_report.txt")
    log_path = Path("incidents.log")

    start_time = time.perf_counter()

    try:
        accumulator = run_pipeline(
            input_path,
            report_path,
            log_path,
        )

    except TelemetryFileError as error:
        print(f"\n[ПОМИЛКА] {error}")

    else:
        print("\n" + accumulator.report_text())

        # Демонстрація передачі *args та **kwargs
        recent = tuple(accumulator.recent_frames)

        statistics = aggregate_measurements(
            "Тяговий контур",
            *recent,
            precision=2,
            minimum=0.0,
        )

        print(f"\nДодаткова статистика: {statistics}")
        print(f"Звіт збережено: {report_path}")
        print(f"Журнал інцидентів: {log_path}")

    finally:
        elapsed = time.perf_counter() - start_time
        print(f"\nЧас виконання: {elapsed * 1000:.3f} мс")


if __name__ == "__main__":
    main()
