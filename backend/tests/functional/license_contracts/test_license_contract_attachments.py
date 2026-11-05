"""Feature: 계약에 파일을 첨부한다(Deal 첨부와 같은 규칙, 이력은 남기지 않는다).

같은 이름은 기본 409(file-exists)이고 교체·건너뛰기를 고를 수 있다. 삭제·교체 권한은 admin 모두,
sales는 본인 또는 퇴사한 sales의 파일, user는 불가다. 파일은
`<저장 위치>/license-contracts/<계약 id>/<키>`에 있다(Deal 폴더가 아니다).
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.attachments import (
    DELETE_FORBIDDEN,
    OCTET_STREAM,
    REPLACE_FORBIDDEN,
    UPLOAD_UNAVAILABLE,
    disk_files,
    given_file,
    given_storage_location_removed,
    then_disk_holds,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import history_rows, when_list_history
from tests.functional.steps.license_contracts import (
    contracts_of,
    given_contract_file,
    given_contract_of,
    given_won_deal,
    then_contract_disk_holds,
    then_contract_file_is_named_by_a_key,
    then_contract_folder_exists,
    then_deal_folder_has_no_contract_files,
    then_file_row_count_is,
    when_delete_contract_file,
    when_download_contract_file,
    when_get_contract,
    when_list_contract_files,
    when_upload_contract_file,
)
from tests.functional.steps.users import given_signed_in_session
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from typing import Any

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

ATTACHMENT_KEYS = {"id", "file_name", "description", "size", "mime", "uploaded_by", "uploaded_at"}


async def _contract(api: Api) -> tuple[str, dict[str, Any]]:
    await given_logged_in_as(api)
    code = await given_won_deal(api)
    return code, await given_contract_of(api, code)


async def test_uploading_stores_the_row_and_the_disk_file(api: Api) -> None:
    """Scenario: 업로드하면 201 uploaded이고 목록·계약 첨부 건수·디스크에 반영된다."""
    # Given
    code, contract = await _contract(api)
    # When
    response = await when_upload_contract_file(
        api, contract["id"], name="계약서.pdf", data=b"contract", description="최종본"
    )
    # Then
    then_status_is(response, 201)
    body = response.json()
    assert set(body) == {"outcome", "attachment"}
    assert body["outcome"] == "uploaded"
    assert set(body["attachment"]) >= ATTACHMENT_KEYS
    assert body["attachment"]["file_name"] == "계약서.pdf"
    assert (body["attachment"]["size"], body["attachment"]["description"]) == (8, "최종본")
    listed = (await when_list_contract_files(api, contract["id"])).json()
    assert [a["id"] for a in listed["items"]] == [body["attachment"]["id"]]
    assert (await when_get_contract(api, contract["id"])).json()["attachment_count"] == 1
    then_contract_disk_holds(api, contract["id"], [b"contract"])
    then_contract_file_is_named_by_a_key(api, contract["id"])
    then_deal_folder_has_no_contract_files(api, code)


async def test_uploading_does_not_write_the_deal_history(api: Api) -> None:
    """Scenario: 계약 첨부는 Deal 이력에 남지 않는다."""
    # Given
    code, contract = await _contract(api)
    before = history_rows(await when_list_history(api, code))
    # When
    await when_upload_contract_file(api, contract["id"])
    # Then
    assert history_rows(await when_list_history(api, code)) == before


async def test_the_list_is_newest_first_and_readable_by_every_role(api: Api) -> None:
    """Scenario: 첨부 목록은 최신순이고 user도 읽는다."""
    # Given
    _, contract = await _contract(api)
    await given_contract_file(api, contract["id"], name="old.pdf")
    await given_contract_file(api, contract["id"], name="new.pdf")
    viewer = await given_signed_in_session(api, login_id="viewer", role="user")
    # When
    response = await when_list_contract_files(api, contract["id"], session=viewer)
    # Then
    then_status_is(response, 200)
    assert [a["file_name"] for a in response.json()["items"]] == ["new.pdf", "old.pdf"]


async def test_the_same_name_is_a_conflict_by_default(api: Api) -> None:
    """Scenario: 같은 이름을 on_exists 없이 올리면 409(file-exists)이고 아무것도 바뀌지 않는다."""
    # Given
    _code, contract = await _contract(api)
    await given_contract_file(api, contract["id"], name="a.pdf", data=b"old")
    # When
    response = await when_upload_contract_file(api, contract["id"], name="a.pdf", data=b"new")
    # Then
    then_problem_is(response, status=409, type_suffix="file-exists")
    then_contract_disk_holds(api, contract["id"], [b"old"])
    await then_file_row_count_is(api, 1)


async def test_skip_changes_nothing(api: Api) -> None:
    """Scenario: 건너뛰기는 200 skipped이고 기존 파일이 그대로다."""
    # Given
    _code, contract = await _contract(api)
    await given_contract_file(api, contract["id"], name="a.pdf", data=b"old")
    # When
    response = await when_upload_contract_file(
        api, contract["id"], name="a.pdf", data=b"new", on_exists="skip"
    )
    # Then
    then_status_is(response, 200)
    assert response.json() == {"outcome": "skipped", "attachment": None}
    then_contract_disk_holds(api, contract["id"], [b"old"])


async def test_replace_keeps_the_id_and_swaps_the_content(api: Api) -> None:
    """Scenario: 교체는 200 replaced이고 id는 그대로, 새 내용으로 바뀌며 이전 파일은 사라진다."""
    # Given
    _code, contract = await _contract(api)
    original = await given_contract_file(api, contract["id"], name="a.pdf", data=b"old")
    # When
    response = await when_upload_contract_file(
        api, contract["id"], name="a.pdf", data=b"newer content", on_exists="replace"
    )
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert body["outcome"] == "replaced"
    assert body["attachment"]["id"] == original["id"]
    assert body["attachment"]["size"] == len(b"newer content")
    then_contract_disk_holds(api, contract["id"], [b"newer content"])


async def test_another_sales_cannot_replace_a_file_they_did_not_upload(api: Api) -> None:
    """Scenario: 다른 sales의 교체는 403이고 파일이 그대로다."""
    # Given
    _code, contract = await _contract(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    await given_contract_file(api, contract["id"], session=kim, name="a.pdf", data=b"keep")
    # When
    response = await when_upload_contract_file(
        api, contract["id"], session=park, name="a.pdf", data=b"new", on_exists="replace"
    )
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == REPLACE_FORBIDDEN
    then_contract_disk_holds(api, contract["id"], [b"keep"])


async def test_the_same_name_in_another_contract_is_a_new_file(api: Api) -> None:
    """Scenario: 이름 중복은 계약 안에서만 본다(갱신으로 생긴 새 계약은 같은 이름을 쓸 수 있다)."""
    # Given
    _code, contract = await _contract(api)
    api.clock.advance(60)
    issued = await api.post(
        f"/api/v1/license-contracts/{contract['id']}/issue",
        json={"start_date": "2026-01-01", "term_amount": 1, "term_unit": "year"},
    )
    then_status_is(issued, 200)
    renewal = (
        await api.post(
            f"/api/v1/license-contracts/{contract['id']}/renewal",
            json={"start_date": "2027-01-01", "term_amount": 1, "term_unit": "year"},
        )
    ).json()
    await given_contract_file(api, contract["id"], name="a.pdf", data=b"one")
    # When
    response = await when_upload_contract_file(api, renewal["id"], name="a.pdf", data=b"two")
    # Then
    then_status_is(response, 201)
    then_contract_disk_holds(api, contract["id"], [b"one"])
    then_contract_disk_holds(api, renewal["id"], [b"two"])


@pytest.mark.parametrize("name", ["virus.exe", "run.bat"])
async def test_a_blocked_extension_is_rejected(api: Api, name: str) -> None:
    """Scenario: 차단 확장자는 422이고 아무것도 저장되지 않는다."""
    # Given
    code, contract = await _contract(api)
    # When
    response = await when_upload_contract_file(api, contract["id"], name=name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_file_row_count_is(api, 0)
    assert disk_files(api, code) == []
    then_contract_disk_holds(api, contract["id"], [])


async def test_a_description_over_100_characters_is_rejected(api: Api) -> None:
    """Scenario: 설명이 100자를 넘으면 422다."""
    # Given
    _, contract = await _contract(api)
    # When
    response = await when_upload_contract_file(api, contract["id"], description="가" * 101)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")


async def test_a_request_without_a_file_part_is_rejected(api: Api) -> None:
    """Scenario: 파일 파트가 없으면 422다."""
    # Given
    _, contract = await _contract(api)
    # When
    response = await when_upload_contract_file(api, contract["id"], name=None)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")


async def test_without_a_storage_location_the_upload_is_unavailable(api: Api) -> None:
    """Scenario: 저장 위치가 없으면 503(storage-unavailable)이다."""
    # Given
    _, contract = await _contract(api)
    await given_storage_location_removed(api)
    # When
    response = await when_upload_contract_file(api, contract["id"])
    # Then
    then_problem_is(response, status=503, type_suffix="storage-unavailable")
    assert response.json()["detail"] == UPLOAD_UNAVAILABLE
    await then_file_row_count_is(api, 0)


async def test_uploading_to_a_missing_contract_is_404(api: Api) -> None:
    """Scenario: 없는 계약에 올리면 404다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_upload_contract_file(api, MISSING_ID)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


