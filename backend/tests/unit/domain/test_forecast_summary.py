"""ForecastSummary.build / ForecastColumn.from_codes / ordered.

규칙: Lost 열·묶음은 제외, open_total은 OPEN 셀의 합(Won·Lost 제외), total은 행 합, 없는 셀은 0,
기간 안에 Open 또는 Won이 없는 담당자는 행에서 뺀다.
"""

from app.domain.code.values import CodeKind, ForecastOutcome
from app.domain.forecast.summary import (
    ForecastBucket,
    ForecastColumn,
    ForecastSummary,
    Tally,
)
from tests.fakes.catalog_seed import default_codes
from tests.support.user_ids import uid

KIM = uid("fc-kim")
LEE = uid("fc-lee")
PARK = uid("fc-park")

PIPELINE = ForecastColumn("pipeline", "Pipeline", ForecastOutcome.OPEN, 1)
BEST = ForecastColumn("best", "Best", ForecastOutcome.OPEN, 2)
COMMIT = ForecastColumn("commit", "Commit", ForecastOutcome.OPEN, 4)
WON = ForecastColumn("won", "Won", ForecastOutcome.WON, 5)
LOST = ForecastColumn("lost", "Lost", ForecastOutcome.LOST, 6)
COLUMNS = [PIPELINE, BEST, COMMIT, WON, LOST]


def _bucket(owner: object, key: str, count: int, amount: int) -> ForecastBucket:
    return ForecastBucket(owner, key, Tally(count, amount))  # type: ignore[arg-type]


def _row(summary: ForecastSummary, owner: object) -> object:
    return next(row for row in summary.rows if row.owner_id == owner)


# ---- Tally ----


def test_tally_add_sums_count_and_amount() -> None:
    """Tally 덧셈은 건수와 금액을 각각 더한다"""
    # when: 두 Tally를 더한다
    total = Tally(2, 100).add(Tally(3, 50))
    # then: 건수와 금액이 합쳐진다
    assert total == Tally(5, 150)


def test_tally_zero_is_the_identity() -> None:
    """Tally.ZERO는 덧셈의 항등원이다"""
    # when: ZERO를 다른 Tally에 더한다
    added = Tally(4, 9).add(Tally.ZERO)

    # then: ZERO는 (0, 0)이고 더해도 값이 변하지 않는다
    assert Tally(0, 0) == Tally.ZERO
    assert added == Tally(4, 9)


# ---- from_codes ----


def test_columns_from_default_codes_are_in_order_without_lost() -> None:
    """기본 코드에서 만든 열은 order 순이고 Lost가 없다"""
    # given: 기본 Forecast 코드
    codes = [c for c in default_codes() if c.kind is CodeKind.FORECAST]

    # when: 코드에서 열을 만든다
    columns = ForecastColumn.from_codes(codes)

    # then: pipeline~won 순이고 won의 outcome이 won이며 order가 오름차순이다
    assert [c.key for c in columns] == ["pipeline", "best", "most_likely", "commit", "won"]
    assert [c.outcome for c in columns][-1] is ForecastOutcome.WON
    assert [c.order for c in columns] == sorted(c.order for c in columns)


def test_columns_carry_the_code_name_for_display() -> None:
    """열은 표시용 코드 이름을 담는다"""
    # given: 기본 Forecast 코드
    codes = [c for c in default_codes() if c.kind is CodeKind.FORECAST]

    # when: 열을 만든다
    columns = ForecastColumn.from_codes(codes)

    # then: most_likely의 이름은 "Most Likely"다
    assert {c.key: c.name for c in columns}["most_likely"] == "Most Likely"


# ---- build: 열 ----


def test_lost_column_is_excluded_from_columns() -> None:
    """Lost 열은 요약 열에서 제외한다"""
    # when: Lost를 포함한 열로 요약을 만든다
    summary = ForecastSummary.build(COLUMNS, [])

    # then: 열에 lost가 없다
    assert [c.key for c in summary.columns] == ["pipeline", "best", "commit", "won"]


