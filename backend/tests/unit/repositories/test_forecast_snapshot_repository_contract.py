"""ForecastSnapshotRepository 계약: Fake와 SQL에 같은 기대값.

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
    """없는 기준 월은 None이다"""
    # when: 없는 기준 월을 읽는다
    found = await snapshot_case.snapshots.get(SEPT)
    # then: None이다
    assert found is None


async def test_no_snapshots_lists_nothing(snapshot_case: SnapshotCase) -> None:
    """스냅숏이 없으면 목록이 비어 있다

    테스트 코드: FC-025
    """
    # when: 기준 월 목록을 읽는다
    periods = list(await snapshot_case.snapshots.list_periods())
    # then: 비어 있다
    assert periods == []


async def test_replace_saves_a_new_snapshot_that_get_returns(snapshot_case: SnapshotCase) -> None:
    """새 스냅숏을 저장하면 get이 같은 값을 돌려준다"""
    # given: KIM·LEE와 셀 3개, 열 3개의 스냅숏
    await snapshot_case.ensure_owner(KIM)
    await snapshot_case.ensure_owner(LEE)
    saved = make_snapshot(
        SEPT,
        make_cell(KIM, 2026, 8, "pipeline", count=2, amount=140),
        make_cell(KIM, 2026, 9, "commit", count=1, amount=7),
        make_cell(LEE, 2026, 8, "won", count=1, amount=500),
        columns=[make_column("pipeline", "초기"), make_column("commit"), make_column("won")],
    )

    # when: 저장한다
    await snapshot_case.snapshots.replace(saved)

    # when: 다시 읽는다
    found = await snapshot_case.snapshots.get(SEPT)
    # then: 기준 월·생성 시각·셀·열이 저장한 값과 같다
    assert found is not None
    assert found.period == SEPT
    assert found.taken_at == saved.taken_at
    assert _cells(found) == _cells(saved)
    assert _columns(found) == _columns(saved)


async def test_columns_keep_the_stored_key_name_outcome_and_order(
    snapshot_case: SnapshotCase,
) -> None:
    """열은 저장된 key·이름·outcome·order를 order 순으로 돌려준다"""
    # given: 순서가 섞인 열 3개의 스냅숏을 저장한다
    await snapshot_case.snapshots.replace(
        make_snapshot(
            SEPT,
            columns=[make_column("won"), make_column("commit", "확정"), make_column("lost")],
        )
    )

    # when: 읽는다
    found = await snapshot_case.snapshots.get(SEPT)

    # then: 스냅숏이 있고 order 오름차순이며 저장된 이름·outcome이다
    assert found is not None
    assert _columns(found) == [  # 저장 순서(order 오름차순)로 돌려준다
        ("commit", "확정", ForecastOutcome.OPEN, 4),
        ("won", "Won", ForecastOutcome.WON, 5),
        ("lost", "Lost", ForecastOutcome.LOST, 6),
    ]


async def test_columns_without_any_cell_are_stored(snapshot_case: SnapshotCase) -> None:
    """셀이 없는 코드의 열도 저장한다"""
    # given: pipeline 셀 하나와 기본 열 6개의 스냅숏을 저장한다
    await snapshot_case.ensure_owner(KIM)
    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, make_cell(KIM, key="pipeline"), columns=default_columns())
    )

    # when: 읽는다
    found = await snapshot_case.snapshots.get(SEPT)

    # then: 열 6개와 셀 하나가 있다
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
    """열도 셀도 없는 스냅숏도 저장한다"""
    # given: 열도 셀도 없는 스냅숏을 저장한다
    await snapshot_case.snapshots.replace(make_snapshot(SEPT, columns=[]))

    # when: 읽는다
    found = await snapshot_case.snapshots.get(SEPT)

    # then: 열도 셀도 비어 있다
    assert found is not None
    assert list(found.columns) == []
    assert list(found.cells) == []


async def test_lost_and_won_cells_are_stored_with_their_key(snapshot_case: SnapshotCase) -> None:
    """Lost·Won 셀도 key와 함께 저장한다"""
    # given: Lost·Won 셀을 저장한다
    await snapshot_case.ensure_owner(KIM)
    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, make_cell(KIM, key="lost", amount=9), make_cell(KIM, key="won"))
    )

    # when: 읽는다
    found = await snapshot_case.snapshots.get(SEPT)

    # then: key별 금액이 그대로다
    assert found is not None
    assert {c.forecast_key: c.tally.amount for c in found.cells} == {"lost": 9, "won": 100}


async def test_amounts_beyond_32_bits_are_stored_exactly(snapshot_case: SnapshotCase) -> None:
    """32비트를 넘는 금액을 정확히 저장한다"""
    # given: 2^40+1 금액 셀을 저장한다
    await snapshot_case.ensure_owner(KIM)
    big = 2**40 + 1
    await snapshot_case.snapshots.replace(make_snapshot(SEPT, make_cell(KIM, amount=big)))

    # when: 읽는다
    found = await snapshot_case.snapshots.get(SEPT)

    # then: 금액이 그대로다
    assert found is not None
    assert found.cells[0].tally.amount == big


async def test_a_snapshot_without_cells_is_stored(snapshot_case: SnapshotCase) -> None:
    """셀이 없는 스냅숏도 목록에 나온다"""
    # given: 셀 없는 스냅숏을 저장한다
    await snapshot_case.snapshots.replace(make_snapshot(SEPT))

    # when: 읽는다
    found = await snapshot_case.snapshots.get(SEPT)

    # then: 셀이 없고 목록에 기준 월이 있다
    assert found is not None
    assert list(found.cells) == []
    assert [info.period for info in await snapshot_case.snapshots.list_periods()] == [SEPT]


async def test_replace_swaps_the_cells_and_the_taken_at_of_the_same_period(
    snapshot_case: SnapshotCase,
) -> None:
    """같은 기준 월을 다시 저장하면 셀과 생성 시각이 통째로 바뀐다

    테스트 코드: FC-020
    """
    # given: 셀 둘의 스냅숏이 이미 있다
    await snapshot_case.ensure_owner(KIM)
    await snapshot_case.ensure_owner(LEE)
    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, make_cell(KIM, key="pipeline"), make_cell(LEE, key="best"))
    )
    # when: 더 늦은 시각의 셀 하나짜리 스냅숏으로 다시 저장한다
    later = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)

    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, make_cell(KIM, key="commit", amount=7), taken_at=later)
    )

    # when: 읽는다
    found = await snapshot_case.snapshots.get(SEPT)
    # then: 생성 시각과 셀이 새 값뿐이다
    assert found is not None
    assert found.taken_at == later
    assert [(c.owner_id, c.forecast_key, c.tally.amount) for c in found.cells] == [
        (KIM, "commit", 7)
    ]


async def test_replace_swaps_the_columns_of_the_same_period(snapshot_case: SnapshotCase) -> None:
    """같은 기준 월을 다시 저장하면 열도 통째로 바뀐다

    테스트 코드: FC-020
    """
    # given: 열 pipeline(옛 이름)·best 스냅숏이 이미 있다
    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, columns=[make_column("pipeline", "옛 이름"), make_column("best")])
    )

    # when: pipeline(새 이름)·commit 열로 다시 저장한다
    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, columns=[make_column("pipeline", "새 이름"), make_column("commit")])
    )

    # when: 읽는다
    found = await snapshot_case.snapshots.get(SEPT)
    # then: 열이 새 목록 그대로다
    assert found is not None
    assert sorted((c.key, c.name) for c in found.columns) == [
        ("commit", "Commit"),
        ("pipeline", "새 이름"),
    ]


async def test_columns_of_another_period_keep_their_own_names(snapshot_case: SnapshotCase) -> None:
    """다른 기준 월의 열은 자기 이름을 유지한다

    테스트 코드: FC-020
    """
    # given: 8월·9월 스냅숏의 commit 열 이름이 다르다
    await snapshot_case.snapshots.replace(
        make_snapshot(YearMonth(2026, 8), columns=[make_column("commit", "8월 이름")])
    )

    await snapshot_case.snapshots.replace(
        make_snapshot(SEPT, columns=[make_column("commit", "9월 이름")])
    )

    # when: 8월 스냅숏을 읽는다
    august = await snapshot_case.snapshots.get(YearMonth(2026, 8))
    # then: 8월 이름이 그대로다
    assert august is not None
    assert [(c.key, c.name) for c in august.columns] == [("commit", "8월 이름")]


async def test_replace_keeps_a_single_snapshot_per_period(snapshot_case: SnapshotCase) -> None:
    """같은 기준 월의 스냅숏은 하나만 남는다

    테스트 코드: FC-020
    """
    # given: 기준 월의 스냅숏을 저장해 둔 상태
    await snapshot_case.snapshots.replace(make_snapshot(SEPT))

    # when: 같은 기준 월로 다시 저장한다
    await snapshot_case.snapshots.replace(make_snapshot(SEPT))

    # then: 목록에 기준 월이 하나뿐이다
    listed = await snapshot_case.snapshots.list_periods()
    assert [info.period for info in listed] == [SEPT]


async def test_replace_leaves_other_periods_untouched(snapshot_case: SnapshotCase) -> None:
    """다른 기준 월의 스냅숏은 건드리지 않는다

    테스트 코드: FC-020
    """
    # given: 8월 스냅숏을 저장한다
    await snapshot_case.ensure_owner(KIM)
    await snapshot_case.snapshots.replace(make_snapshot(YearMonth(2026, 8), make_cell(KIM)))

    # when: 9월을 저장한다
    await snapshot_case.snapshots.replace(make_snapshot(SEPT, make_cell(KIM, key="commit")))

    # then: 8월 스냅숏의 셀이 그대로다
    august = await snapshot_case.snapshots.get(YearMonth(2026, 8))
    assert august is not None
    assert [c.forecast_key for c in august.cells] == ["pipeline"]


async def test_list_periods_is_newest_first_with_taken_at(snapshot_case: SnapshotCase) -> None:
    """기준 월 목록은 최근 순이고 생성 시각을 함께 준다

    테스트 코드: FC-025
    """
    # given: 2025-12, 2026-08, 2026-09 스냅숏을 섞인 순서로 저장한다
    taken = {
        YearMonth(2025, 12): datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        YearMonth(2026, 8): datetime(2026, 9, 1, 0, 5, tzinfo=UTC),
        YearMonth(2026, 9): datetime(2026, 10, 1, 0, 5, tzinfo=UTC),
    }
    for period in (YearMonth(2026, 8), YearMonth(2025, 12), YearMonth(2026, 9)):
        await snapshot_case.snapshots.replace(make_snapshot(period, taken_at=taken[period]))

    # when: 목록을 읽는다
    infos = await snapshot_case.snapshots.list_periods()

    # then: 2026-09, 2026-08, 2025-12 순이다
    assert [(info.period, info.taken_at) for info in infos] == [
        (YearMonth(2026, 9), taken[YearMonth(2026, 9)]),
        (YearMonth(2026, 8), taken[YearMonth(2026, 8)]),
        (YearMonth(2025, 12), taken[YearMonth(2025, 12)]),
    ]


async def test_list_orders_by_year_before_month(snapshot_case: SnapshotCase) -> None:
    """목록은 연도 먼저, 같은 해는 월 순(최근 먼저)이다

    테스트 코드: FC-025
    """
    # given: 2026-12, 2027-01, 2026-02 스냅숏을 저장한다
    for period in (YearMonth(2026, 12), YearMonth(2027, 1), YearMonth(2026, 2)):
        await snapshot_case.snapshots.replace(make_snapshot(period))

    # when: 목록을 읽는다
    infos = await snapshot_case.snapshots.list_periods()

    # then: 2027-01, 2026-12, 2026-02 순이다
    assert [info.period for info in infos] == [
        YearMonth(2027, 1),
        YearMonth(2026, 12),
        YearMonth(2026, 2),
    ]


async def test_lock_then_replace_works_in_one_transaction(snapshot_case: SnapshotCase) -> None:
    """기준 월 잠금 뒤 같은 트랜잭션에서 저장할 수 있다"""
    # given: 담당자 KIM
    await snapshot_case.ensure_owner(KIM)

    # when: 기준 월을 잠그고 저장한다
    await snapshot_case.snapshots.lock_period(SEPT)
    await snapshot_case.snapshots.replace(make_snapshot(SEPT, make_cell(KIM)))

    # when: 읽는다
    found = await snapshot_case.snapshots.get(SEPT)
    # then: 스냅숏이 하나 저장된다
    assert found is not None
    assert len(found.cells) == 1
    assert [info.period for info in await snapshot_case.snapshots.list_periods()] == [SEPT]


async def test_exists_is_false_for_a_missing_period(snapshot_case: SnapshotCase) -> None:
    """없는 기준 월은 exists가 False다"""
    # when: 없는 기준 월을 확인한다
    exists = await snapshot_case.snapshots.exists(SEPT)

    # then: False다
    assert exists is False


async def test_exists_is_true_after_replace(snapshot_case: SnapshotCase) -> None:
    """저장한 기준 월은 exists가 True다"""
    # given: 스냅숏을 저장한다
    await snapshot_case.snapshots.replace(make_snapshot(SEPT))

    # when: 저장한 기준 월을 확인한다
    exists = await snapshot_case.snapshots.exists(SEPT)

    # then: True다
    assert exists is True


async def test_exists_is_false_for_another_month(snapshot_case: SnapshotCase) -> None:
    """다른 월·다른 해는 exists가 False다"""
    # given: 2026-09 스냅숏을 저장한다
    await snapshot_case.snapshots.replace(make_snapshot(SEPT))

    # when: 2026-08·2025-09를 확인한다
    other_month = await snapshot_case.snapshots.exists(YearMonth(2026, 8))
    other_year = await snapshot_case.snapshots.exists(YearMonth(2025, 9))

    # then: 모두 False다
    assert other_month is False
    assert other_year is False
