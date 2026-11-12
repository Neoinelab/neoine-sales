"""StatusPipeline / StatusColumn: Status 코드를 order 순으로, 없으면 0으로.

Lost 제외 같은 조회 조건은 `DashboardCriteria`가, 묶음 계산은 저장소 계약이 맡는다.
여기서는 코드 목록과 tally 매핑을 합치는 규칙만 본다.
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
    """Status 열은 Status 코드만 order 순서로 담는다.

    테스트 코드: DSH-010
    """
    # when: 기본 코드(Status·Forecast 섞임)로 열을 만든다
    columns = _columns()

    # then: Status 코드 7개만 order 순이다
    assert [c.key for c in columns] == STATUS_KEYS
    assert [c.order for c in columns] == sorted(c.order for c in columns)


def test_columns_carry_the_code_name_for_display() -> None:
    """열은 화면에 보일 코드 이름을 가진다.

    테스트 코드: DSH-010
    """
    # when: 기본 코드로 열을 만든다
    names = {c.key: c.name for c in _columns()}

    # then: 이름이 코드 이름이다
    assert names["prospecting"] == "기회발굴"
    assert names["contract_completed"] == "계약완료"


def test_columns_are_sorted_by_order_even_if_codes_arrive_shuffled() -> None:
    """코드가 뒤섞여 들어와도 열은 order 순이다.

    테스트 코드: DSH-010
    """
    # given: 역순으로 뒤집은 Status 코드
    codes = [c for c in default_codes() if c.kind is CodeKind.STATUS]

    # when: 열을 만든다
    columns = StatusColumn.from_codes(reversed(codes))

    # then: order 순이다
    assert [c.key for c in columns] == STATUS_KEYS


def test_status_pipeline_lists_every_status_in_code_order() -> None:
    """파이프라인은 모든 Status를 코드 순서로 나열한다.

    테스트 코드: DSH-010
    """
    # when: 한 Status의 집계만으로 파이프라인을 만든다
    pipeline = StatusPipeline.build(_columns(), {"poc_completed": Tally(2, 50)})

    # then: 모든 Status가 코드 순서로 있다
    assert [item.column.key for item in pipeline.items] == STATUS_KEYS


def test_status_without_deals_is_zero() -> None:
    """Deal이 없는 Status는 0이다.

    테스트 코드: DSH-010
    """
    # when: 한 Status의 집계만으로 파이프라인을 만든다
    pipeline = StatusPipeline.build(_columns(), {"poc_completed": Tally(2, 50)})

    # then: 집계가 있는 Status만 값이 있고 나머지는 0이다
    tallies = {item.column.key: item.tally for item in pipeline.items}
    assert tallies["poc_completed"] == Tally(2, 50)
    assert tallies["prospecting"] == Tally.ZERO
    assert tallies["contract_completed"] == Tally.ZERO


def test_unknown_status_key_is_ignored() -> None:
    """모르는 Status key의 집계는 무시한다.

    BDD 밖: 저장소가 코드에 없는 key를 돌려줘도 합계가 어긋나지 않는지 확인한다.
    """
    # when: 모르는 key가 섞인 집계로 파이프라인을 만든다
    pipeline = StatusPipeline.build(
        _columns(), {"prospecting": Tally(1, 10), "no_such_status": Tally(9, 999)}
    )

    # then: 항목 수는 그대로이고 합계에 모르는 key가 들지 않는다
    assert len(pipeline.items) == len(STATUS_KEYS)
    assert pipeline.total == Tally(1, 10)


def test_status_total_is_sum_of_items() -> None:
    """Status 합계는 항목 합계다.

    테스트 코드: DSH-011
    """
    # when: 세 Status의 집계로 파이프라인을 만든다
    pipeline = StatusPipeline.build(
        _columns(),
        {
            "prospecting": Tally(18, 320),
            "poc_completed": Tally(4, 70),
            "contract_completed": Tally(1, 5),
        },
    )

    # then: 합계는 항목을 더한 값이다
    assert pipeline.total == Tally(23, 395)
    assert pipeline.total == sum_of(pipeline)


def test_pipeline_with_no_tallies_is_all_zero() -> None:
    """집계가 없으면 모든 항목과 합계가 0이다.

    테스트 코드: DSH-021
    """
    # when: 빈 집계로 파이프라인을 만든다
    pipeline = StatusPipeline.build(_columns(), {})

    # then: 모두 0이다
    assert all(item.tally == Tally.ZERO for item in pipeline.items)
    assert pipeline.total == Tally.ZERO


def test_an_added_open_status_code_gets_its_own_item() -> None:
    """admin이 추가한 Status 코드도 자기 항목을 가진다.

    BDD 밖: 코드 추가(CD)가 Dashboard 열에 반영되는지 확인한다.
    """
    # given: 순서 99의 새 Status 코드 "검토"
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

    # when: 새 코드를 포함해 파이프라인을 만든다
    columns = StatusColumn.from_codes([*default_codes(), extra])
    pipeline = StatusPipeline.build(columns, {"review": Tally(3, 30)})

    # then: 마지막 항목이 검토이고 값이 있다
    assert [i.column.key for i in pipeline.items][-1] == "review"
    assert pipeline.items[-1].tally == Tally(3, 30)


def sum_of(pipeline: StatusPipeline) -> Tally:
    total = Tally.ZERO
    for item in pipeline.items:
        total = total.add(item.tally)
    return total
