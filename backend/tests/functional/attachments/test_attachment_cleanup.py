"""Feature: Deal을 지우면 첨부가 함께 사라지고, 첨부를 올린 사용자는 지워지지 않고 퇴사 처리된다.

Deal 삭제는 첨부 행(CASCADE)과 저장 위치 아래 `<deal_code>` 디렉터리를 함께 지운다.
삭제 영향에는 첨부 수가 들어간다. 첨부를 올린 사용자는 '연결 있음'이라 삭제하면
퇴사 처리(물리 삭제 아님)다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.attachments import (
    given_deal_with_files_enabled,
    given_file,
    given_storage_location_removed,
    then_deal_directory_is_gone,
    then_disk_holds,
    then_row_count_is,
    then_storage_root_still_exists,
)
from tests.functional.steps.common import then_body_is, then_problem_is, then_status_is
from tests.functional.steps.deals import DEALS, given_deal, when_delete_deal
from tests.functional.steps.rereads import then_user_is_listed_as_resigned
from tests.functional.steps.users import given_signed_in_session, id_of, when_delete_user

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_deleting_a_deal_removes_its_files_and_its_directory(api: Api) -> None:
    """Scenario: Deal을 지우면 첨부 행과 Deal 디렉터리가 사라지고, 다른 Deal의 파일은 남는다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    other = str((await given_deal(api))["code"])
    await given_file(api, code, name="a.pdf", data=b"mine")
    await given_file(api, code, name="b.pdf", data=b"mine too")
    await given_file(api, other, name="c.pdf", data=b"theirs")
    # When
    response = await when_delete_deal(api, code)
    # Then
    then_status_is(response, 204)
    then_deal_directory_is_gone(api, code)
    await then_row_count_is(api, code, 0)
    then_disk_holds(api, other, [b"theirs"])
    then_storage_root_still_exists(api)


async def test_the_deletion_impact_counts_the_attachments(api: Api) -> None:
    """Scenario: 삭제 영향에 그 Deal의 첨부 수가 들어간다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    other = str((await given_deal(api))["code"])
    await given_file(api, code, name="a.pdf")
    await given_file(api, code, name="b.pdf")
    await given_file(api, other, name="c.pdf")
    # When
    response = await api.get(f"{DEALS}/{code}/deletion-impact")
    # Then
    then_status_is(response, 200)
    assert response.json()["attachment_count"] == 2
    assert (await api.get(f"{DEALS}/{other}/deletion-impact")).json()["attachment_count"] == 1


async def test_a_deal_without_files_has_no_attachments_in_its_impact(api: Api) -> None:
    """Scenario: 첨부가 없는 Deal의 삭제 영향 첨부 수는 0이다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await api.get(f"{DEALS}/{code}/deletion-impact")
    # Then
    assert response.json()["attachment_count"] == 0


async def test_a_deal_is_deleted_even_without_a_storage_location(api: Api) -> None:
    """Scenario: 저장 위치 설정이 없어도 Deal 삭제는 204다(디스크는 건드리지 않는다)."""
    # Given
    code = await given_deal_with_files_enabled(api)
    await given_file(api, code, name="a.pdf", data=b"stays")
    await given_storage_location_removed(api)
    # When
    response = await when_delete_deal(api, code)
    # Then
    then_status_is(response, 204)
    await then_row_count_is(api, code, 0)
    then_disk_holds(api, code, [b"stays"])


async def test_a_refused_deal_delete_keeps_the_files(api: Api) -> None:
    """Scenario: 확인 code가 틀려 삭제가 거절되면 파일은 그대로다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    await given_file(api, code, name="a.pdf", data=b"keep")
    # When
    response = await when_delete_deal(api, code, confirm_code="wrong")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_disk_holds(api, code, [b"keep"])
    await then_row_count_is(api, code, 1)


async def test_a_user_who_uploaded_a_file_is_resigned_not_deleted(api: Api) -> None:
    """Scenario: 첨부를 올린 사용자를 삭제하면 퇴사 처리되고 첨부는 그대로 남는다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    await given_file(api, code, session=kim, name="a.pdf", data=b"kim's")
    kim_id = await id_of(api, "kim")
    # When
    response = await when_delete_user(api, kim_id)
    # Then
    then_body_is(response, {"outcome": "resigned"})
    await then_user_is_listed_as_resigned(api, "kim")
    await then_row_count_is(api, code, 1)
    then_disk_holds(api, code, [b"kim's"])
