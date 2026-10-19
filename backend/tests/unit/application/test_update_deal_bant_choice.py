"""Deal 수정(PATCH)의 BANT 선택(AC-17~22): {id}|{name}|None, 바뀐 구분만 History.

등록의 BANT 규칙은 test_deal_bant_choice.py. 수정에서 새 Label은 검증을 모두 통과한 뒤 만들고,
History에는 새 Label의 이름이 표기된다. 수정이 실패하면 새 Label도 남지 않는다.
"""

from typing import TYPE_CHECKING

from app.application.choice import CatalogChoice

from app.domain.bant.values import BantCategory
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import InvalidBantLabelError
from tests.factories_deal import SALES, make_patch
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


# --- 수정 (AC-17~22) ---


async def test_patch_bant_name_records_history_with_new_label_name(env: DealEnv) -> None:
    view = await env.new_deal()

    updated = await env.update.execute(
        view.item.deal.id.value,
        make_patch(bant={BantCategory.BUDGET: CatalogChoice(name="신규 예산")}),
        SALES,
    )

    assert await env.changes(updated) == [("bant", "BANT Label: Budget", "선택 안 함", "신규 예산")]
    assert await _label_count(env) == BASELINE_LABELS + 1


async def test_patch_bant_name_of_an_existing_label_reuses_it(env: DealEnv) -> None:
    existing = await label_by_name(env.uow, BantCategory.TIMELINE, "금년 구매")
    view = await env.new_deal()

    updated = await env.update.execute(
        view.item.deal.id.value,
        make_patch(bant={BantCategory.TIMELINE: CatalogChoice(name="금년 구매")}),
        SALES,
    )

    assert updated.item.deal.bant.get(BantCategory.TIMELINE) == existing.id
    assert await _label_count(env) == BASELINE_LABELS


async def test_unchanged_bant_records_nothing(env: DealEnv) -> None:
    ceo = await label_by_name(env.uow, BantCategory.AUTHORITY, "CEO 보고 완료")
    view = await env.new_deal(bant={BantCategory.AUTHORITY: CatalogChoice(id=ceo.id)})

    same_by_id = await env.update.execute(
        view.item.deal.id.value,
        make_patch(bant={BantCategory.AUTHORITY: CatalogChoice(id=ceo.id)}),
        SALES,
    )
    same_by_name = await env.update.execute(
        view.item.deal.id.value,
        make_patch(bant={BantCategory.AUTHORITY: CatalogChoice(name="ceo 보고 완료")}),
        SALES,
    )

    assert await env.changes(same_by_id) == []
    assert await env.changes(same_by_name) == []
    assert await _label_count(env) == BASELINE_LABELS


async def test_only_the_changed_category_is_logged(env: DealEnv) -> None:
    ceo = await label_by_name(env.uow, BantCategory.AUTHORITY, "CEO 보고 완료")
    view = await env.new_deal(bant={BantCategory.AUTHORITY: CatalogChoice(id=ceo.id)})

    updated = await env.update.execute(
        view.item.deal.id.value,
        make_patch(
            bant={
                BantCategory.AUTHORITY: CatalogChoice(id=ceo.id),
                BantCategory.NEED: CatalogChoice(name="신규 필요"),
            }
        ),
        SALES,
    )

    assert await env.changes(updated) == [("bant", "BANT Label: Need", "선택 안 함", "신규 필요")]


async def test_patch_with_null_clears_the_category(env: DealEnv) -> None:
    budget = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
    view = await env.new_deal(bant={BantCategory.BUDGET: CatalogChoice(id=budget.id)})

    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(bant={BantCategory.BUDGET: None}), SALES
    )

    assert updated.item.deal.bant.get(BantCategory.BUDGET) is None
    assert await env.changes(updated) == [
        ("bant", "BANT Label: Budget", "풀 예산 확보", "선택 안 함")
    ]


async def test_patch_failure_after_bant_creates_no_label(env: DealEnv) -> None:
    view = await env.new_deal()

    with raises_with(InvalidValueError, PROCUREMENT):
        await env.update.execute(
            view.item.deal.id.value,
            make_patch(
                bant={BantCategory.NEED: CatalogChoice(name="신규 필요")}, procurement="가" * 501
            ),
            SALES,
        )

    assert await _label_count(env) == BASELINE_LABELS
    assert await env.changes(view) == []


async def test_patch_with_another_categorys_label_id_is_rejected_without_a_label(
    env: DealEnv,
) -> None:
    need = await label_by_name(env.uow, BantCategory.NEED, "모름")
    view = await env.new_deal()

    with raises_with(InvalidBantLabelError, LABEL_INVALID):
        await env.update.execute(
            view.item.deal.id.value,
            make_patch(
                bant={
                    BantCategory.BUDGET: CatalogChoice(id=need.id),
                    BantCategory.TIMELINE: CatalogChoice(name="신규 일정"),
                }
            ),
            SALES,
        )

    assert await _label_count(env) == BASELINE_LABELS


async def test_a_patch_without_bant_neither_checks_nor_creates_labels(env: DealEnv) -> None:
    budget = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
    view = await env.new_deal(bant={BantCategory.BUDGET: CatalogChoice(id=budget.id)})

    updated = await env.update.execute(view.item.deal.id.value, make_patch(name="새 이름"), SALES)

    assert updated.item.deal.bant.get(BantCategory.BUDGET) == budget.id
    assert await _label_count(env) == BASELINE_LABELS
