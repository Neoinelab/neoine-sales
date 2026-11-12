"""UploadAttachment - 검증: Deal 확인이 먼저, 목업 순서의 422, 실패하면 흔적이 없다."""

from typing import TYPE_CHECKING, Any

import pytest

from app.application.storage.errors import UPLOAD_UNAVAILABLE, StorageUnavailableError
from app.domain.attachment.values import (
    DESCRIPTION_TOO_LONG,
    FILE_TOO_LARGE,
    INVALID_FILE_NAME,
    MAX_FILE_BYTES,
    NO_FILE,
    blocked_message,
)
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import DealNotFoundError
from tests.support.expect import raises_with
from tests.unit.application.attachment_env import DEAL_NOT_FOUND, KIM

if TYPE_CHECKING:
    from tests.unit.application.attachment_env import AttachmentEnv

INVALID_UPLOADS = [
    pytest.param({"name": None}, NO_FILE, id="no-file"),
    pytest.param({"description": "가" * 101}, DESCRIPTION_TOO_LONG, id="description-101"),
    pytest.param(
        {"name": "big.bin", "declared_size": MAX_FILE_BYTES + 1}, FILE_TOO_LARGE, id="over-100mb"
    ),
    pytest.param({"name": "setup.EXE"}, blocked_message("exe"), id="blocked-extension"),
    pytest.param({"name": "a/b.txt"}, INVALID_FILE_NAME, id="slash-in-name"),
    pytest.param({"name": ".."}, INVALID_FILE_NAME, id="dot-dot-name"),
    pytest.param({"name": "x" * 256}, INVALID_FILE_NAME, id="name-256"),
    pytest.param({"name": "a\x01.txt"}, INVALID_FILE_NAME, id="control-char"),
]


@pytest.mark.parametrize(("fields", "message"), INVALID_UPLOADS)
async def test_an_invalid_upload_is_rejected_and_leaves_nothing_behind(
    attachment_env: AttachmentEnv, fields: dict[str, Any], message: str
) -> None:
    """규칙 위반 업로드는 정해진 문구의 422이고 행·이력·파일이 남지 않는다.

    테스트 코드: AT-006
    """
    # given: 업로드 전 상태
    before = await attachment_env.snapshot()
    options = {"name": "a.pdf", **fields}

    # when·then: 규칙을 어긴 파일을 올리면 해당 문구의 오류다
    with raises_with(InvalidValueError, message):
        await attachment_env.put(KIM, options.pop("name"), b"data", **options)

    # then: 저장 상태가 그대로이고 디스크 파일이 없다
    assert await attachment_env.snapshot() == before
    assert attachment_env.storage.file_count() == 0


async def test_a_nul_in_the_description_is_rejected(attachment_env: AttachmentEnv) -> None:
    """설명에 NUL이 있으면 거절된다.

    테스트 코드: AT-007
    """
    # when·then: 설명 "a\x00b"로 올리면 NUL 오류다 (전제: 저장 위치가 설정된 Deal)
    with raises_with(InvalidValueError, "설명에는 NUL 문자를 쓸 수 없습니다"):
        await attachment_env.put(KIM, "a.pdf", b"x", description="a\x00b")

    # then: 첨부 행이 없다
    assert await attachment_env.rows() == []


async def test_the_first_violation_wins_in_the_documented_order(
    attachment_env: AttachmentEnv,
) -> None:
    """여러 규칙을 어기면 정해진 순서의 첫 위반 문구만 나온다.

    테스트 코드: AT-008
    """
    # when·then: 설명 101자에 크기 초과, 차단 확장자이면 설명 문구다 (전제: 저장 위치가 설정된 Deal)
    with raises_with(InvalidValueError, DESCRIPTION_TOO_LONG):
        await attachment_env.put(
            KIM, "a.exe", b"x", description="가" * 101, declared_size=MAX_FILE_BYTES + 1
        )
    # when·then: 크기 초과 + 차단 확장자이면 크기 문구다
    with raises_with(InvalidValueError, FILE_TOO_LARGE):
        await attachment_env.put(KIM, "a.exe", b"x", declared_size=MAX_FILE_BYTES + 1)
    # when·then: 차단 확장자 + 쓸 수 없는 이름("dir/a.exe")이면 차단 확장자 문구다
    with raises_with(InvalidValueError, blocked_message("exe")):
        await attachment_env.put(KIM, "dir/a.exe", b"x")


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code", ""])
async def test_a_missing_or_malformed_deal_is_not_found_before_the_upload_is_validated(
    attachment_env: AttachmentEnv, code: str
) -> None:
    """없는 Deal·형식이 틀린 code는 파일 검증보다 먼저 404다.

    테스트 코드: AT-013
    """
    # when·then: 파일 없이 설명 101자로 올려도 Deal 없음 오류다 (전제: 저장 위치가 설정된 Deal)
    with raises_with(DealNotFoundError, DEAL_NOT_FOUND):
        await attachment_env.put(KIM, None, code=code, description="가" * 101)

    # then: 디스크 파일이 없다
    assert attachment_env.storage.file_count() == 0


async def test_validation_comes_before_the_storage_location_check(
    attachment_env: AttachmentEnv,
) -> None:
    """검증 위반이 저장 위치 확인보다 먼저다.

    테스트 코드: AT-014
    """
    # given: 저장 위치 설정이 없다
    await attachment_env.remove_storage_settings()

    # when·then: 파일 없이 올리면 저장 위치 오류가 아니라 파일 없음 문구다
    with raises_with(InvalidValueError, NO_FILE):
        await attachment_env.put(KIM, None)


async def test_a_missing_deal_is_not_found_even_without_a_storage_location(
    attachment_env: AttachmentEnv,
) -> None:
    """저장 위치가 없어도 없는 Deal은 404다.

    테스트 코드: AT-013
    """
    # given: 저장 위치 설정이 없다
    await attachment_env.remove_storage_settings()

    # when·then: 없는 Deal에 올리면 Deal 없음 오류다
    with pytest.raises(DealNotFoundError):
        await attachment_env.put(KIM, "a.pdf", code="20991231-ZZZZ")


async def test_a_valid_upload_without_a_storage_location_is_unavailable(
    attachment_env: AttachmentEnv,
) -> None:
    """저장 위치 설정이 없으면 올바른 업로드도 503 오류이고 아무것도 남지 않는다.

    테스트 코드: AT-014
    """
    # given: 저장 위치 설정이 없고 현재 상태를 기록한다
    await attachment_env.remove_storage_settings()
    before = await attachment_env.snapshot()

    # when·then: 올바른 파일을 올리면 저장 위치 불가 오류다
    with raises_with(StorageUnavailableError, UPLOAD_UNAVAILABLE):
        await attachment_env.put(KIM, "a.pdf", b"x")

    # then: 저장 상태가 그대로다
    assert await attachment_env.snapshot() == before
