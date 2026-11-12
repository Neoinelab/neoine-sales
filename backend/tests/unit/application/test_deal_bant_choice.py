"""Deal 등록·수정의 BANT 선택: 구분마다 {id}|{name}|None, 검증 뒤 같은 트랜잭션 생성.

`{id}`는 그 구분의 있는 Label을 가리키고, `{name}`은 같은 구분 안에서 대소문자 무시로 찾아 있으면 그
Label을, 없으면 요청자가 만든 새 Label을 쓴다. 검증이 하나라도 실패하면 새 Label도 남지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.choice import CatalogChoice
from app.domain.bant.values import BantCategory
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import InvalidBantLabelError
from tests.factories_deal import SALES, make_draft
from tests.support.catalog import label_by_name
from tests.support.expect import raises_with
from tests.support.ids import new_id

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv

LABEL_INVALID = "BANT Label이 올바르지 않습니다."
LABEL_REQUIRED = "Label 이름을 입력하세요."
LABEL_TOO_LONG = "Label 이름은 50자 이내로 입력하세요."
SYNC = "Status와 Forecast의 동기화가 맞지 않습니다."
PROCUREMENT = "구매절차는 500자 이내로 입력하세요."
BASELINE_LABELS = 23


async def _label_count(env: DealEnv) -> int:
    return len(await env.uow.bant_labels.list())


# --- {id} / None ---


async def test_bant_by_id_is_kept(env: DealEnv) -> None:
    """그 구분의 Label id를 고르면 그 Label이 쓰인다.

    테스트 코드: CL-071
    """
    # given: budget의 '풀 예산 확보'가 있다
    budget = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")

    # when: BANT budget을 {id}로 골라 Deal을 등록한다
    view = await env.new_deal(bant={BantCategory.BUDGET: CatalogChoice(id=budget.id)})

    # then: Deal은 그 Label을 가리키고 Label 수는 그대로다
    assert view.item.deal.bant.get(BantCategory.BUDGET) == budget.id
    assert await _label_count(env) == BASELINE_LABELS


async def test_bant_id_of_another_category_is_rejected_and_stores_nothing(env: DealEnv) -> None:
    """다른 구분의 Label id를 고르면 거절하고 Deal을 저장하지 않는다.

    테스트 코드: CL-072
    """
    # given: need의 '모름' Label이 있다
    need = await label_by_name(env.uow, BantCategory.NEED, "모름")

    # when: 그 id를 budget으로 골라 Deal을 등록한다
    with raises_with(InvalidBantLabelError, LABEL_INVALID):
        await env.new_deal(bant={BantCategory.BUDGET: CatalogChoice(id=need.id)})

    # then: 'BANT Label이 올바르지 않습니다.' 오류이고 Deal이 없다
    assert len(env.uow.deals._items) == 0


async def test_an_unknown_bant_id_is_rejected_without_creating_a_label(env: DealEnv) -> None:
    """없는 Label id를 고르면 거절하고 Label을 만들지 않는다.

    테스트 코드: CL-072
    """
    # when: 없는 id를 need로 골라 Deal을 등록한다
    with raises_with(InvalidBantLabelError, LABEL_INVALID):
        await env.new_deal(bant={BantCategory.NEED: CatalogChoice(id=new_id())})

    # then: 'BANT Label이 올바르지 않습니다.' 오류이고 Label은 23개 그대로다
    assert await _label_count(env) == BASELINE_LABELS


async def test_null_bant_category_means_not_selected(env: DealEnv) -> None:
    """BANT 구분에 null을 주면 선택하지 않은 것이다."""
    # when: null BANT로 Deal을 등록한다
    view = await env.new_deal(bant={BantCategory.BUDGET: None})

    # then: 구분이 비어 있고 Label은 늘지 않는다
    assert all(view.item.deal.bant.get(category) is None for category in BantCategory)
    assert await _label_count(env) == BASELINE_LABELS


# --- {name} ---


async def test_bant_name_reuses_label_in_same_category_ignoring_case(env: DealEnv) -> None:
    """같은 구분 Label과 대소문자만 다른 이름은 그 Label을 쓴다.

    테스트 코드: CL-073
    """
    # given: authority에 'CEO 보고 완료'가 있다
    existing = await label_by_name(env.uow, BantCategory.AUTHORITY, "CEO 보고 완료")

    # when: ' ceo 보고 완료 '로 골라 Deal을 등록한다
    view = await env.new_deal(bant={BantCategory.AUTHORITY: CatalogChoice(name=" ceo 보고 완료 ")})

    # then: 기존 Label을 가리키고 Label은 23개 그대로다
    assert view.item.deal.bant.get(BantCategory.AUTHORITY) == existing.id
    assert await _label_count(env) == BASELINE_LABELS


async def test_bant_name_creates_label_in_that_category_by_the_actor(env: DealEnv) -> None:
    """같은 구분에 없는 이름은 그 구분에 요청자가 만든 새 Label이 된다.

    테스트 코드: CL-074
    """
    # when: timeline에 '  분기 내 구매  '로 골라 Deal을 등록한다
    view = await env.new_deal(bant={BantCategory.TIMELINE: CatalogChoice(name="  분기 내 구매  ")})

    # then: 요청자가 만든 직접 만든 Label이 그 구분에 생긴다
    label_id = view.item.deal.bant.get(BantCategory.TIMELINE)
    created = await env.uow.bant_labels.get(label_id)  # type: ignore[arg-type]
    assert (created.category, created.name) == (BantCategory.TIMELINE, "분기 내 구매")
    assert created.is_default is False
    assert created.created_by_user_id == SALES.user_id
    assert created.created_at == env.clock.now()
    assert await _label_count(env) == BASELINE_LABELS + 1


async def test_a_new_label_name_gets_an_allocated_id(env: DealEnv) -> None:
    """새 Label은 새 정수 id를 받고 Deal이 그 id를 가리킨다.

    테스트 코드: CL-074
    """
    # when: budget·need에 새 이름을 골라 Deal을 등록한다
    view = await env.new_deal(
        bant={
            BantCategory.BUDGET: CatalogChoice(name="신규 예산"),
            BantCategory.NEED: CatalogChoice(name="신규 필요"),
        }
    )

    # then: 새 Label 둘의 id를 Deal이 가리킨다
    bant = view.item.deal.bant
    created = {x.name: x.id for x in await env.uow.bant_labels.list() if not x.is_default}
    assert sorted(created.values()) == [1, 2]  # 이 테이블에서 할당받은 번호(시드는 높은 번호)
    assert bant.get(BantCategory.BUDGET) == created["신규 예산"]
    assert bant.get(BantCategory.NEED) == created["신규 필요"]


async def test_same_name_in_another_category_creates_a_new_label(env: DealEnv) -> None:
    """다른 구분에만 있는 같은 이름은 쓰지 않고 이 구분에 새로 만든다.

    테스트 코드: CL-074
    """
    # when: budget에 '모름'을 골라 Deal을 등록한다
    view = await env.new_deal(bant={BantCategory.BUDGET: CatalogChoice(name="모름")})

    # then: budget에 새 Label이 생겨 그것을 가리키고 기존 '모름'은 그대로 둘이다
    label_id = view.item.deal.bant.get(BantCategory.BUDGET)
    created = await env.uow.bant_labels.get(label_id)  # type: ignore[arg-type]
    assert created.category is BantCategory.BUDGET
    others = {
        x.id for x in await env.uow.bant_labels.list() if x.name == "모름" and x.id != created.id
    }
    assert label_id not in others
    assert len(others) == 2
    assert await _label_count(env) == BASELINE_LABELS + 1


async def test_new_names_in_several_categories_create_one_label_each(env: DealEnv) -> None:
    """여러 구분에 새 이름을 보내면 구분마다 하나씩 만든다.

    테스트 코드: CL-074
    """
    # when: budget·need에 새 이름을 골라 Deal을 등록한다
    view = await env.new_deal(
        bant={
            BantCategory.BUDGET: CatalogChoice(name="신규 예산"),
            BantCategory.NEED: CatalogChoice(name="신규 필요"),
        }
    )

    # then: 구분마다 새 Label 하나씩 생긴다
    bant = view.item.deal.bant
    assert (await env.uow.bant_labels.get(bant.get(BantCategory.BUDGET))).name == "신규 예산"  # type: ignore[arg-type]
    assert (await env.uow.bant_labels.get(bant.get(BantCategory.NEED))).name == "신규 필요"  # type: ignore[arg-type]
    assert await _label_count(env) == BASELINE_LABELS + 2


async def test_a_created_label_is_reused_by_the_next_deal(env: DealEnv) -> None:
    """한 번 만든 Label 이름은 다음 선택에서 재사용된다.

    테스트 코드: CL-074
    """
    # given: 첫 Deal이 need에 새 이름 Label을 만들었다
    first = await env.new_deal(bant={BantCategory.NEED: CatalogChoice(name="신규 필요")})

    # when: 같은 이름으로 두 번째 Deal을 등록한다
    second = await env.new_deal(bant={BantCategory.NEED: CatalogChoice(name="신규 필요")})

    # then: 같은 Label을 가리키고 Label은 한 개만 늘었다
    assert second.item.deal.bant.get(BantCategory.NEED) == first.item.deal.bant.get(
        BantCategory.NEED
    )
    assert await _label_count(env) == BASELINE_LABELS + 1


@pytest.mark.parametrize(
    ("name", "message"),
    [("   ", LABEL_REQUIRED), ("", LABEL_REQUIRED), ("가" * 51, LABEL_TOO_LONG)],
    ids=["blank", "empty", "51-chars"],
)
async def test_blank_or_long_bant_name_is_rejected_with_label_messages(
    env: DealEnv, name: str, message: str
) -> None:
    """이름으로 고른 BANT도 공백뿐·빈 이름·51자는 Label 문구로 거절한다.

    테스트 코드: CL-075
    """
    # when: 유효하지 않은 이름으로 골라 Deal을 등록한다
    with raises_with(InvalidValueError, message):
        await env.new_deal(bant={BantCategory.NEED: CatalogChoice(name=name)})

    # then: 필수·길이 문구 오류이고 Label은 23개 그대로다
    assert await _label_count(env) == BASELINE_LABELS


async def test_a_50_code_point_bant_name_is_accepted(env: DealEnv) -> None:
    """이름으로 고른 BANT는 이모지 50개(50 코드 포인트)까지 허용된다.

    테스트 코드: CL-075
    """
    # when: 이모지 50개 이름으로 Deal을 등록한다
    view = await env.new_deal(bant={BantCategory.NEED: CatalogChoice(name="😀" * 50)})

    # then: 그 이름의 Label이 만들어진다
    label = await env.uow.bant_labels.get(view.item.deal.bant.get(BantCategory.NEED))  # type: ignore[arg-type]
    assert label.name == "😀" * 50


async def test_nul_in_a_bant_name_is_rejected(env: DealEnv) -> None:
    """NUL 문자가 든 BANT 이름은 거절하고 Label을 만들지 않는다.

    테스트 코드: CL-075
    """
    # when: NUL이 든 이름으로 Deal을 등록한다
    with pytest.raises(InvalidValueError, match="NUL"):
        await env.new_deal(bant={BantCategory.NEED: CatalogChoice(name="신\x00규")})

    # then: NUL 오류이고 Label은 23개 그대로다
    assert await _label_count(env) == BASELINE_LABELS


async def test_bant_is_validated_after_sync_and_before_procurement(env: DealEnv) -> None:
    """BANT 검증은 동기화 검증 뒤, 구매 방식 검증 앞에 일어난다."""
    # given: 이름이 공백뿐인 BANT 선택
    bad_bant = {BantCategory.NEED: CatalogChoice(name="   ")}

    # when·then: 동기화도 틀린 채 등록한다 → BANT 오류가 아니라 동기화 오류가 먼저 난다
    with raises_with(InvalidValueError, SYNC):
        await env.new_deal(bant=bad_bant, status_key="contract_completed", forecast_key="pipeline")
    # when·then: 구매 방식도 틀린 채 등록한다 → 구매 방식 오류가 아니라 BANT 오류가 먼저 난다
    with raises_with(InvalidValueError, LABEL_REQUIRED):
        await env.new_deal(bant=bad_bant, procurement="가" * 501)


# --- 이후 검증이 실패하면 새 Label도 없다 ---


async def test_later_validation_failure_creates_no_label(env: DealEnv) -> None:
    """뒤쪽 검증이 실패하면 새 Label도 만들어지지 않는다."""
    # when: 새 Label 이름과 너무 긴 구매 방식으로 등록한다
    with raises_with(InvalidValueError, PROCUREMENT):
        await env.new_deal(
            bant={BantCategory.NEED: CatalogChoice(name="신규 필요")}, procurement="가" * 501
        )

    # then: 구매 방식 오류이고 Label과 Deal이 늘지 않는다
    assert await _label_count(env) == BASELINE_LABELS
    assert len(env.uow.deals._items) == 0


async def test_contact_failure_after_bant_creates_no_label(env: DealEnv) -> None:
    """연락처 검증이 실패하면 새 BANT Label도 만들어지지 않는다."""
    # when: 새 Label 이름과 틀린 이메일로 등록한다
    with raises_with(InvalidValueError, "이메일 형식이 올바르지 않습니다."):
        await env.new_deal(
            bant={BantCategory.NEED: CatalogChoice(name="신규 필요")},
            customer=make_draft(email="bad"),
        )

    # then: 이메일 오류이고 Label이 늘지 않는다
    assert await _label_count(env) == BASELINE_LABELS


async def test_a_failed_registration_leaves_the_catalog_in_the_state_before_the_call(
    env: DealEnv,
) -> None:
    """등록이 실패하면 카탈로그는 호출 전 상태 그대로다."""
    # given: 호출 전 BANT Label 목록
    before = {x.id: x.name for x in await env.uow.bant_labels.list()}

    # when: 새 Label 둘과 잘못된 사용자 수로 등록한다
    with pytest.raises(InvalidValueError):
        await env.new_deal(
            bant={
                BantCategory.BUDGET: CatalogChoice(name="신규 예산"),
                BantCategory.NEED: CatalogChoice(name="신규 필요"),
            },
            users=-1,
        )

    # then: 입력값 오류이고 카탈로그가 호출 전과 같다
    assert {x.id: x.name for x in await env.uow.bant_labels.list()} == before
