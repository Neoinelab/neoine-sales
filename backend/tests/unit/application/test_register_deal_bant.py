"""RegisterDeal의 BANT 저장 결과와 판정 순서(DE-R5 ⑬, DE-R10).

선택 해석 규칙 자체(`{id}`·`{name}` 대소문자·구분 일치·Label 이름 규칙)는 CL 소유 테스트
(`test_deal_bant_choice.py`)이고, 여기서는 Deal 등록이 그 결과를 어떻게 저장·롤백하는지만 본다.
"""

from typing import TYPE_CHECKING

from app.application.choice import CatalogChoice
from app.domain.bant.values import BantCategory
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import InvalidBantLabelError
from tests.factories_deal import SALES, make_create_input, make_draft
from tests.support.catalog import label_by_name
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv

BASELINE_LABELS = 23
LABEL_INVALID = "BANT Label이 올바르지 않습니다."
SYNC = "Status와 Forecast의 동기화가 맞지 않습니다."
PROCUREMENT = "구매절차는 500자 이내로 입력하세요."
EMAIL = "이메일 형식이 올바르지 않습니다."


async def _label_count(env: DealEnv) -> int:
    return len(await env.uow.bant_labels.list())


async def test_each_category_may_use_an_id_a_name_or_null_and_a_missing_one_is_not_selected(
    env: DealEnv,
) -> None:
    """구분마다 {id}·{name}·null을 섞어 보내면 각각 저장되고 빠진 구분은 선택 안 함이다.

    테스트 코드: DE-020
    """
    # given: 기본 시드 Label이 있다
    budget = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
    # when: Budget은 {id}, Authority는 새 {name}, Need는 null, Timeline은 생략하고 등록한다
    view = await env.new_deal(
        bant={
            BantCategory.BUDGET: CatalogChoice(id=budget.id),
            BantCategory.AUTHORITY: CatalogChoice(name="신규 결재선"),
            BantCategory.NEED: None,
        }
    )

    # then: Budget은 그 Label, Authority는 새로 만든 Label, Need·Timeline은 선택 안 함이다
    bant = view.item.deal.bant
    new_authority = await label_by_name(env.uow, BantCategory.AUTHORITY, "신규 결재선")
    assert bant.get(BantCategory.BUDGET) == budget.id
    assert bant.get(BantCategory.AUTHORITY) == new_authority.id
    assert bant.get(BantCategory.NEED) is None
    assert bant.get(BantCategory.TIMELINE) is None
    assert await _label_count(env) == BASELINE_LABELS + 1


async def test_a_registration_without_bant_selects_nothing(env: DealEnv) -> None:
    """bant를 생략한 등록은 네 구분 모두 선택 안 함이다.

    테스트 코드: DE-020
    """
    # when: bant 없이 등록한다
    view = await env.new_deal()

    # then: 네 구분이 모두 선택 안 함이고 Label은 늘지 않는다
    assert [view.item.deal.bant.get(category) for category in BantCategory] == [None] * 4
    assert await _label_count(env) == BASELINE_LABELS


async def test_a_failure_in_procurement_after_a_new_bant_name_leaves_no_label_or_deal(
    env: DealEnv,
) -> None:
    """BANT 뒤의 구매절차 검증에서 실패하면 새 Label도 Deal도 남지 않는다.

    테스트 코드: DE-021
    """
    # when: 새 BANT 이름과 501자 구매절차로 등록한다
    with raises_with(InvalidValueError, PROCUREMENT):
        await env.new_deal(
            bant={BantCategory.NEED: CatalogChoice(name="신규 필요")}, procurement="가" * 501
        )

    # then: 구매절차 오류이고 Label은 늘지 않았으며 Deal이 없다
    assert await _label_count(env) == BASELINE_LABELS
    assert env.uow.deals._items == {}


async def test_a_contact_format_error_after_a_new_bant_name_leaves_no_label_or_deal(
    env: DealEnv,
) -> None:
    """BANT 뒤의 연락처 형식 검증에서 실패하면 새 Label도 Deal도 남지 않는다.

    테스트 코드: DE-021
    """
    # when: 새 BANT 이름과 틀린 고객 이메일로 등록한다
    with raises_with(InvalidValueError, EMAIL):
        await env.new_deal(
            bant={BantCategory.NEED: CatalogChoice(name="신규 필요")},
            customer=make_draft(email="no-at-sign"),
        )

    # then: 이메일 오류이고 Label은 늘지 않았으며 Deal·연락처가 없다
    assert await _label_count(env) == BASELINE_LABELS
    assert env.uow.deals._items == {}
    assert env.uow.contacts._items == {}


async def test_bant_is_judged_after_the_status_forecast_sync(env: DealEnv) -> None:
    """동기화 위반과 BANT 위반이 함께 있으면 동기화 문구가 먼저 나온다.

    테스트 코드: DE-022
    """
    # given: 다른 구분의 Label id (BANT 위반)
    need = await label_by_name(env.uow, BantCategory.NEED, "모름")
    # when: 동기화 위반 + BANT 위반으로 등록한다
    with raises_with(InvalidValueError, SYNC):
        await env.register.execute(
            make_create_input(
                status_key="contract_completed",
                forecast_key="pipeline",
                bant={BantCategory.BUDGET: need.id},
            ),
            SALES,
        )
    # then: 동기화 문구가 나왔다 (위 with 블록)


async def test_bant_is_judged_before_the_procurement(env: DealEnv) -> None:
    """BANT 위반과 구매절차 위반이 함께 있으면 BANT 문구가 먼저 나온다.

    테스트 코드: DE-022
    """
    # given: 다른 구분의 Label id (BANT 위반)
    need = await label_by_name(env.uow, BantCategory.NEED, "모름")
    # when: BANT 위반 + 501자 구매절차로 등록한다
    with raises_with(InvalidBantLabelError, LABEL_INVALID):
        await env.register.execute(
            make_create_input(bant={BantCategory.BUDGET: need.id}, procurement="가" * 501),
            SALES,
        )
    # then: BANT 문구가 나왔다 (위 with 블록)
