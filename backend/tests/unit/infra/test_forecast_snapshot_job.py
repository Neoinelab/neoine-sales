"""월말 스냅숏 CLI `python -m app.jobs.forecast_snapshot`(P6 R2 AC-13~15): 종료 코드와 인자 규칙.

종료 코드: 성공 0, 실행 중 실패 1, 허용되지 않는 인자(형식 오류·알 수 없는 인자·
전월/당월이 아닌 월) 2.
`run(argv, use_case)`는 인자 해석과 종료 코드 결정을 하는 비동기 진입점이고(Fake UoW 위의
실제 유스케이스로 검증), `main()`은 설정·Container 조립 뒤 `run`을 부르는 동기 진입점이다.
인자 오류는 설정을 읽기 전에 거절해야 하므로, 설정이 전혀 없는 환경의 하위 프로세스로도
확인한다.
"""

import os
import subprocess
import sys
from typing import TYPE_CHECKING, Any, cast

import pytest

from app.application.forecast.take_snapshot import TakeForecastSnapshot
from app.domain.forecast.snapshot import YearMonth
from app.jobs.forecast_snapshot import run
from tests.fakes.catalog_seed import seed_catalog
from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
from tests.unit.application.forecast_snapshot_env import local

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

RUN_AT = local(2026, 10, 1, 0, 5)


def _setup(now: datetime = RUN_AT) -> tuple[FakeUnitOfWork, TakeForecastSnapshot]:
    uow = FakeUnitOfWork()
    seed_catalog(uow)
    return uow, TakeForecastSnapshot(cast("Any", lambda: uow), FixedClock(now))


async def _periods(uow: FakeUnitOfWork) -> list[YearMonth]:
    return [info.period for info in await uow.forecast_snapshots.list_periods()]


class _FailingUseCase:
    """실행 중 예외(예: DB 오류)를 내는 유스케이스 대역."""

    async def execute(self, target: YearMonth | None = None) -> object:
        msg = "database is down (test double)"
        raise RuntimeError(msg)


async def test_no_arguments_takes_the_previous_month_and_exits_zero() -> None:
    uow, use_case = _setup()

    code = await run([], use_case)

    assert code == 0
    assert await _periods(uow) == [YearMonth(2026, 9)]


@pytest.mark.parametrize("month", ["2026-09", "2026-10"])
async def test_previous_and_current_month_are_accepted_and_exit_zero(month: str) -> None:
    uow, use_case = _setup()

    code = await run(["--month", month], use_case)

    assert code == 0
    assert await _periods(uow) == [YearMonth.parse(month)]


async def test_rerunning_the_same_month_exits_zero_and_keeps_one_snapshot() -> None:
    uow, use_case = _setup()

    first = await run([], use_case)
    second = await run(["--month", "2026-09"], use_case)

    assert (first, second) == (0, 0)
    assert await _periods(uow) == [YearMonth(2026, 9)]


async def test_cli_exit_code_2_for_disallowed_month(capsys: pytest.CaptureFixture[str]) -> None:
    uow, use_case = _setup()

    code = await run(["--month", "2026-08"], use_case)

    assert code == 2
    assert "다시 계산할 수 없습니다" in capsys.readouterr().err
    assert await _periods(uow) == []


async def test_a_future_month_exits_two_and_writes_nothing() -> None:
    uow, use_case = _setup()

    code = await run(["--month", "2026-11"], use_case)

    assert code == 2
    assert await _periods(uow) == []


@pytest.mark.parametrize(
    "month", ["2026-9", "2026/09", "202609", "abc", "", "2026-13", "2026-09-01"]
)
async def test_cli_exit_code_2_for_bad_month_format(month: str) -> None:
    uow, use_case = _setup()

    code = await run(["--month", month], use_case)

    assert code == 2
    assert await _periods(uow) == []


@pytest.mark.parametrize(
    "argv", [["--unknown"], ["--month"], ["extra"], ["--month", "2026-09", "--month"], ["-x"]]
)
async def test_unknown_or_incomplete_arguments_exit_two_without_raising(argv: list[str]) -> None:
    uow, use_case = _setup()

    code = await run(argv, use_case)

    assert code == 2
    assert await _periods(uow) == []


async def test_cli_exit_code_1_on_use_case_error() -> None:
    code = await run([], cast("Any", _FailingUseCase()))

    assert code == 1


def _bare_environment(home: Path) -> dict[str, str]:
    """설정 값이 하나도 없는 환경(APP_* 없음, 비밀 없음)."""
    return {"PATH": os.environ.get("PATH", ""), "HOME": str(home)}


@pytest.mark.parametrize("argv", [["--month", "2026-9"], ["--unknown"], ["--month", "abc"]])
def test_module_entry_exits_two_for_bad_arguments_before_reading_settings(
    argv: list[str], tmp_path: Path
) -> None:
    done = subprocess.run(  # noqa: S603 - 테스트가 만든 고정 인자
        [sys.executable, "-m", "app.jobs.forecast_snapshot", *argv],
        cwd=tmp_path,
        env=_bare_environment(tmp_path),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert done.returncode == 2, (done.stdout, done.stderr)


def test_main_help_prints_usage_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    from app.jobs.forecast_snapshot import main  # noqa: PLC0415

    code = main(["--help"])

    out = capsys.readouterr()
    assert code == 0
    assert "--month" in out.out
    assert "인자 오류" not in out.err


async def test_run_help_exits_zero_without_taking_a_snapshot() -> None:
    use_case = _FailingUseCase()

    code = await run(["--help"], cast("Any", use_case))

    assert code == 0


def test_main_unknown_argument_still_exits_two() -> None:
    from app.jobs.forecast_snapshot import main  # noqa: PLC0415

    assert main(["--unknown"]) == 2
