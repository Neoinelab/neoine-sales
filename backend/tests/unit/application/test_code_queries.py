"""코드 조회 유스케이스: 전체 조회(CD-001~003)와 종류별 사용 수(CD-004~007)."""

from typing import TYPE_CHECKING

import pytest

from app.application.code.list_code_set import ListCodeSet
from app.application.code.list_codes_with_usage import ListCodesWithUsage
from app.domain.code.values import CodeKind
from tests.fakes.catalog_seed import DEFAULT_FORECASTS, DEFAULT_STATUSES, EN_DASH
from tests.support.catalog import add_deals_with_status

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork

STATUS_KEYS = [key for key, _ in DEFAULT_STATUSES]
FORECAST_KEYS = [key for key, *_ in DEFAULT_FORECASTS]
STATUS_LOCKED = {"prospecting", "contract_completed"}
FORECAST_LOCKED = {"pipeline", "won", "lost"}


async def test_list_code_set_returns_statuses_and_forecasts_in_order(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """기본 Status 7개·Forecast 6개를 이름·순서·잠금·결과·힌트와 함께 순서대로 돌려준다.

    테스트 코드: CD-001
    """
    # when: 코드 목록을 읽는다 (전제: 기본 코드만 있는 시스템(seeded))
    result = await ListCodeSet(uow_factory).execute()

    # then: 7개·6개가 기본 순서이고 각 줄의 값이 기본 코드 정의와 같다
    assert [c.key.value for c in result.statuses] == STATUS_KEYS
    assert [c.key.value for c in result.forecasts] == FORECAST_KEYS
    assert [c.order for c in result.statuses] == list(range(1, 8))
    assert [c.order for c in result.forecasts] == list(range(1, 7))
    assert [(c.key.value, c.name) for c in result.statuses] == list(DEFAULT_STATUSES)
    assert all(c.outcome.value == "open" and c.probability_hint is None for c in result.statuses)
    assert [c.locked for c in result.statuses] == [True, False, False, False, False, False, True]
    assert [
        (c.key.value, c.name, c.outcome.value, c.probability_hint, c.locked)
        for c in result.forecasts
    ] == [
        ("pipeline", "Pipeline", "open", f"0{EN_DASH}50", True),
        ("best", "Best", "open", f"51{EN_DASH}75", False),
        ("most_likely", "Most Likely", "open", f"75{EN_DASH}85", False),
        ("commit", "Commit", "open", f"85{EN_DASH}100", False),
        ("won", "Won", "won", None, True),
        ("lost", "Lost", "lost", None, True),
    ]
    assert "lost" not in [c.key.value for c in result.statuses]


async def test_list_code_set_follows_a_changed_order(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """순서를 바꾼 코드는 조회 결과에서도 그 순서를 따른다.

    테스트 코드: CD-002
    """
    # given: 첫 Status의 order를 99로 바꿔 둔다
    first = (await seeded.codes.list(CodeKind.STATUS))[0]
    first.place(99, first.updated_at)
    await seeded.codes.update(first)

    # when: 코드 목록을 읽는다
    result = await ListCodeSet(uow_factory).execute()

    # then: 그 Status가 statuses의 맨 끝이다
    assert [c.key.value for c in result.statuses][-1] == first.key.value


async def test_locked_is_true_only_for_the_five_system_keys(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """잠금은 정해진 다섯 key에만 있다.

    테스트 코드: CD-003
    """
    # when: 코드 목록을 읽는다 (전제: 기본 코드만 있는 시스템(seeded))
    result = await ListCodeSet(uow_factory).execute()

    # then: Status prospecting·contract_completed, Forecast pipeline·won·lost만 잠겨 있다
    assert {c.key.value for c in result.statuses if c.locked} == STATUS_LOCKED
    assert {c.key.value for c in result.forecasts if c.locked} == FORECAST_LOCKED


async def test_list_codes_with_usage_is_zero_when_no_deal_exists(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """Deal이 없으면 Status 사용 수는 모두 0이다.

    테스트 코드: CD-004
    """
    # when: Status 사용 현황을 읽는다 (전제: Deal이 하나도 없다(seeded))
    usage = await ListCodesWithUsage(uow_factory).execute(CodeKind.STATUS)

    # then: 7개 모두 0이고 순서는 기본 순서다
    assert [u.code.key.value for u in usage] == STATUS_KEYS
    assert [u.usage_count for u in usage] == [0] * 7


async def test_list_codes_with_usage_counts_deals_by_status(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """Status 사용 수는 그 Status를 쓰는 Deal 수다.

    테스트 코드: CD-004
    """
    # given: Status 기회발굴 Deal 2건, 제품소개 Deal 1건
    await add_deals_with_status(seeded, "prospecting", 2)
    await add_deals_with_status(seeded, "introduction", 1)

    # when: Status 사용 현황을 읽는다
    usage = await ListCodesWithUsage(uow_factory).execute(CodeKind.STATUS)

    # then: prospecting 2, introduction 1, 나머지 0이고 기본 순서다
    assert [u.code.key.value for u in usage] == STATUS_KEYS
    assert {u.code.key.value: u.usage_count for u in usage} == {
        key: {"prospecting": 2, "introduction": 1}.get(key, 0) for key in STATUS_KEYS
    }


async def test_list_codes_with_usage_for_forecast_uses_the_forecast_counts(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """Forecast 사용 수는 그 Forecast를 쓰는 Deal 수다.

    테스트 코드: CD-005
    """
    # given: Forecast Best Deal 2건, Commit Deal 1건
    seeded.deals.forecast_counts = {"best": 2, "commit": 1}

    # when: Forecast 사용 현황을 읽는다
    usage = await ListCodesWithUsage(uow_factory).execute(CodeKind.FORECAST)

    # then: best 2, commit 1, 나머지 0이다
    assert [u.code.key.value for u in usage] == FORECAST_KEYS
    assert {u.code.key.value: u.usage_count for u in usage} == {
        key: {"best": 2, "commit": 1}.get(key, 0) for key in FORECAST_KEYS
    }


@pytest.mark.parametrize(
    ("kind", "keys"),
    [(CodeKind.FORECAST, FORECAST_KEYS), (CodeKind.STATUS, STATUS_KEYS)],
)
async def test_list_codes_with_usage_returns_only_the_requested_kind(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, kind: CodeKind, keys: list[str]
) -> None:
    """사용 현황은 요청한 종류의 코드만 기본 순서대로 돌려준다.

    테스트 코드: CD-006
    """
    # when: 한 종류로 사용 현황을 읽는다 (전제: 기본 코드(seeded))
    usage = await ListCodesWithUsage(uow_factory).execute(kind)

    # then: 모든 항목이 그 종류이고 기본 순서다
    assert {u.code.kind for u in usage} == {kind}
    assert [u.code.key.value for u in usage] == keys
