"""Feature: 같은 이름의 파일을 다시 올리면 묻고, 교체하거나 건너뛸 수 있다.

기본(ask)은 409(file-exists)로 알린다. 교체(replace)는 같은 첨부 id에 새 내용·크기·형식·설명·
업로더·시각이 들어가고 이전 내용은 디스크에서 사라지며, 교체 권한은 삭제 권한과 같다(업로더 본인,
퇴사한 sales의 파일은 sales 누구나, admin은 모두). 건너뛰기(skip)는 아무것도 바꾸지 않는다.
"""

import unicodedata
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.attachments import (
    REPLACE_FORBIDDEN,
    given_deal_with_files_enabled,
    given_file,
    then_attachment_history_is,
    then_attachment_is_unchanged,
    then_deal_updated_at_is_now,
    then_detail_is,
    then_disk_holds,
    then_listed_names_are,
    then_row_count_is,
    then_upload_is,
    when_upload,
)
from tests.functional.steps.common import then_problem_is
from tests.functional.steps.users import given_signed_in_session, given_user_deleted

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_the_same_name_is_a_conflict_by_default(api: Api) -> None:
    """Scenario: 같은 이름을 on_exists 없이 올리면 409(file-exists)이고 아무것도 바뀌지 않는다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    original = await given_file(api, code, name="a.pdf", data=b"old")
    # When
    response = await when_upload(api, code, name="a.pdf", data=b"new")
    # Then
    then_problem_is(response, status=409, type_suffix="file-exists")
    then_detail_is(response, "같은 이름의 파일이 이미 있습니다: a.pdf")
    await then_attachment_is_unchanged(api, original)
    then_disk_holds(api, code, [b"old"])
    await then_attachment_history_is(api, code, [("", "업로드 a.pdf")])


async def test_skip_keeps_the_existing_file_and_changes_nothing(api: Api) -> None:
    """Scenario: 건너뛰기는 200 skipped이고 행·이력·디스크·Deal 수정 시각이 그대로다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    original = await given_file(api, code, name="a.pdf", data=b"old")
    before = (await api.get(f"/api/v1/deals/{code}")).json()["updated_at"]
    # When
    response = await when_upload(api, code, name="a.pdf", data=b"new", on_exists="skip")
    # Then
    then_upload_is(response, status=200, outcome="skipped")
    assert "location" not in response.headers
    await then_attachment_is_unchanged(api, original)
    then_disk_holds(api, code, [b"old"])
    await then_attachment_history_is(api, code, [("", "업로드 a.pdf")])
    assert (await api.get(f"/api/v1/deals/{code}")).json()["updated_at"] == before


async def test_replace_keeps_the_id_and_swaps_the_content(api: Api) -> None:
    """Scenario: 교체는 200 replaced이고 id는 그대로, 새 내용으로 바뀌고 이전 파일은 사라진다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    original = await given_file(api, code, name="a.pdf", data=b"old", description="이전")
    # When
    response = await when_upload(
        api,
        code,
        name="a.pdf",
        data=b"newer content",
        mime="text/plain",
        description="새 설명",
        on_exists="replace",
    )
    # Then
    replaced = then_upload_is(response, status=200, outcome="replaced", name="a.pdf")
    assert replaced is not None
    assert replaced["id"] == original["id"]
    assert (replaced["size"], replaced["mime"], replaced["description"]) == (
        13,
        "text/plain",
        "새 설명",
    )
    assert replaced["uploaded_at"] != original["uploaded_at"]
    then_disk_holds(api, code, [b"newer content"])
    await then_row_count_is(api, code, 1)
    await then_deal_updated_at_is_now(api, code)


async def test_replace_is_recorded_in_the_deal_history(api: Api) -> None:
    """Scenario: 교체하면 Deal History에 '교체 <파일명>'이 남는다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    await given_file(api, code, name="a.pdf")
    # When
    await when_upload(api, code, name="a.pdf", data=b"v2", on_exists="replace")
    # Then
    await then_attachment_history_is(api, code, [("", "업로드 a.pdf"), ("", "교체 a.pdf")])