async def test_everyone_downloads_the_exact_bytes_as_an_attachment(api: Api) -> None:
    """Scenario: 저장한 바이트 그대로, octet-stream 첨부로 내려받는다."""
    # Given
    _, contract = await _contract(api)
    data = b"%PDF \x00\x01\x02 binary \xff" * 50
    attachment = await given_contract_file(api, contract["id"], name="report.pdf", data=data)
    viewer = await given_signed_in_session(api, login_id="viewer", role="user")
    # When
    response = await when_download_contract_file(api, attachment["id"], session=viewer)
    # Then
    then_status_is(response, 200)
    assert response.content == data
    assert response.headers["content-type"].split(";")[0] == OCTET_STREAM
    assert response.headers["content-disposition"] == (
        "attachment; filename=\"report.pdf\"; filename*=UTF-8''report.pdf"
    )


async def test_downloading_an_unknown_attachment_is_404(api: Api) -> None:
    """Scenario: 없는 첨부의 다운로드는 404다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_download_contract_file(api, MISSING_ID)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


async def test_the_uploader_deletes_their_own_file(api: Api) -> None:
    """Scenario: 업로더 본인이 지우면 204이고 행·디스크에서 사라진다."""
    # Given
    _code, contract = await _contract(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    attachment = await given_contract_file(api, contract["id"], session=kim, name="a.pdf")
    # When
    response = await when_delete_contract_file(api, attachment["id"], session=kim)
    # Then
    then_status_is(response, 204)
    then_contract_disk_holds(api, contract["id"], [])
    then_contract_folder_exists(api, contract["id"])  # 파일만 지우고 계약 폴더는 남긴다
    await then_file_row_count_is(api, 0)
    then_problem_is(
        await when_download_contract_file(api, attachment["id"]),
        status=404,
        type_suffix="not-found",
    )


async def test_another_sales_cannot_delete_it_but_an_admin_can(api: Api) -> None:
    """Scenario: 다른 sales의 삭제는 403이고 admin은 지울 수 있다."""
    # Given
    _code, contract = await _contract(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    attachment = await given_contract_file(
        api, contract["id"], session=kim, name="a.pdf", data=b"k"
    )
    # When
    refused = await when_delete_contract_file(api, attachment["id"], session=park)
    allowed = await when_delete_contract_file(api, attachment["id"])
    # Then
    then_problem_is(refused, status=403, type_suffix="forbidden")
    assert refused.json()["detail"] == DELETE_FORBIDDEN
    then_status_is(allowed, 204)
    then_contract_disk_holds(api, contract["id"], [])


async def test_a_read_only_user_cannot_upload_or_delete(api: Api) -> None:
    """Scenario: user의 업로드·삭제는 403이다."""
    # Given
    _, contract = await _contract(api)
    attachment = await given_contract_file(api, contract["id"])
    viewer = await given_signed_in_session(api, login_id="viewer", role="user")
    # When
    upload = await when_upload_contract_file(api, contract["id"], session=viewer, name="b.pdf")
    delete = await when_delete_contract_file(api, attachment["id"], session=viewer)
    # Then
    then_problem_is(upload, status=403, type_suffix="forbidden")
    then_problem_is(delete, status=403, type_suffix="forbidden")


async def test_deleting_an_unknown_attachment_is_404(api: Api) -> None:
    """Scenario: 없는 첨부의 삭제는 404다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_delete_contract_file(api, MISSING_ID)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