def test_custom_open_code_becomes_column() -> None:
    """추가한 Open 코드도 열이 된다"""
    # given: order 3의 Open 코드 verbal
    extra = ForecastColumn("verbal", "Verbal", ForecastOutcome.OPEN, 3)

    # when: 요약을 만든다
    summary = ForecastSummary.build([PIPELINE, extra, WON], [_bucket(KIM, "verbal", 1, 70)])

    # then: order 순으로 열이 되고 셀·Open 합계에 반영된다
    assert [c.key for c in summary.columns] == ["pipeline", "verbal", "won"]
    assert summary.rows[0].cells["verbal"] == Tally(1, 70)
    assert summary.rows[0].open_total == Tally(1, 70)


# ---- build: 행·셀 ----


def test_missing_cells_are_zero() -> None:
    """Deal이 없는 칸은 0이다"""
    # when: commit 묶음 하나로 요약을 만든다
    summary = ForecastSummary.build(COLUMNS, [_bucket(KIM, "commit", 1, 100)])

    # then: 모든 열이 있고 commit만 값이 있다
    cells = summary.rows[0].cells
    assert set(cells) == {"pipeline", "best", "commit", "won"}
    assert cells["pipeline"] == Tally.ZERO
    assert cells["won"] == Tally.ZERO
    assert cells["commit"] == Tally(1, 100)


def test_open_total_sums_only_open_cells() -> None:
    """Open 합계는 Open 열만 더한다"""
    # given: pipeline·commit·best 묶음
    buckets = [
        _bucket(KIM, "pipeline", 2, 100),
        _bucket(KIM, "commit", 1, 50),
        _bucket(KIM, "best", 3, 30),
    ]

    # when: 요약을 만든다
    summary = ForecastSummary.build(COLUMNS, buckets)

    # then: Open 합계는 (6, 180)이다
    assert summary.rows[0].open_total == Tally(6, 180)


def test_won_is_not_in_open_total() -> None:
    """Won은 Open 합계에 들지 않는다"""
    # when: commit과 won 묶음으로 요약을 만든다
    summary = ForecastSummary.build(
        COLUMNS, [_bucket(KIM, "commit", 1, 50), _bucket(KIM, "won", 4, 400)]
    )

    # then: Open 합계는 commit뿐이고 won 셀은 그대로다
    row = summary.rows[0]
    assert row.open_total == Tally(1, 50)
    assert row.cells["won"] == Tally(4, 400)


def test_lost_bucket_is_ignored() -> None:
    """Lost 묶음은 무시한다"""
    # when: commit과 lost 묶음으로 요약을 만든다
    summary = ForecastSummary.build(
        COLUMNS, [_bucket(KIM, "commit", 1, 50), _bucket(KIM, "lost", 9, 900)]
    )

    # then: 행·합계 어디에도 lost가 없고 Open 합계는 commit뿐이다
    assert summary.rows[0].open_total == Tally(1, 50)
    assert "lost" not in summary.rows[0].cells
    assert "lost" not in summary.total.cells
    assert summary.total.open_total == Tally(1, 50)


def test_owner_with_only_lost_has_no_row() -> None:
    """Lost만 있는 담당자는 행이 없다"""
    # when: Lost 묶음만으로 요약을 만든다
    summary = ForecastSummary.build(COLUMNS, [_bucket(KIM, "lost", 2, 200)])

    # then: 행이 없다
    assert list(summary.rows) == []


def test_owner_with_only_won_has_row() -> None:
    """Won만 있는 담당자도 행이 있다"""
    # when: Won 묶음만으로 요약을 만든다
    summary = ForecastSummary.build(COLUMNS, [_bucket(KIM, "won", 1, 10)])

    # then: 행이 있고 Open 합계는 0이다
    assert [row.owner_id for row in summary.rows] == [KIM]
    assert summary.rows[0].open_total == Tally.ZERO


