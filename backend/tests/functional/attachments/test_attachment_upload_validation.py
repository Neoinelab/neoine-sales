"""Feature: 올릴 수 없는 파일은 이유를 알려 주고, 아무것도 저장하지 않는다.

검증 순서와 문구는 화면(목업)과 같다: 파일 없음 -> 설명 100자 -> 100MB -> 차단 확장자 -> 파일 이름.
실패하면 첨부 행·Deal History·디스크 파일이 모두 남지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.attachments import (
    DESCRIPTION_TOO_LONG,
    INVALID_NAME,
    NO_FILE,
    TOO_LARGE,
    given_deal_with_files_enabled,
    then_attachment_history_is,
    then_detail_is,
    then_disk_holds,
    then_row_count_is,
    when_upload,
)
from tests.functional.steps.common import then_problem_is

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

MAX_BYTES = 100 * 1024 * 1024
BLOCKED = "실행·설치 파일(.{ext})은 업로드할 수 없습니다."


async def _then_nothing_is_kept(api: Api, code: str) -> None:
    await then_row_count_is(api, code, 0)
    await then_attachment_history_is(api, code, [])
    then_disk_holds(api, code, [])


async def test_no_file_part_is_rejected(api: Api) -> None:
    """Scenario: 파일 파트가 없으면 422(invalid-value)와 안내 문구다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await when_upload(api, code, name=None, description="설명만")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, NO_FILE)
    await _then_nothing_is_kept(api, code)


async def test_a_description_over_100_characters_is_rejected(api: Api) -> None:
    """Scenario: 앞뒤 공백을 뺀 설명이 101자(코드 포인트)이면 422다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await when_upload(api, code, description="  " + "😀" * 101 + "  ")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, DESCRIPTION_TOO_LONG)
    await _then_nothing_is_kept(api, code)


async def test_a_nul_in_the_description_is_rejected(api: Api) -> None:
    """Scenario: 설명에 NUL 문자가 있으면 422다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await when_upload(api, code, description="a\x00b")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await _then_nothing_is_kept(api, code)


async def test_a_file_over_100mb_is_rejected(api: Api) -> None:
    """Scenario: 100MB(104,857,600바이트)를 1바이트라도 넘으면 422이고 디스크에 남지 않는다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await when_upload(api, code, name="big.bin", data=bytes(MAX_BYTES + 1))
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, TOO_LARGE)
    await _then_nothing_is_kept(api, code)


@pytest.mark.parametrize(
    "name", ["setup.exe", "SETUP.MSI", "run.Sh", "a.b.ps1", "x.appimage", "x.vbs"]
)
async def test_a_blocked_extension_is_rejected_with_the_lowercase_extension(
    api: Api, name: str
) -> None:
    """Scenario: 실행·설치 파일 확장자는 마지막 확장자 기준으로 대소문자 없이 막힌다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await when_upload(api, code, name=name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, BLOCKED.format(ext=name.rsplit(".", 1)[1].lower()))
    await _then_nothing_is_kept(api, code)


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("..", id="dot-dot"),
        pytest.param(".", id="dot"),
        pytest.param("n" * 256, id="256-chars"),
    ],
)
async def test_a_file_name_that_cannot_be_used_is_rejected(api: Api, name: str) -> None:
    """Scenario: 255자를 넘거나 '.', '..'인 이름은 422다(제어 문자는 단위 테스트가 맡는다)."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await when_upload(api, code, name=name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, INVALID_NAME)
    await _then_nothing_is_kept(api, code)


async def test_the_first_violation_is_the_one_reported(api: Api) -> None:
    """Scenario: 설명도 길고 차단 확장자인 파일은 설명 문구가 먼저 나온다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await when_upload(api, code, name="a.exe", description="가" * 101)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, DESCRIPTION_TOO_LONG)


async def test_an_unknown_on_exists_value_is_a_request_validation_error(api: Api) -> None:
    """Scenario: on_exists에 모르는 값을 보내면 422(request-validation)이다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    # When
    response = await when_upload(api, code, on_exists="overwrite")
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await _then_nothing_is_kept(api, code)
