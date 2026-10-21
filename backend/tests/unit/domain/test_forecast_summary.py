"""ForecastSummary.build / ForecastColumn.from_codes / ordered (P6 R1 AC-2·3·4·5).

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
    assert Tally(2, 100).add(Tally(3, 50)) == Tally(5, 150)


def test_tally_zero_is_the_identity() -> None:
    assert Tally(0, 0) == Tally.ZERO
    assert Tally(4, 9).add(Tally.ZERO) == Tally(4, 9)


# ---- from_codes ----


def test_columns_from_default_codes_are_in_order_without_lost() -> None:
    codes = [c for c in default_codes() if c.kind is CodeKind.FORECAST]

    columns = ForecastColumn.from_codes(codes)

    assert [c.key for c in columns] == ["pipeline", "best", "most_likely", "commit", "won"]
    assert [c.outcome for c in columns][-1] is ForecastOutcome.WON
    assert [c.order for c in columns] == sorted(c.order for c in columns)


def test_columns_carry_the_code_name_for_display() -> None:
    codes = [c for c in default_codes() if c.kind is CodeKind.FORECAST]

    columns = ForecastColumn.from_codes(codes)

    assert {c.key: c.name for c in columns}["most_likely"] == "Most Likely"


# ---- build: 열 ----


def test_lost_column_is_excluded_from_columns() -> None:
    summary = ForecastSummary.build(COLUMNS, [])

    assert [c.key for c in summary.columns] == ["pipeline", "best", "commit", "won"]


def test_custom_open_code_becomes_column() -> None:
    extra = ForecastColumn("verbal", "Verbal", ForecastOutcome.OPEN, 3)

    summary = ForecastSummary.build([PIPELINE, extra, WON], [_bucket(KIM, "verbal", 1, 70)])

    assert [c.key for c in summary.columns] == ["pipeline", "verbal", "won"]
    assert summary.rows[0].cells["verbal"] == Tally(1, 70)
    assert summary.rows[0].open_total == Tally(1, 70)


# ---- build: 행·셀 ----


def test_missing_cells_are_zero() -> None:
    summary = ForecastSummary.build(COLUMNS, [_bucket(KIM, "commit", 1, 100)])

    cells = summary.rows[0].cells
    assert set(cells) == {"pipeline", "best", "commit", "won"}
    assert cells["pipeline"] == Tally.ZERO
    assert cells["won"] == Tally.ZERO
    assert cells["commit"] == Tally(1, 100)


def test_open_total_sums_only_open_cells() -> None:
    buckets = [
        _bucket(KIM, "pipeline", 2, 100),
        _bucket(KIM, "commit", 1, 50),
        _bucket(KIM, "best", 3, 30),
    ]

    summary = ForecastSummary.build(COLUMNS, buckets)

    assert summary.rows[0].open_total == Tally(6, 180)


def test_won_is_not_in_open_total() -> None:
    summary = ForecastSummary.build(
        COLUMNS, [_bucket(KIM, "commit", 1, 50), _bucket(KIM, "won", 4, 400)]
    )

    row = summary.rows[0]
    assert row.open_total == Tally(1, 50)
    assert row.cells["won"] == Tally(4, 400)


def test_lost_bucket_is_ignored() -> None:
    summary = ForecastSummary.build(
        COLUMNS, [_bucket(KIM, "commit", 1, 50), _bucket(KIM, "lost", 9, 900)]
    )

    assert summary.rows[0].open_total == Tally(1, 50)
    assert "lost" not in summary.rows[0].cells
    assert "lost" not in summary.total.cells
    assert summary.total.open_total == Tally(1, 50)


def test_owner_with_only_lost_has_no_row() -> None:
    summary = ForecastSummary.build(COLUMNS, [_bucket(KIM, "lost", 2, 200)])

    assert list(summary.rows) == []


def test_owner_with_only_won_has_row() -> None:
    summary = ForecastSummary.build(COLUMNS, [_bucket(KIM, "won", 1, 10)])

    assert [row.owner_id for row in summary.rows] == [KIM]
    assert summary.rows[0].open_total == Tally.ZERO


def test_unknown_key_bucket_is_ignored() -> None:
    summary = ForecastSummary.build(COLUMNS, [_bucket(KIM, "deleted_code", 5, 500)])

    assert list(summary.rows) == []


def test_buckets_of_the_same_owner_share_one_row() -> None:
    summary = ForecastSummary.build(
        COLUMNS,
        [_bucket(KIM, "commit", 1, 1), _bucket(LEE, "commit", 2, 2), _bucket(KIM, "won", 1, 1)],
    )

    owner_ids = [row.owner_id for row in summary.rows]
    assert None not in owner_ids
    assert sorted(i for i in owner_ids if i is not None) == sorted([KIM, LEE])


# ---- build: 합계 ----


def test_total_row_equals_sum_of_rows() -> None:
    buckets = [
        _bucket(KIM, "pipeline", 2, 100),
        _bucket(KIM, "won", 1, 10),
        _bucket(LEE, "pipeline", 1, 5),
        _bucket(LEE, "commit", 3, 30),
        _bucket(LEE, "lost", 7, 700),
    ]

    summary = ForecastSummary.build(COLUMNS, buckets)

    assert summary.total.owner_id is None
    assert summary.total.cells["pipeline"] == Tally(3, 105)
    assert summary.total.cells["commit"] == Tally(3, 30)
    assert summary.total.cells["won"] == Tally(1, 10)
    assert summary.total.cells["best"] == Tally.ZERO
    assert summary.total.open_total == Tally(6, 135)


def test_empty_buckets_give_no_rows_and_a_zero_total() -> None:
    summary = ForecastSummary.build(COLUMNS, [])

    assert list(summary.rows) == []
    assert summary.total.open_total == Tally.ZERO
    assert all(cell == Tally.ZERO for cell in summary.total.cells.values())


# ---- ordered ----


def test_rows_order_active_first_then_name_then_id() -> None:
    buckets = [_bucket(owner, "commit", 1, 1) for owner in (KIM, LEE, PARK)]
    # 키 = (퇴사 여부, 이름, id): 재직자 먼저 → 이름 → id
    keys = {KIM: (True, "가나", 1), LEE: (False, "다라", 2), PARK: (False, "가나", 3)}

    summary = ForecastSummary.build(COLUMNS, buckets).ordered(lambda owner: keys[owner])

    assert [row.owner_id for row in summary.rows] == [PARK, LEE, KIM]


def test_ordering_keeps_the_total_row() -> None:
    buckets = [_bucket(KIM, "commit", 1, 1), _bucket(LEE, "commit", 2, 2)]

    summary = ForecastSummary.build(COLUMNS, buckets).ordered(lambda owner: (False, "x", owner))

    assert summary.total.open_total == Tally(3, 3)
