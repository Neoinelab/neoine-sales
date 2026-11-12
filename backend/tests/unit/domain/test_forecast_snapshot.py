"""ForecastSnapshot.summary: 저장된 셀을 기간으로 모아 요약한다.

열은 스냅숏이 생성 시점에 함께 저장한 Forecast 코드 목록(`columns`: key·이름·outcome·순서)에서
만든다. 셀이 없는 코드도 열로 보이고(0건 열), 기간을 바꿔도 같은 열이 나오며, Lost는 열·행·합계에서
빠진다. 셀(`SnapshotCell`)에는 이름·outcome·순서가 없다(열에서 찾는다).
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.domain.code.values import ForecastOutcome
from app.domain.forecast.period import ForecastPeriod
from app.domain.forecast.snapshot import ForecastSnapshot, SnapshotCell, SnapshotColumn, YearMonth
from app.domain.forecast.summary import Tally
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId

KIM = uid("snap-kim")
LEE = uid("snap-lee")
TAKEN_AT = datetime(2026, 10, 1, 0, 5, tzinfo=UTC)
ORDERS = {"pipeline": 1, "best": 2, "most_likely": 3, "commit": 4, "won": 5, "lost": 6}
OUTCOMES = {"won": ForecastOutcome.WON, "lost": ForecastOutcome.LOST}


def _column(key: str, name: str | None = None) -> SnapshotColumn:
    return SnapshotColumn(
        key=key,
        name=name or key.title(),
        outcome=OUTCOMES.get(key, ForecastOutcome.OPEN),
        order=ORDERS[key],
    )


ALL_COLUMNS = tuple(_column(key) for key in ORDERS)


def _cell(  # noqa: PLR0913, PLR0917 - 셀의 독립 필드
    year: int,
    month: int,
    key: str = "pipeline",
    count: int = 1,
    amount: int = 100,
    owner: UserId = KIM,
) -> SnapshotCell:
    return SnapshotCell(
        revenue_year=year,
        revenue_month=month,
        owner_id=owner,
        forecast_key=key,
        tally=Tally(count, amount),
    )


def _snapshot(
    *cells: SnapshotCell, columns: tuple[SnapshotColumn, ...] = ALL_COLUMNS
) -> ForecastSnapshot:
    return ForecastSnapshot(
        period=YearMonth(2026, 9), taken_at=TAKEN_AT, columns=list(columns), cells=list(cells)
    )


def test_quarter_sums_its_three_months() -> None:
    """분기 요약은 그 분기 세 달의 셀을 합친다"""
    # given: 7·8·9월 셀이 있는 스냅숏
    snapshot = _snapshot(
        _cell(2026, 7, amount=10), _cell(2026, 8, amount=20), _cell(2026, 9, amount=30)
    )

    # when: Q3로 요약한다
    summary = snapshot.summary(ForecastPeriod(year=2026, quarters=frozenset({3})), None)

    # then: 세 달이 (3, 60)으로 합쳐진다
    assert summary.rows[0].cells["pipeline"] == Tally(3, 60)


def test_months_outside_the_quarter_are_left_out() -> None:
    """분기 밖 달과 다른 해의 셀은 뺀다"""
    # given: 6월·7월·10월·2025-08 셀이 있는 스냅숏
    snapshot = _snapshot(_cell(2026, 6), _cell(2026, 7), _cell(2026, 10), _cell(2025, 8))

    # when: 2026 Q3로 요약한다
    summary = snapshot.summary(ForecastPeriod(year=2026, quarters=frozenset({3})), None)

    # then: 7월 셀만 (1, 100)으로 남는다
    assert summary.rows[0].cells["pipeline"] == Tally(1, 100)


def test_year_only_period_sums_the_whole_year() -> None:
    """연도만 있는 기간은 그 해 전체를 합친다"""
    # given: 2026-01·2026-12·2027-01 셀이 있는 스냅숏
    snapshot = _snapshot(_cell(2026, 1), _cell(2026, 12), _cell(2027, 1))

    # when: 2026년으로 요약한다
    summary = snapshot.summary(ForecastPeriod(year=2026), None)

    # then: 2026년 두 셀만 (2, 200)이다
    assert summary.total.cells["pipeline"] == Tally(2, 200)


def test_month_period_takes_only_that_month() -> None:
    """월 기간은 그 달 셀만 합친다"""
    # given: 3월·4월 셀이 있는 스냅숏
    snapshot = _snapshot(_cell(2026, 3, amount=7), _cell(2026, 4, amount=9))

    # when: 2026년 3월로 요약한다
    summary = snapshot.summary(ForecastPeriod(year=2026, month=3), None)

    # then: 3월 셀만 (1, 7)이다
    assert summary.total.cells["pipeline"] == Tally(1, 7)


def test_owner_filter_keeps_only_that_owners_row() -> None:
    """담당자 조건은 그 담당자 행만 남긴다"""
    # given: KIM·LEE의 셀이 있는 스냅숏
    snapshot = _snapshot(_cell(2026, 7, owner=KIM), _cell(2026, 7, owner=LEE, amount=5))

    # when: LEE 조건으로 요약한다
    summary = snapshot.summary(ForecastPeriod(year=2026), LEE)

    # then: LEE 행만 있고 합계는 LEE 값이다
    assert [row.owner_id for row in summary.rows] == [LEE]
    assert summary.total.cells["pipeline"] == Tally(1, 5)


def test_cell_carries_no_code_name_outcome_or_order() -> None:
    """셀에는 이름·outcome·순서가 없다"""
    # when: 셀 필드 목록을 읽는다
    fields = set(SnapshotCell.__dataclass_fields__)

    # then: 연·월·담당자·key·건수 필드뿐이다
    assert fields == {"revenue_year", "revenue_month", "owner_id", "forecast_key", "tally"}


def test_columns_use_the_stored_names_and_order_not_the_cell_order() -> None:
    """열은 저장된 이름·순서를 쓰고 셀 순서와 무관하다"""
    # given: commit·pipeline·won 열이 섞인 순서로 저장된 스냅숏
    columns = (_column("commit", "확정"), _column("pipeline", "초기"), _column("won"))
    snapshot = _snapshot(_cell(2026, 7, "commit"), columns=columns)

    # when: 요약한다
    summary = snapshot.summary(ForecastPeriod(year=2026), None)

    # then: 저장 order 순이고 저장된 이름이다
    assert [(c.key, c.name, c.order) for c in summary.columns] == [
        ("pipeline", "초기", 1),
        ("commit", "확정", 4),
        ("won", "Won", 5),
    ]


def test_columns_carry_the_stored_outcome() -> None:
    """열은 저장된 outcome을 담는다"""
    # when: 셀 없는 스냅숏을 요약한다
    summary = _snapshot().summary(ForecastPeriod(year=2026), None)

    # then: 열 outcome이 저장된 값(won만 won, Lost 제외)이다
    assert {c.key: c.outcome for c in summary.columns} == {
        "pipeline": ForecastOutcome.OPEN,
        "best": ForecastOutcome.OPEN,
        "most_likely": ForecastOutcome.OPEN,
        "commit": ForecastOutcome.OPEN,
        "won": ForecastOutcome.WON,
    }


def test_a_code_without_any_deal_is_still_a_zero_column() -> None:
    """Deal이 없는 코드도 0건 열로 나온다"""
    # given: pipeline 셀만 있는 스냅숏
    snapshot = _snapshot(_cell(2026, 7, "pipeline", amount=5))

    # when: 요약한다
    summary = snapshot.summary(ForecastPeriod(year=2026), None)

    # then: 저장된 열이 모두 나오고 commit은 0, pipeline은 값이 있다
    assert [c.key for c in summary.columns] == ["pipeline", "best", "most_likely", "commit", "won"]
    assert summary.total.cells["commit"] == Tally.ZERO
    assert summary.total.cells["pipeline"] == Tally(1, 5)


def test_columns_are_the_same_whatever_period_is_selected() -> None:
    """열은 선택한 기간과 무관하게 같다"""
    # given: 1월 commit·7월 pipeline 셀이 있는 스냅숏
    snapshot = _snapshot(_cell(2026, 1, "commit"), _cell(2026, 7, "pipeline"))

    # when: Q3, 연도, 셀 없는 2030년으로 각각 요약한다
    q3 = snapshot.summary(ForecastPeriod(year=2026, quarters=frozenset({3})), None)
    year = snapshot.summary(ForecastPeriod(year=2026), None)
    empty_period = snapshot.summary(ForecastPeriod(year=2030), None)

    # then: 세 요약의 열이 같고 Q3에는 7월 값만 있다
    assert [c.key for c in q3.columns] == [c.key for c in year.columns]
    assert [c.key for c in empty_period.columns] == [c.key for c in year.columns]
    assert q3.total.cells["commit"] == Tally.ZERO
    assert q3.total.cells["pipeline"] == Tally(1, 100)


def test_lost_column_is_not_shown_and_its_cells_are_left_out_of_rows_and_totals() -> None:
    """Lost 열은 보이지 않고 Lost 셀은 행·합계에서 빠진다"""
    # given: Lost 999원과 pipeline 5원 셀
    snapshot = _snapshot(_cell(2026, 7, "lost", amount=999), _cell(2026, 7, "pipeline", amount=5))

    # when: 요약한다
    summary = snapshot.summary(ForecastPeriod(year=2026), None)

    # then: lost 열이 없고 Open 합계는 (1, 5)다
    assert "lost" not in [c.key for c in summary.columns]
    assert summary.total.open_total == Tally(1, 5)


def test_owner_with_only_lost_cells_has_no_row() -> None:
    """Lost 셀만 있는 담당자는 행이 없다"""
    # given: LEE는 Lost 셀만, KIM은 pipeline 셀
    snapshot = _snapshot(_cell(2026, 7, "lost", owner=LEE), _cell(2026, 7, "pipeline", owner=KIM))

    # when: 요약한다
    summary = snapshot.summary(ForecastPeriod(year=2026), None)

    # then: KIM 행만 있다
    assert [row.owner_id for row in summary.rows] == [KIM]


def test_open_total_leaves_out_won_and_total_row_is_the_sum_of_rows() -> None:
    """Open 합계는 Won을 빼고 합계 행은 행의 합이다"""
    # given: KIM pipeline 10·won 500, LEE commit 7
    snapshot = _snapshot(
        _cell(2026, 7, "pipeline", amount=10, owner=KIM),
        _cell(2026, 7, "won", amount=500, owner=KIM),
        _cell(2026, 8, "commit", amount=7, owner=LEE),
    )

    # when: 요약한다
    summary = snapshot.summary(ForecastPeriod(year=2026), None)

    # then: 행별 Open 합계, 합계 행 Open (2, 17)·won (1, 500), 합계 행 owner 없음
    by_owner = {row.owner_id: row for row in summary.rows}
    assert by_owner[KIM].open_total == Tally(1, 10)
    assert by_owner[KIM].cells["won"] == Tally(1, 500)
    assert summary.total.open_total == Tally(2, 17)
    assert summary.total.cells["won"] == Tally(1, 500)
    assert summary.total.owner_id is None


def test_snapshot_without_cells_has_zero_columns_but_no_rows() -> None:
    """셀이 없는 스냅숏은 0건 열만 있고 행이 없다"""
    # when: 셀 없는 스냅숏을 요약한다
    summary = _snapshot().summary(ForecastPeriod(year=2026), None)

    # then: 열은 모두 있고 행이 없으며 Open 합계는 0이다
    assert [c.key for c in summary.columns] == ["pipeline", "best", "most_likely", "commit", "won"]
    assert list(summary.rows) == []
    assert summary.total.open_total == Tally.ZERO


def test_snapshot_without_columns_has_no_columns() -> None:
    """열이 없는 스냅숏은 열도 행도 없다"""
    # when: 열이 없는 스냅숏을 요약한다
    summary = _snapshot(columns=()).summary(ForecastPeriod(year=2026), None)

    # then: 열도 행도 없다
    assert list(summary.columns) == []
    assert list(summary.rows) == []


def test_separated_quarters_sum_only_their_months() -> None:
    """떨어진 분기는 그 달들만 합친다"""
    # given: 1~12월 각 1건(금액=월)
    cells = [_cell(2026, month, amount=month) for month in range(1, 13)]
    snapshot = _snapshot(*cells)

    # when: Q1·Q3로 요약한다
    summary = snapshot.summary(ForecastPeriod(year=2026, quarters=frozenset({1, 3})), None)

    # then: 1·2·3·7·8·9월만 (6, 30)이다
    assert summary.total.cells["pipeline"] == Tally(6, 1 + 2 + 3 + 7 + 8 + 9)


def test_the_gap_quarter_between_chosen_quarters_is_left_out() -> None:
    """고른 분기 사이의 분기는 뺀다"""
    # given: 5월(사이 분기)과 2월 셀
    snapshot = _snapshot(_cell(2026, 5, amount=1000), _cell(2026, 2, amount=1))

    # when: Q1·Q3로 요약한다
    summary = snapshot.summary(ForecastPeriod(year=2026, quarters=frozenset({1, 3})), None)

    # then: 2월 셀만 (1, 1)이다
    assert summary.total.cells["pipeline"] == Tally(1, 1)
