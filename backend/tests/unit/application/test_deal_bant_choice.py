"""Deal 등록·수정의 BANT 선택(AC-17~22): 구분마다 {id}|{name}|None, 검증 뒤 같은 트랜잭션 생성.

`{id}`는 그 구분의 있는 Label을 가리키고, `{name}`은 같은 구분 안에서 대소문자 무시로 찾아 있으면 그
Label을, 없으면 요청자가 만든 새 Label을 쓴다. 검증이 하나라도 실패하면 새 Label도 남지 않는다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.choice import CatalogChoice
from app.domain.bant.values import BantCategory
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import InvalidBantLabelError
from tests.factories_deal import SALES, make_draft
from tests.support.catalog import label_by_name
from tests.support.expect import raises_with

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


# --- {id} / None (AC-17·18) ---


async def test_bant_by_id_is_kept(env: DealEnv) -> None:
    budget = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")

    view = await env.new_deal(bant={BantCategory.BUDGET: CatalogChoice(id=budget.id)})

    assert view.item.deal.bant.get(BantCategory.BUDGET) == budget.id
    assert await _label_count(env) == BASELINE_LABELS


async def test_bant_id_of_another_category_is_rejected_and_stores_nothing(env: DealEnv) -> None:
    need = await label_by_name(env.uow, BantCategory.NEED, "모름")

    with raises_with(InvalidBantLabelError, LABEL_INVALID):
        await env.new_deal(bant={BantCategory.BUDGET: CatalogChoice(id=need.id)})

    assert len(env.uow.deals._items) == 0


async def test_an_unknown_bant_id_is_rejected_without_creating_a_label(env: DealEnv) -> None:
    with raises_with(InvalidBantLabelError, LABEL_INVALID):
        await env.new_deal(bant={BantCategory.NEED: CatalogChoice(id=uuid4())})

    assert await _label_count(env) == BASELINE_LABELS


async def test_null_bant_category_means_not_selected(env: DealEnv) -> None:
    view = await env.new_deal(bant={BantCategory.BUDGET: None})

    assert all(view.item.deal.bant.get(category) is None for category in BantCategory)
    assert await _label_count(env) == BASELINE_LABELS


# --- {name} (AC-19·20) ---


async def test_bant_name_reuses_label_in_same_category_ignoring_case(env: DealEnv) -> None:
    existing = await label_by_name(env.uow, BantCategory.AUTHORITY, "CEO 보고 완료")

    view = await env.new_deal(bant={BantCategory.AUTHORITY: CatalogChoice(name=" ceo 보고 완료 ")})

    assert view.item.deal.bant.get(BantCategory.AUTHORITY) == existing.id
    assert await _label_count(env) == BASELINE_LABELS


async def test_bant_name_creates_label_in_that_category_by_the_actor(env: DealEnv) -> None:
    view = await env.new_deal(bant={BantCategory.TIMELINE: CatalogChoice(name="  분기 내 구매  ")})

    label_id = view.item.deal.bant.get(BantCategory.TIMELINE)
    created = await env.uow.bant_labels.get(label_id)  # type: ignore[arg-type]
    assert (created.category, created.name) == (BantCategory.TIMELINE, "분기 내 구매")
    assert created.is_default is False
    assert created.created_by_user_id == SALES.user_id
    assert created.created_at == env.clock.now()
    assert await _label_count(env) == BASELINE_LABELS + 1


async def test_same_name_in_another_category_creates_a_new_label(env: DealEnv) -> None:
    """'모름'은 authority·need에는 있고 budget에는 없다: budget에 새로 만든다."""
    view = await env.new_deal(bant={BantCategory.BUDGET: CatalogChoice(name="모름")})

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
    view = await env.new_deal(
        bant={
            BantCategory.BUDGET: CatalogChoice(name="신규 예산"),
            BantCategory.NEED: CatalogChoice(name="신규 필요"),
        }
    )

    bant = view.item.deal.bant
    assert (await env.uow.bant_labels.get(bant.get(BantCategory.BUDGET))).name == "신규 예산"  # type: ignore[arg-type]
    assert (await env.uow.bant_labels.get(bant.get(BantCategory.NEED))).name == "신규 필요"  # type: ignore[arg-type]
    assert await _label_count(env) == BASELINE_LABELS + 2


async def test_a_created_label_is_reused_by_the_next_deal(env: DealEnv) -> None:
    first = await env.new_deal(bant={BantCategory.NEED: CatalogChoice(name="신규 필요")})

    second = await env.new_deal(bant={BantCategory.NEED: CatalogChoice(name="신규 필요")})

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
    with raises_with(InvalidValueError, message):
        await env.new_deal(bant={BantCategory.NEED: CatalogChoice(name=name)})

    assert await _label_count(env) == BASELINE_LABELS


async def test_a_50_code_point_bant_name_is_accepted(env: DealEnv) -> None:
    view = await env.new_deal(bant={BantCategory.NEED: CatalogChoice(name="😀" * 50)})

    label = await env.uow.bant_labels.get(view.item.deal.bant.get(BantCategory.NEED))  # type: ignore[arg-type]
    assert label.name == "😀" * 50


async def test_nul_in_a_bant_name_is_rejected(env: DealEnv) -> None:
    with pytest.raises(InvalidValueError, match="NUL"):
        await env.new_deal(bant={BantCategory.NEED: CatalogChoice(name="신\x00규")})

    assert await _label_count(env) == BASELINE_LABELS


async def test_bant_is_validated_after_sync_and_before_procurement(env: DealEnv) -> None:
    bad_bant = {BantCategory.NEED: CatalogChoice(name="   ")}

    with raises_with(InvalidValueError, SYNC):
        await env.new_deal(bant=bad_bant, status_key="contract_completed", forecast_key="pipeline")
    with raises_with(InvalidValueError, LABEL_REQUIRED):
        await env.new_deal(bant=bad_bant, procurement="가" * 501)


# --- 이후 검증이 실패하면 새 Label도 없다 (AC-21) ---


async def test_later_validation_failure_creates_no_label(env: DealEnv) -> None:
    with raises_with(InvalidValueError, PROCUREMENT):
        await env.new_deal(
            bant={BantCategory.NEED: CatalogChoice(name="신규 필요")}, procurement="가" * 501
        )

    assert await _label_count(env) == BASELINE_LABELS
    assert len(env.uow.deals._items) == 0


async def test_contact_failure_after_bant_creates_no_label(env: DealEnv) -> None:
    with raises_with(InvalidValueError, "이메일 형식이 올바르지 않습니다."):
        await env.new_deal(
            bant={BantCategory.NEED: CatalogChoice(name="신규 필요")},
            customer=make_draft(email="bad"),
        )

    assert await _label_count(env) == BASELINE_LABELS


async def test_a_failed_registration_leaves_the_catalog_in_the_state_before_the_call(
    env: DealEnv,
) -> None:
    before = {x.id: x.name for x in await env.uow.bant_labels.list()}

    with pytest.raises(InvalidValueError):
        await env.new_deal(
            bant={
                BantCategory.BUDGET: CatalogChoice(name="신규 예산"),
                BantCategory.NEED: CatalogChoice(name="신규 필요"),
            },
            users=-1,
        )

    assert {x.id: x.name for x in await env.uow.bant_labels.list()} == before