@pytest.mark.parametrize("on_exists", ["replace", "skip"])
async def test_replace_and_skip_upload_normally_when_the_name_is_new(
    api: Api, on_exists: str
) -> None:
    """Scenario: 같은 이름이 없으면 replace·skip도 새 업로드(201)다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await when_upload(api, code, name="new.pdf", on_exists=on_exists)
    # Then
    then_upload_is(response, status=201, outcome="uploaded", name="new.pdf")
    then_disk_holds(api, code, [b"hello"])


async def test_names_are_compared_exactly_after_unicode_normalization(api: Api) -> None:
    """Scenario: 대소문자가 다른 이름은 다른 파일이고, 한글 조합 방식이 달라도 같은 이름이다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    await given_file(api, code, name="Report.PDF")
    await given_file(api, code, name="한글.pdf")
    # When
    other_case = await when_upload(api, code, name="report.pdf")
    decomposed = await when_upload(api, code, name=unicodedata.normalize("NFD", "한글.pdf"))
    # Then
    then_upload_is(other_case, status=201, outcome="uploaded")
    then_problem_is(decomposed, status=409, type_suffix="file-exists")
    await then_listed_names_are(api, code, ["report.pdf", "한글.pdf", "Report.PDF"])


async def test_the_uploader_can_replace_their_own_file(api: Api) -> None:
    """Scenario: 업로더 본인 sales는 자기 파일을 교체할 수 있다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    await given_file(api, code, session=kim, name="a.pdf", data=b"old")
    # When
    response = await when_upload(
        api, code, session=kim, name="a.pdf", data=b"new", on_exists="replace"
    )
    # Then
    then_upload_is(response, status=200, outcome="replaced")
    then_disk_holds(api, code, [b"new"])


async def test_another_sales_cannot_replace_a_file_but_can_still_skip_or_ask(api: Api) -> None:
    """Scenario: 다른 sales의 교체는 403이고 아무것도 바뀌지 않는다. ask는 409, skip은 200이다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    original = await given_file(api, code, session=kim, name="a.pdf", data=b"kim's")
    # When
    replace = await when_upload(
        api, code, session=park, name="a.pdf", data=b"park's", on_exists="replace"
    )
    ask = await when_upload(api, code, session=park, name="a.pdf", data=b"park's")
    skip = await when_upload(
        api, code, session=park, name="a.pdf", data=b"park's", on_exists="skip"
    )
    # Then
    then_problem_is(replace, status=403, type_suffix="forbidden")
    then_detail_is(replace, REPLACE_FORBIDDEN)
    then_problem_is(ask, status=409, type_suffix="file-exists")
    then_upload_is(skip, status=200, outcome="skipped")
    await then_attachment_is_unchanged(api, original)
    then_disk_holds(api, code, [b"kim's"])


async def test_an_admin_can_replace_anyones_file_and_becomes_its_uploader(api: Api) -> None:
    """Scenario: admin은 남의 파일도 교체할 수 있고 업로더가 admin으로 바뀐다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    original = await given_file(api, code, session=kim, name="a.pdf", data=b"old")
    # When
    response = await when_upload(api, code, name="a.pdf", data=b"admin's", on_exists="replace")
    # Then
    replaced = then_upload_is(response, status=200, outcome="replaced")
    assert replaced is not None
    assert replaced["uploaded_by"]["id"] != original["uploaded_by"]["id"]
    assert replaced["uploaded_by"]["role"] == "admin"


async def test_sales_can_replace_a_file_whose_uploader_has_resigned(api: Api) -> None:
    """Scenario: 업로더(sales)가 퇴사했으면 다른 sales가 그 파일을 교체할 수 있다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    original = await given_file(api, code, session=kim, name="a.pdf", data=b"old")
    resigned_id = original["uploaded_by"]["id"]
    await given_user_deleted(api, resigned_id)  # 첨부가 있어 퇴사 처리된다
    # When
    response = await when_upload(
        api, code, session=park, name="a.pdf", data=b"new", on_exists="replace"
    )
    # Then
    replaced = then_upload_is(response, status=200, outcome="replaced")
    assert replaced is not None
    assert replaced["id"] == original["id"]
    then_disk_holds(api, code, [b"new"])
    assert replaced["uploaded_by"]["label"] == "사용자 park"
