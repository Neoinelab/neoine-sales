"""월말 Forecast 스냅숏 CLI: `python -m app.jobs.forecast_snapshot [--month YYYY-MM]`.

인자가 없으면 실행일의 전월, `--month`를 주면 그 월(전월·당월만)의 스냅숏을 만들거나 대체한다.
종료 코드: 성공(`--help` 포함) 0, 실행 중 실패 1, 허용되지 않는 인자 2.
인자는 설정·DB를 읽기 전에 해석하므로 인자 오류는 서버 설정 없이도 2로 끝난다.
"""

import argparse
import asyncio
import logging
import sys
from typing import TYPE_CHECKING, NoReturn, Protocol

from app.domain.common.errors import InvalidValueError
from app.domain.forecast.snapshot import YearMonth

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.forecast.take_snapshot import SnapshotResult

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

logger = logging.getLogger("app.jobs.forecast_snapshot")


class SnapshotUseCase(Protocol):
    async def execute(self, target: YearMonth | None = None) -> SnapshotResult: ...


class _UsageError(Exception):
    pass


class _HelpShown(Exception):  # noqa: N818
    """`--help`로 도움말(stdout)을 이미 출력했다."""


class _Parser(argparse.ArgumentParser):
    """잘못된 인자에서 종료하지 않고 예외로 알린다."""

    def error(self, message: str) -> NoReturn:
        raise _UsageError(message)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if status == 0:
            raise _HelpShown
        raise _UsageError(message or "")


def _target(argv: Sequence[str]) -> YearMonth | None:
    parser = _Parser(prog="forecast_snapshot", allow_abbrev=False, add_help=True)
    parser.add_argument("--month", metavar="YYYY-MM", help="기준 월(전월·당월만). 생략하면 전월")
    month = parser.parse_args(list(argv)).month
    return None if month is None else YearMonth.parse(month)


async def run(argv: Sequence[str], use_case: SnapshotUseCase) -> int:
    try:
        target = _target(argv)
    except _HelpShown:
        return EXIT_OK
    except (_UsageError, InvalidValueError) as error:
        print(f"인자 오류: {error}", file=sys.stderr)
        return EXIT_USAGE
    try:
        result = await use_case.execute(target)
    except InvalidValueError as error:  # 전월·당월이 아닌 기준 월
        print(f"인자 오류: {error}", file=sys.stderr)
        return EXIT_USAGE
    except Exception:
        logger.exception("Forecast 스냅숏 저장에 실패했습니다(이전 스냅숏은 그대로입니다).")
        return EXIT_FAILED
    logger.info(
        "Forecast 스냅숏 저장 완료: period=%s cell_count=%d replaced=%s taken_at=%s",
        result.period,
        result.cell_count,
        result.replaced,
        result.taken_at.isoformat(),
    )
    return EXIT_OK


async def _run_with_container(argv: Sequence[str]) -> int:
    # 설정·DB 의존은 인자를 확인한 뒤에만 불러온다.
    from app.config import get_settings  # noqa: PLC0415
    from app.container import Container  # noqa: PLC0415

    container = Container(get_settings())
    try:
        return await run(argv, container.take_forecast_snapshot())
    finally:
        await container.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(message)s")
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        _target(arguments)
    except _HelpShown:
        return EXIT_OK
    except (_UsageError, InvalidValueError) as error:
        print(f"인자 오류: {error}", file=sys.stderr)
        return EXIT_USAGE
    try:
        return asyncio.run(_run_with_container(arguments))
    except Exception:
        logger.exception("Forecast 스냅숏 작업을 시작하지 못했습니다(설정·DB 연결을 확인하세요).")
        return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
