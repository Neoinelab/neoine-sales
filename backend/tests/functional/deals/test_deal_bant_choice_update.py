"""Feature: Deal 수정에서도 BANT는 목록에서 고르거나 이름으로 입력하고, 없는 이름은 새 Label이 된다.

수정(PATCH)의 `bant` 규칙은 등록과 같다(`test_deal_bant_choice.py`). 바뀐 구분만 History에 한 건씩
남고(새 Label은 이름으로 표기), 수정이 실패하면 새 Label도 Deal 변경도 없다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    deal_body,
    given_deal,
    given_label_id,
    then_deal_keeps,
    then_history_is,
    when_register_deal_with_body,
    when_update_deal,
)
from tests.functional.steps.labels import given_label_list, then_label_count_is

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

NONE = {"budget": None, "authority": None, "need": None, "timeline": None}
LABEL_INVALID = "BANT Label이 올바르지 않습니다."
LABEL_REQUIRED = "Label 이름을 입력하세요."
LABEL_TOO_LONG = "Label 이름은 50자 이내로 입력하세요."
DEFAULT_LABELS = 23


async def _labels_named(api: Api, name: str) -> list[dict[str, object]]:
    return [x for x in await given_label_list(api) if x["name"] == name]


async def test_patching_bant_by_name_records_history_with_the_new_label_name(api: Api) -> None:
    """Scenario: 수정에서 새 이름을 보내면 Label이 생기고 History에는 그 이름이 표기된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_update_deal(
        api, deal["code"], bant={**NONE, "budget": {"name": "신규 예산"}}
    )
    # Then
    then_status_is(response, 200)
    (created,) = await _labels_named(api, "신규 예산")
    await then_deal_keeps(api, deal["code"], bant={**NONE, "budget": created["id"]})
    await then_history_is(
        api, deal["code"], [("bant", "BANT Label: Budget", "선택 안 함", "신규 예산")]
    )


async def test_patching_the_same_label_by_id_or_by_name_records_nothing(api: Api) -> None:
    """Scenario: 같은 Label을 id로 또는 대소문자만 다른 이름으로 보내면 변경도 History도 없다."""
    # Given
    await given_logged_in_as(api, role="sales")
    ceo = await given_label_id(api, category="authority", name="CEO 보고 완료")
    deal = await given_deal(api, bant={**NONE, "authority": ceo})
    # When
    by_id = await when_update_deal(api, deal["code"], bant={**NONE, "authority": {"id": ceo}})
    by_name = await when_update_deal(
        api, deal["code"], bant={**NONE, "authority": {"name": "ceo 보고 완료"}}
    )
    # Then
    then_status_is(by_id, 200)
    then_status_is(by_name, 200)
    await then_history_is(api, deal["code"], [])
    await then_label_count_is(api, count=DEFAULT_LABELS)


async def test_patching_one_category_logs_only_that_category(api: Api) -> None:
    """Scenario: 바뀌지 않은 구분은 History에 남지 않고 바뀐 구분만 한 건씩 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    budget = await given_label_id(api, category="budget", name="풀 예산 확보")
    deal = await given_deal(api, bant={**NONE, "budget": budget})
    # When
    response = await when_update_deal(
        api,
        deal["code"],
        bant={**NONE, "budget": {"id": budget}, "timeline": {"name": "신규 일정"}},
    )
    # Then
    then_status_is(response, 200)
    await then_history_is(
        api, deal["code"], [("bant", "BANT Label: Timeline", "선택 안 함", "신규 일정")]
    )


async def test_patching_with_null_clears_the_category(api: Api) -> None:
    """Scenario: null을 보내면 선택 안 함이 되고 History에 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    budget = await given_label_id(api, category="budget", name="풀 예산 확보")
    deal = await given_deal(api, bant={**NONE, "budget": budget})
    # When
    response = await when_update_deal(api, deal["code"], bant=NONE)
    # Then
    then_status_is(response, 200)
    await then_deal_keeps(api, deal["code"], bant=NONE)
    await then_history_is(
        api, deal["code"], [("bant", "BANT Label: Budget", "풀 예산 확보", "선택 안 함")]
    )


async def test_a_failed_patch_leaves_no_new_label(api: Api) -> None:
    """Scenario: 수정이 BANT 뒤의 검증에서 실패하면 새 Label도, Deal 변경도 없다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_update_deal(
        api, deal["code"], bant={**NONE, "need": {"name": "신규 필요"}}, procurement="가" * 501
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_label_count_is(api, count=DEFAULT_LABELS)
    await then_deal_keeps(api, deal["code"], bant=NONE)
    await then_history_is(api, deal["code"], [])


async def test_read_only_user_cannot_register_a_deal_with_a_new_label(api: Api) -> None:
    """Scenario: 읽기 전용 user는 BANT 이름을 보내도 403이고 Label은 생기지 않는다."""
    # Given
    await given_logged_in_as(api, role="user")
    # When
    response = await when_register_deal_with_body(
        api, {**await deal_body(api), "bant": {**NONE, "need": {"name": "신규 필요"}}}
    )
    # Then
    then_status_is(response, 403)
    await then_label_count_is(api, count=DEFAULT_LABELS)
