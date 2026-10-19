"""UploadAttachment - 새 파일(P2b AC-07): 그대로 저장하고 행·이력·Deal 수정 시각을 남긴다."""

import re
from typing import TYPE_CHECKING

import pytest

from app.application.attachment.inputs import UploadOutcomeKind
from app.application.ports.file_storage import StoredFileLocation
from tests.unit.application.attachment_env import KIM, ROOT_PATH, TARGET

if TYPE_CHECKING:
    from tests.unit.application.attachment_env import AttachmentEnv


async def test_a_new_file_is_stored_byte_for_byte_and_recorded(
    attachment_env: AttachmentEnv,
) -> None:
    outcome = await attachment_env.put(KIM, "견적서.pdf", b"%PDF-1.7 bytes", description=" 최종본 ")

    attachment = outcome.attachment
    assert outcome.kind is UploadOutcomeKind.UPLOADED
    assert attachment.file_name.value == "견적서.pdf"
    assert (attachment.description, attachment.size) == ("최종본", len(b"%PDF-1.7 bytes"))
    assert (attachment.mime, attachment.uploaded_by) == ("application/pdf", KIM.user_id)
    assert attachment.deal_code.value == attachment_env.code
    assert attachment_env.content_of(attachment) == b"%PDF-1.7 bytes"
    assert (await attachment_env.stored(attachment.id)).storage_key == attachment.storage_key


async def test_the_upload_time_is_the_server_time_of_the_request(
    attachment_env: AttachmentEnv,
) -> None:
    outcome = await attachment_env.put(KIM, "a.pdf")

    now = attachment_env.env.clock.now()
    assert outcome.attachment.uploaded_at == now
    assert outcome.attachment.created_at == outcome.attachment.updated_at == now


async def test_the_disk_file_is_named_by_a_random_key_not_by_the_original_name(
    attachment_env: AttachmentEnv,
) -> None:
    outcome = await attachment_env.put(KIM, "견적서 최종.pdf", b"x")

    key = outcome.attachment.storage_key
    assert re.fullmatch(r"[0-9a-f]{32}", key)
    assert attachment_env.storage.entries(f"{ROOT_PATH}/{attachment_env.code}") == [key]


async def test_every_upload_gets_its_own_key(attachment_env: AttachmentEnv) -> None:
    first = await attachment_env.uploaded(KIM, "a.pdf", b"1")
    second = await attachment_env.uploaded(KIM, "b.pdf", b"2")

    assert first.storage_key != second.storage_key
    assert attachment_env.content_of(first) == b"1"
    assert attachment_env.content_of(second) == b"2"


async def test_the_size_is_the_number_of_bytes_actually_stored(
    attachment_env: AttachmentEnv,
) -> None:
    outcome = await attachment_env.put(KIM, "a.bin", b"0123456789", declared_size=3)

    assert outcome.attachment.size == 10


async def test_the_size_is_known_even_when_the_request_did_not_declare_one(
    attachment_env: AttachmentEnv,
) -> None:
    outcome = await attachment_env.put(KIM, "a.bin", b"abcde", declared_size=None)

    assert outcome.attachment.size == 5


async def test_an_empty_file_is_accepted(attachment_env: AttachmentEnv) -> None:
    outcome = await attachment_env.put(KIM, "empty.txt", b"")

    assert outcome.kind is UploadOutcomeKind.UPLOADED
    assert outcome.attachment.size == 0
    assert attachment_env.content_of(outcome.attachment) == b""


@pytest.mark.parametrize("name", ["a.tar.gz", "README", ".bashrc", "한글 이름 (1).docx", "x" * 255])
async def test_ordinary_names_are_accepted(attachment_env: AttachmentEnv, name: str) -> None:
    outcome = await attachment_env.put(KIM, name, b"x")

    assert outcome.attachment.file_name.value == name


async def test_the_description_defaults_to_empty(attachment_env: AttachmentEnv) -> None:
    outcome = await attachment_env.put(KIM, "a.pdf")

    assert outcome.attachment.description == ""


@pytest.mark.parametrize(
    ("sent", "stored"),
    [
        ("application/pdf", "application/pdf"),
        (None, "application/octet-stream"),
        ("", "application/octet-stream"),
        ("x/" + "y" * 253, "x/" + "y" * 253),
        ("x/" + "y" * 254, "application/octet-stream"),
    ],
)
async def test_the_mime_is_the_clients_unless_it_is_missing_or_longer_than_255(
    attachment_env: AttachmentEnv, sent: str | None, stored: str
) -> None:
    outcome = await attachment_env.put(KIM, "a.bin", b"x", mime=sent)

    assert outcome.attachment.mime == stored


async def test_one_history_entry_records_the_upload(attachment_env: AttachmentEnv) -> None:
    await attachment_env.put(KIM, "a.pdf")

    assert await attachment_env.history() == [(TARGET, "", "업로드 a.pdf")]
    (entry,) = await attachment_env.entries()
    assert entry.changed_by == KIM.user_id
    assert entry.changed_at == attachment_env.env.clock.now()


async def test_the_deal_modification_time_becomes_the_upload_time(
    attachment_env: AttachmentEnv,
) -> None:
    before = await attachment_env.deal_updated_at()

    await attachment_env.put(KIM, "a.pdf")

    now = attachment_env.env.clock.now()
    assert before < now
    assert await attachment_env.deal_updated_at() == now


async def test_the_upload_is_committed(attachment_env: AttachmentEnv) -> None:
    commits = attachment_env.env.uow.commits

    await attachment_env.put(KIM, "a.pdf")

    assert attachment_env.env.uow.commits > commits


async def test_the_same_name_in_another_deal_is_a_separate_file(
    attachment_env: AttachmentEnv,
) -> None:
    other = await attachment_env.env.new_deal()
    first = await attachment_env.uploaded(KIM, "a.pdf", b"first")

    second = await attachment_env.put(KIM, "a.pdf", b"second", code=other.item.deal.id.value)

    assert second.kind is UploadOutcomeKind.UPLOADED
    assert second.attachment.id != first.id
    assert attachment_env.content_of(first) == b"first"
    location = StoredFileLocation(deal_code=other.item.deal.id, key=second.attachment.storage_key)
    assert attachment_env.storage.contents_of(attachment_env.root, location) == b"second"


async def test_names_that_differ_only_by_case_are_separate_files(
    attachment_env: AttachmentEnv,
) -> None:
    await attachment_env.uploaded(KIM, "Report.PDF", b"1")

    outcome = await attachment_env.put(KIM, "report.pdf", b"2")

    assert outcome.kind is UploadOutcomeKind.UPLOADED
    assert len(await attachment_env.rows()) == 2


@pytest.mark.parametrize("on_exists", ["replace", "skip"])
async def test_replace_and_skip_still_upload_when_no_file_has_that_name(
    attachment_env: AttachmentEnv, on_exists: str
) -> None:
    from app.domain.attachment.values import OnExists  # noqa: PLC0415

    outcome = await attachment_env.put(KIM, "new.pdf", b"x", on_exists=OnExists(on_exists))

    assert outcome.kind is UploadOutcomeKind.UPLOADED
    assert attachment_env.content_of(outcome.attachment) == b"x"
    assert await attachment_env.history() == [(TARGET, "", "업로드 new.pdf")]
