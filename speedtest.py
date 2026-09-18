"""Замер скорости интернета: последовательно скачивает один и тот же файл N раз
и печатает среднее время запроса, объём скачанных данных и скорость в МБ/с.

Пример:
    python speedtest.py https://example.com/heavy.jpg
    python speedtest.py https://example.com/heavy.jpg --requests 20 --timeout 60
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

CHUNK_SIZE = 64 * 1024  # читаем потоком, чтобы не держать файл целиком в памяти
BYTES_IN_MB = 1024 * 1024
DEFAULT_REQUESTS = 10
DEFAULT_TIMEOUT = 30.0
USER_AGENT = "speedtest-script/1.0"


@dataclass(frozen=True)
class Attempt:
    """Результат одного скачивания."""

    seconds: float
    bytes_downloaded: int

    @property
    def mb_per_second(self) -> float:
        if self.seconds <= 0:
            return 0.0
        return self.bytes_downloaded / BYTES_IN_MB / self.seconds


def download_once(url: str, timeout: float) -> Attempt:
    """Скачивает URL целиком и возвращает время и объём.

    Время считаем монотонными часами: они не прыгают при переводе системного
    времени. Тело читаем до конца, иначе замер получится нечестным — часть
    данных ещё висела бы в буфере.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    downloaded = 0
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            downloaded += len(chunk)
    elapsed = time.perf_counter() - started
    return Attempt(seconds=elapsed, bytes_downloaded=downloaded)


def run(url: str, requests_count: int, timeout: float) -> list[Attempt]:
    attempts: list[Attempt] = []
    for number in range(1, requests_count + 1):
        try:
            attempt = download_once(url, timeout)
        except urllib.error.HTTPError as error:
            print(f"[{number}/{requests_count}] HTTP {error.code}: {error.reason}", file=sys.stderr)
            continue
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            print(f"[{number}/{requests_count}] ошибка сети: {error}", file=sys.stderr)
            continue

        attempts.append(attempt)
        print(
            f"[{number}/{requests_count}] {attempt.seconds:.3f} c, "
            f"{attempt.bytes_downloaded / BYTES_IN_MB:.2f} МБ, "
            f"{attempt.mb_per_second:.2f} МБ/с"
        )
    return attempts


def report(attempts: list[Attempt], requests_count: int) -> None:
    if not attempts:
        print("Ни один запрос не завершился успешно.", file=sys.stderr)
        raise SystemExit(1)

    total_bytes = sum(a.bytes_downloaded for a in attempts)
    total_seconds = sum(a.seconds for a in attempts)
    average_seconds = total_seconds / len(attempts)

    # Скорость считаем как общий объём делить на общее время, а не как среднее
    # арифметическое скоростей: иначе быстрые запросы весили бы столько же,
    # сколько медленные, и итог был бы завышен.
    average_speed = total_bytes / BYTES_IN_MB / total_seconds if total_seconds else 0.0

    print("\n--- Итог ---")
    print(f"Успешных запросов:     {len(attempts)} из {requests_count}")
    print(f"Среднее время запроса: {average_seconds:.3f} с")
    print(f"Скачано всего:         {total_bytes / BYTES_IN_MB:.2f} МБ ({total_bytes} байт)")
    print(f"Средняя скорость:      {average_speed:.2f} МБ/с")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Замеряет скорость скачивания: N последовательных запросов к одному URL."
    )
    parser.add_argument("url", help="адрес файла для скачивания (например, тяжёлая картинка)")
    parser.add_argument(
        "-n",
        "--requests",
        type=int,
        default=DEFAULT_REQUESTS,
        help=f"количество запросов (по умолчанию {DEFAULT_REQUESTS})",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"таймаут одного запроса в секундах (по умолчанию {DEFAULT_TIMEOUT})",
    )
    args = parser.parse_args()

    if args.requests < 1:
        parser.error("--requests должно быть не меньше 1")
    if args.timeout <= 0:
        parser.error("--timeout должно быть больше 0")
    return args


def main() -> None:
    args = parse_args()
    print(f"Замеряю скорость на {args.url} ({args.requests} запросов)\n")
    attempts = run(args.url, args.requests, args.timeout)
    report(attempts, args.requests)


if __name__ == "__main__":
    main()
