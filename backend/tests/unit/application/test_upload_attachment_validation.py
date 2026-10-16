"""UploadAttachment - 검증(P2b AC-08): Deal 확인이 먼저, 목업 순서의 422, 실패하면 흔적이 없다."""

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
    before = await attachment_env.snapshot()
    options = {"name": "a.pdf", **fields}

    with raises_with(InvalidValueError, message):
        await attachment_env.put(KIM, options.pop("name"), b"data", **options)

    assert await attachment_env.snapshot() == before
    assert attachment_env.storage.file_count() == 0


async def test_a_nul_in_the_description_is_rejected(attachment_env: AttachmentEnv) -> None:
    with pytest.raises(InvalidValueError, match="NUL"):
        await attachment_env.put(KIM, "a.pdf", b"x", description="a\x00b")

    assert await attachment_env.rows() == []


async def test_the_first_violation_wins_in_the_documented_order(
    attachment_env: AttachmentEnv,
) -> None:
    with raises_with(InvalidValueError, DESCRIPTION_TOO_LONG):
        await attachment_env.put(
            KIM, "a.exe", b"x", description="가" * 101, declared_size=MAX_FILE_BYTES + 1
        )
    with raises_with(InvalidValueError, FILE_TOO_LARGE):
        await attachment_env.put(KIM, "a.exe", b"x", declared_size=MAX_FILE_BYTES + 1)
    with raises_with(InvalidValueError, blocked_message("exe")):
        await attachment_env.put(KIM, "dir/a.exe", b"x")


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code", ""])
async def test_a_missing_or_malformed_deal_is_not_found_before_the_upload_is_validated(
    attachment_env: AttachmentEnv, code: str
) -> None:
    with raises_with(DealNotFoundError, DEAL_NOT_FOUND):
        await attachment_env.put(KIM, None, code=code, description="가" * 101)

    assert attachment_env.storage.file_count() == 0


async def test_validation_comes_before_the_storage_location_check(
    attachment_env: AttachmentEnv,
) -> None:
    await attachment_env.remove_storage_settings()

    with raises_with(InvalidValueError, NO_FILE):
        await attachment_env.put(KIM, None)


async def test_a_missing_deal_is_not_found_even_without_a_storage_location(
    attachment_env: AttachmentEnv,
) -> None:
    await attachment_env.remove_storage_settings()

    with pytest.raises(DealNotFoundError):
        await attachment_env.put(KIM, "a.pdf", code="20991231-ZZZZ")


async def test_a_valid_upload_without_a_storage_location_is_unavailable(
    attachment_env: AttachmentEnv,
) -> None:
    await attachment_env.remove_storage_settings()
    before = await attachment_env.snapshot()

    with raises_with(StorageUnavailableError, UPLOAD_UNAVAILABLE):
        await attachment_env.put(KIM, "a.pdf", b"x")

    assert await attachment_env.snapshot() == before
