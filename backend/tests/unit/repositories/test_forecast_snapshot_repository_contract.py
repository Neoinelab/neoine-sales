"""ForecastSnapshotRepository 계약(P6 R2 AC-13·14·16·19): Fake와 SQL에 같은 기대값.

기준 월(연, 월)당 스냅숏 하나. `replace`는 같은 기준 월이 있으면 헤더 시각과 열(저장 당시의 코드
목록: key·이름·outcome·순서)과 셀을 통째로 바꾸고 없으면 새로 만든다. 열은 셀이 없는 코드도
저장한다(0건 열). 셀에는 key만 있고 이름·outcome·순서는 열에서 찾는다. Lost도 저장한다.
목록은 최근 기준 월부터다. 잠금(`lock_period`)의 직렬화 동작은 검증하지 않는다
(동시 실행은 테스트 대상이 아니다).
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.domain.code.values import ForecastOutcome
from app.domain.forecast.snapshot import YearMonth
from tests.support.user_ids import uid
from tests.unit.repositories.forecast_snapshot_case import (
    default_columns,
    make_cell,
    make_column,
    make_snapshot,
)

if TYPE_CHECKING:
    from app.domain.forecast.snapshot import ForecastSnapshot
    from tests.unit.repositories.forecast_snapshot_case import SnapshotCase

SEPT = YearMonth(2026, 9)
KIM = uid("snapshot-kim")
LEE = uid("snapshot-lee")


def _columns(snapshot: ForecastSnapshot) -> list[tuple[str, str, ForecastOutcome, int]]:
    return [(c.key, c.name, c.outcome, c.order) for c in snapshot.columns]


def _cells(snapshot: ForecastSnapshot) -> set[tuple[object, ...]]:
    return {
        (
            c.revenue_year,
            c.revenue_month,
            c.owner_id,
            c.forecast_key,
            c.tally.count,
            c.tally.amount,
        )
        for c in snapshot.cells
    }


async def test_missing_period_is_none(snapshot_case: SnapshotCase) -> None:
    assert await snapshot_case.snapshots.get(SEPT) is None


async def test_no_snapshots_lists_nothing(snapshot_case: SnapshotCase) -> None:
    assert list(await snapshot_case.snapshots.list_periods()) == []


async def test_replace_saves_a_new_snapshot_that_get_returns(snapshot_case: SnapshotCase) -> None:
    await snapshot_case.ensure_owner(KIM)
    await snapshot_case.ensure_owner(LEE)
    saved = make_snapshot(
        SEPT,
        make_cell(KIM, 2026, 8, "pipeline", count=2, amount=140),
        make_cell(KIM, 2026, 9, "commit", count=1, amount=7),
        make_cell(LEE, 2026, 8, "won", count=1, amount=500),
        columns=[make_column("pipeline", "초기"), make_column("commit"), make_column("won")],
    )

    await snapshot_case.snapshots.replace(saved)

    found = await snapshot_case.snapshots.get(SEPT)
    assert found is not None
    assert found.period == SEPT
    assert found.taken_at == saved.taken_at
    assert _cells(found) == _cells(saved)
    assert _columns(found) == _columns(saved)


async def test_columns_keep_the_stored_key_name_outcome_and_order(
    snapshot_case: SnapshotCase,
) -> None:
    await snapshot_case.snapshots.replace(
        make_snapshot(
            SEPT,
            columns=[make_column("won"), make_column("commit", "확정"), make_column("lost")],
        )
    )

    found = await snapshot_case.snapshots.get(SEPT)

    assert found is not None
    assert _columns(found) == [  # 저장 순서(order 오름차순)로 돌려준다
        ("commit", "확정", ForecastOutcome.OPEN, 4),
        ("won", "Won", ForecastOutcome.WON, 5),
        ("lost", "Lost", ForecastOutcome.LOST, 6),
    ]


async def test_columns_without_any_cell_are_stored(snapshot_case: SnapshotCase) -> None:
    await snapshot_case.ensure_owner(KIM)
    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, make_cell(KIM, key="pipeline"), columns=default_columns())
    )

    found = await snapshot_case.snapshots.get(SEPT)

    assert found is not None
    assert {c.key for c in found.columns} == {
        "pipeline",
        "best",
        "most_likely",
        "commit",
        "won",
        "lost",
    }
    assert [c.forecast_key for c in found.cells] == ["pipeline"]


async def test_a_snapshot_without_columns_or_cells_is_stored(snapshot_case: SnapshotCase) -> None:
    await snapshot_case.snapshots.replace(make_snapshot(SEPT, columns=[]))

    found = await snapshot_case.snapshots.get(SEPT)

    assert found is not None
    assert list(found.columns) == []
    assert list(found.cells) == []


async def test_lost_and_won_cells_are_stored_with_their_key(snapshot_case: SnapshotCase) -> None:
    await snapshot_case.ensure_owner(KIM)
    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, make_cell(KIM, key="lost", amount=9), make_cell(KIM, key="won"))
    )

    found = await snapshot_case.snapshots.get(SEPT)

    assert found is not None
    assert {c.forecast_key: c.tally.amount for c in found.cells} == {"lost": 9, "won": 100}


async def test_amounts_beyond_32_bits_are_stored_exactly(snapshot_case: SnapshotCase) -> None:
    await snapshot_case.ensure_owner(KIM)
    big = 2**40 + 1
    await snapshot_case.snapshots.replace(make_snapshot(SEPT, make_cell(KIM, amount=big)))

    found = await snapshot_case.snapshots.get(SEPT)

    assert found is not None
    assert found.cells[0].tally.amount == big


async def test_a_snapshot_without_cells_is_stored(snapshot_case: SnapshotCase) -> None:
    await snapshot_case.snapshots.replace(make_snapshot(SEPT))

    found = await snapshot_case.snapshots.get(SEPT)

    assert found is not None
    assert list(found.cells) == []
    assert [info.period for info in await snapshot_case.snapshots.list_periods()] == [SEPT]


async def test_replace_swaps_the_cells_and_the_taken_at_of_the_same_period(
    snapshot_case: SnapshotCase,
) -> None:
    await snapshot_case.ensure_owner(KIM)
    await snapshot_case.ensure_owner(LEE)
    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, make_cell(KIM, key="pipeline"), make_cell(LEE, key="best"))
    )
    later = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)

    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, make_cell(KIM, key="commit", amount=7), taken_at=later)
    )

    found = await snapshot_case.snapshots.get(SEPT)
    assert found is not None
    assert found.taken_at == later
    assert [(c.owner_id, c.forecast_key, c.tally.amount) for c in found.cells] == [
        (KIM, "commit", 7)
    ]


async def test_replace_swaps_the_columns_of_the_same_period(snapshot_case: SnapshotCase) -> None:
    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, columns=[make_column("pipeline", "옛 이름"), make_column("best")])
    )

    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, columns=[make_column("pipeline", "새 이름"), make_column("commit")])
    )

    found = await snapshot_case.snapshots.get(SEPT)
    assert found is not None
    assert sorted((c.key, c.name) for c in found.columns) == [
        ("commit", "Commit"),
        ("pipeline", "새 이름"),
    ]


async def test_columns_of_another_period_keep_their_own_names(snapshot_case: SnapshotCase) -> None:
    await snapshot_case.snapshots.replace(
        make_snapshot(YearMonth(2026, 8), columns=[make_column("commit", "8월 이름")])
    )

    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, columns=[make_column("commit", "9월 이름")])
    )

    august = await snapshot_case.snapshots.get(YearMonth(2026, 8))
    assert august is not None
    assert [(c.key, c.name) for c in august.columns] == [("commit", "8월 이름")]


async def test_replace_keeps_a_single_snapshot_per_period(snapshot_case: SnapshotCase) -> None:
    await snapshot_case.snapshots.replace(make_snapshot(SEPT))
    await snapshot_case.snapshots.replace(make_snapshot(SEPT))

    assert [info.period for info in await snapshot_case.snapshots.list_periods()] == [SEPT]


async def test_replace_leaves_other_periods_untouched(snapshot_case: SnapshotCase) -> None:
    await snapshot_case.ensure_owner(KIM)
    await snapshot_case.snapshots.replace(make_snapshot(YearMonth(2026, 8), make_cell(KIM)))

    await snapshot_case.snapshots.replace(make_snapshot(SEPT, make_cell(KIM, key="commit")))

    august = await snapshot_case.snapshots.get(YearMonth(2026, 8))
    assert august is not None
    assert [c.forecast_key for c in august.cells] == ["pipeline"]


async def test_list_periods_is_newest_first_with_taken_at(snapshot_case: SnapshotCase) -> None:
    taken = {
        YearMonth(2025, 12): datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        YearMonth(2026, 8): datetime(2026, 9, 1, 0, 5, tzinfo=UTC),
        YearMonth(2026, 9): datetime(2026, 10, 1, 0, 5, tzinfo=UTC),
    }
    for period in (YearMonth(2026, 8), YearMonth(2025, 12), YearMonth(2026, 9)):
        await snapshot_case.snapshots.replace(make_snapshot(period, taken_at=taken[period]))

    infos = await snapshot_case.snapshots.list_periods()

    assert [(info.period, info.taken_at) for info in infos] == [
        (YearMonth(2026, 9), taken[YearMonth(2026, 9)]),
        (YearMonth(2026, 8), taken[YearMonth(2026, 8)]),
        (YearMonth(2025, 12), taken[YearMonth(2025, 12)]),
    ]


async def test_list_orders_by_year_before_month(snapshot_case: SnapshotCase) -> None:
    for period in (YearMonth(2026, 12), YearMonth(2027, 1), YearMonth(2026, 2)):
        await snapshot_case.snapshots.replace(make_snapshot(period))

    infos = await snapshot_case.snapshots.list_periods()

    assert [info.period for info in infos] == [
        YearMonth(2027, 1),
        YearMonth(2026, 12),
        YearMonth(2026, 2),
    ]


async def test_lock_then_replace_works_in_one_transaction(snapshot_case: SnapshotCase) -> None:
    await snapshot_case.ensure_owner(KIM)

    await snapshot_case.snapshots.lock_period(SEPT)
    await snapshot_case.snapshots.replace(make_snapshot(SEPT, make_cell(KIM)))

    found = await snapshot_case.snapshots.get(SEPT)
    assert found is not None
    assert len(found.cells) == 1
    assert [info.period for info in await snapshot_case.snapshots.list_periods()] == [SEPT]
