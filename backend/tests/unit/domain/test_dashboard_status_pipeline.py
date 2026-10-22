"""StatusPipeline / StatusColumn (Dashboard AC-4): Status 코드를 order 순으로, 없으면 0으로.

Lost 제외 같은 조회 조건은 `DashboardCriteria`가, 묶음 계산은 저장소 계약이 맡는다.
여기서는 코드 목록과
tally 매핑을 합치는 규칙만 본다.
"""

from app.domain.code.values import CodeKind
from app.domain.dashboard.status_pipeline import StatusColumn, StatusPipeline
from app.domain.forecast.summary import Tally
from tests.fakes.catalog_seed import default_codes

STATUS_KEYS = [
    "prospecting",
    "introduction",
    "poc_preparation",
    "poc_completed",
    "technical_evaluation",
    "price_negotiation",
    "contract_completed",
]


def _columns() -> list[StatusColumn]:
    return StatusColumn.from_codes(default_codes())


def test_columns_from_codes_keep_only_status_codes_in_order() -> None:
    columns = _columns()

    assert [c.key for c in columns] == STATUS_KEYS
    assert [c.order for c in columns] == sorted(c.order for c in columns)


def test_columns_carry_the_code_name_for_display() -> None:
    names = {c.key: c.name for c in _columns()}

    assert names["prospecting"] == "기회발굴"
    assert names["contract_completed"] == "계약완료"


def test_columns_are_sorted_by_order_even_if_codes_arrive_shuffled() -> None:
    codes = [c for c in default_codes() if c.kind is CodeKind.STATUS]

    columns = StatusColumn.from_codes(reversed(codes))

    assert [c.key for c in columns] == STATUS_KEYS


def test_status_pipeline_lists_every_status_in_code_order() -> None:
    pipeline = StatusPipeline.build(_columns(), {"poc_completed": Tally(2, 50)})

    assert [item.column.key for item in pipeline.items] == STATUS_KEYS


def test_status_without_deals_is_zero() -> None:
    pipeline = StatusPipeline.build(_columns(), {"poc_completed": Tally(2, 50)})

    tallies = {item.column.key: item.tally for item in pipeline.items}
    assert tallies["poc_completed"] == Tally(2, 50)
    assert tallies["prospecting"] == Tally.ZERO
    assert tallies["contract_completed"] == Tally.ZERO


def test_unknown_status_key_is_ignored() -> None:
    pipeline = StatusPipeline.build(
        _columns(), {"prospecting": Tally(1, 10), "no_such_status": Tally(9, 999)}
    )

    assert len(pipeline.items) == len(STATUS_KEYS)
    assert pipeline.total == Tally(1, 10)


def test_status_total_is_sum_of_items() -> None:
    pipeline = StatusPipeline.build(
        _columns(),
        {
            "prospecting": Tally(18, 320),
            "poc_completed": Tally(4, 70),
            "contract_completed": Tally(1, 5),
        },
    )

    assert pipeline.total == Tally(23, 395)
    assert pipeline.total == sum_of(pipeline)


def test_pipeline_with_no_tallies_is_all_zero() -> None:
    pipeline = StatusPipeline.build(_columns(), {})

    assert all(item.tally == Tally.ZERO for item in pipeline.items)
    assert pipeline.total == Tally.ZERO


def test_an_added_open_status_code_gets_its_own_item() -> None:
    from app.domain.code.entities import Code  # noqa: PLC0415
    from app.domain.code.values import CodeId, CodeKey  # noqa: PLC0415
    from tests.factories import NOW  # noqa: PLC0415
    from tests.support.ids import new_id  # noqa: PLC0415

    extra = Code.create(
        entity_id=CodeId(new_id()),
        kind=CodeKind.STATUS,
        name="검토",
        key=CodeKey("review"),
        order=99,
        probability_hint=None,
        now=NOW,
    )

    columns = StatusColumn.from_codes([*default_codes(), extra])
    pipeline = StatusPipeline.build(columns, {"review": Tally(3, 30)})

    assert [i.column.key for i in pipeline.items][-1] == "review"
    assert pipeline.items[-1].tally == Tally(3, 30)


def sum_of(pipeline: StatusPipeline) -> Tally:
    total = Tally.ZERO
    for item in pipeline.items:
        total = total.add(item.tally)
    return total