async def test_deleting_a_file_leaves_the_other_contract_files(api: Api) -> None:
    """Scenario: 첨부 하나를 지워도 같은 계약의 다른 첨부와 계약 자체는 남는다."""
    # Given
    code, contract = await _contract(api)
    gone = await given_contract_file(api, contract["id"], name="gone.pdf", data=b"gone")
    await given_contract_file(api, contract["id"], name="kept.pdf", data=b"kept")
    # When
    response = await when_delete_contract_file(api, gone["id"])
    # Then
    then_status_is(response, 204)
    then_contract_disk_holds(api, contract["id"], [b"kept"])
    assert len(await contracts_of(api, code)) == 1


async def test_the_deal_attachments_stay_in_the_deal_folder_apart_from_contract_files(
    api: Api,
) -> None:
    """Scenario: Deal 첨부는 Deal 폴더, 계약 첨부는 계약 폴더에 따로 저장된다."""
    # Given
    code, contract = await _contract(api)
    await given_file(api, code, name="deal.pdf", data=b"deal-bytes")
    # When
    response = await when_upload_contract_file(api, contract["id"], name="c.pdf", data=b"c-bytes")
    # Then
    then_status_is(response, 201)
    then_disk_holds(api, code, [b"deal-bytes"])
    then_contract_disk_holds(api, contract["id"], [b"c-bytes"])