def test_unknown_key_bucket_is_ignored() -> None:
    """열에 없는 key의 묶음은 무시한다"""
    # when: 삭제된 코드 key의 묶음으로 요약을 만든다
    summary = ForecastSummary.build(COLUMNS, [_bucket(KIM, "deleted_code", 5, 500)])

    # then: 행이 없다
    assert list(summary.rows) == []


def test_buckets_of_the_same_owner_share_one_row() -> None:
    """같은 담당자의 묶음은 한 행을 쓴다"""
    # when: KIM 2개·LEE 1개 묶음으로 요약을 만든다
    summary = ForecastSummary.build(
        COLUMNS,
        [_bucket(KIM, "commit", 1, 1), _bucket(LEE, "commit", 2, 2), _bucket(KIM, "won", 1, 1)],
    )

    # then: 담당자별로 행이 하나씩이다
    owner_ids = [row.owner_id for row in summary.rows]
    assert None not in owner_ids
    assert sorted(i for i in owner_ids if i is not None) == sorted([KIM, LEE])


# ---- build: 합계 ----


def test_total_row_equals_sum_of_rows() -> None:
    """합계 행은 행의 합이다 (Lost 제외)"""
    # given: KIM·LEE의 여러 코드 묶음(Lost 포함)
    buckets = [
        _bucket(KIM, "pipeline", 2, 100),
        _bucket(KIM, "won", 1, 10),
        _bucket(LEE, "pipeline", 1, 5),
        _bucket(LEE, "commit", 3, 30),
        _bucket(LEE, "lost", 7, 700),
    ]

    # when: 요약을 만든다
    summary = ForecastSummary.build(COLUMNS, buckets)

    # then: 합계 행 셀·Open 합계가 행의 합이고 owner가 없다
    assert summary.total.owner_id is None
    assert summary.total.cells["pipeline"] == Tally(3, 105)
    assert summary.total.cells["commit"] == Tally(3, 30)
    assert summary.total.cells["won"] == Tally(1, 10)
    assert summary.total.cells["best"] == Tally.ZERO
    assert summary.total.open_total == Tally(6, 135)


def test_empty_buckets_give_no_rows_and_a_zero_total() -> None:
    """묶음이 없으면 행이 없고 합계는 0이다"""
    # when: 빈 묶음으로 요약을 만든다
    summary = ForecastSummary.build(COLUMNS, [])

    # then: 행이 없고 합계 셀이 모두 0이다
    assert list(summary.rows) == []
    assert summary.total.open_total == Tally.ZERO
    assert all(cell == Tally.ZERO for cell in summary.total.cells.values())


# ---- ordered ----


def test_rows_order_active_first_then_name_then_id() -> None:
    """행은 재직자 먼저, 이름, id 순으로 정렬한다"""
    # given: KIM(퇴사)·LEE·PARK(이름 같음) 묶음과 정렬 키
    buckets = [_bucket(owner, "commit", 1, 1) for owner in (KIM, LEE, PARK)]
    # 키 = (퇴사 여부, 이름, id): 재직자 먼저 → 이름 → id
    keys = {KIM: (True, "가나", 1), LEE: (False, "다라", 2), PARK: (False, "가나", 3)}

    # when: 정렬한다
    summary = ForecastSummary.build(COLUMNS, buckets).ordered(lambda owner: keys[owner])

    # then: 재직자인 PARK, LEE, 퇴사자 KIM 순이다
    assert [row.owner_id for row in summary.rows] == [PARK, LEE, KIM]


def test_ordering_keeps_the_total_row() -> None:
    """정렬해도 합계 행은 그대로다"""
    # given: KIM·LEE의 commit 묶음
    buckets = [_bucket(KIM, "commit", 1, 1), _bucket(LEE, "commit", 2, 2)]

    # when: 정렬한다
    summary = ForecastSummary.build(COLUMNS, buckets).ordered(lambda owner: (False, "x", owner))

    # then: 합계 행의 Open 합계는 (3, 3)이다
    assert summary.total.open_total == Tally(3, 3)
