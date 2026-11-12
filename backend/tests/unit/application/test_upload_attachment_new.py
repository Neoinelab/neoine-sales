"""UploadAttachment - 새 파일: 그대로 저장하고 행·이력·Deal 수정 시각을 남긴다."""

import re
from typing import TYPE_CHECKING

import pytest

from app.application.attachment.inputs import UploadOutcomeKind
from tests.fakes.file_storage import deal_location
from tests.unit.application.attachment_env import KIM, ROOT_PATH, TARGET

if TYPE_CHECKING:
    from tests.unit.application.attachment_env import AttachmentEnv


async def test_a_new_file_is_stored_byte_for_byte_and_recorded(
    attachment_env: AttachmentEnv,
) -> None:
    """새 파일을 올리면 내용 그대로 저장하고 첨부 행에 기록한다.

    테스트 코드: AT-001
    """
    # when: sales가 앞뒤 공백이 있는 설명과 함께 PDF를 올린다 (전제: 저장 위치가 설정된 Deal)
    outcome = await attachment_env.put(KIM, "견적서.pdf", b"%PDF-1.7 bytes", description=" 최종본 ")

    # then: 업로드 결과이고 이름·설명(공백 제거)·크기·mime·업로더·Deal이 요청대로다
    attachment = outcome.attachment
    assert outcome.kind is UploadOutcomeKind.UPLOADED
    assert attachment.file_name.value == "견적서.pdf"
    assert (attachment.description, attachment.size) == ("최종본", len(b"%PDF-1.7 bytes"))
    assert (attachment.mime, attachment.uploaded_by) == ("application/pdf", KIM.user_id)
    assert attachment.deal_code.value == attachment_env.code
    # then: 디스크 파일은 올린 바이트 그대로이고 저장소 행이 같은 키를 가리킨다
    assert attachment_env.content_of(attachment) == b"%PDF-1.7 bytes"
    assert (await attachment_env.stored(attachment.id)).storage_key == attachment.storage_key


async def test_the_upload_time_is_the_server_time_of_the_request(
    attachment_env: AttachmentEnv,
) -> None:
    """업로드·생성·수정 시각은 요청 시각(서버 시계)이다.

    테스트 코드: AT-004
    """
    # when: 파일을 올린다 (전제: 저장 위치가 설정된 Deal)
    outcome = await attachment_env.put(KIM, "a.pdf")

    # then: 세 시각이 모두 서버 시계의 현재 시각이다
    now = attachment_env.env.clock.now()
    assert outcome.attachment.uploaded_at == now
    assert outcome.attachment.created_at == outcome.attachment.updated_at == now


async def test_the_disk_file_is_named_by_a_random_key_not_by_the_original_name(
    attachment_env: AttachmentEnv,
) -> None:
    """디스크 파일은 원래 이름이 아니라 32자 16진수 키로 저장한다.

    테스트 코드: AT-001
    """
    # when: 공백이 든 한글 이름의 파일을 올린다 (전제: 저장 위치가 설정된 Deal)
    outcome = await attachment_env.put(KIM, "견적서 최종.pdf", b"x")

    # then: 키는 32자 소문자 16진수이고 Deal 폴더에는 그 키 파일 하나뿐이다
    key = outcome.attachment.storage_key
    assert re.fullmatch(r"[0-9a-f]{32}", key)
    assert attachment_env.storage.entries(f"{ROOT_PATH}/{attachment_env.code}") == [key]


async def test_every_upload_gets_its_own_key(attachment_env: AttachmentEnv) -> None:
    """업로드마다 다른 키로 저장된다.

    테스트 코드: AT-001
    """
    # when: 서로 다른 두 파일을 올린다 (전제: 저장 위치가 설정된 Deal)
    first = await attachment_env.uploaded(KIM, "a.pdf", b"1")
    second = await attachment_env.uploaded(KIM, "b.pdf", b"2")

    # then: 두 키가 다르고 각 내용이 그대로 저장된다
    assert first.storage_key != second.storage_key
    assert attachment_env.content_of(first) == b"1"
    assert attachment_env.content_of(second) == b"2"


async def test_the_size_is_the_number_of_bytes_actually_stored(
    attachment_env: AttachmentEnv,
) -> None:
    """선언 크기와 달라도 크기는 실제로 쓴 바이트 수다.

    테스트 코드: AT-004
    """
    # when: 선언 크기 3, 실제 10바이트를 올린다 (전제: 저장 위치가 설정된 Deal)
    outcome = await attachment_env.put(KIM, "a.bin", b"0123456789", declared_size=3)

    # then: 크기는 10이다
    assert outcome.attachment.size == 10


async def test_the_size_is_known_even_when_the_request_did_not_declare_one(
    attachment_env: AttachmentEnv,
) -> None:
    """선언 크기가 없어도 실제 바이트 수를 크기로 기록한다.

    테스트 코드: AT-004
    """
    # when: 선언 크기 없이 5바이트를 올린다 (전제: 저장 위치가 설정된 Deal)
    outcome = await attachment_env.put(KIM, "a.bin", b"abcde", declared_size=None)

    # then: 크기는 5다
    assert outcome.attachment.size == 5


async def test_an_empty_file_is_accepted(attachment_env: AttachmentEnv) -> None:
    """0바이트 파일도 올라간다.

    테스트 코드: AT-005
    """
    # when: 0바이트 파일을 올린다 (전제: 저장 위치가 설정된 Deal)
    outcome = await attachment_env.put(KIM, "empty.txt", b"")

    # then: 새 업로드이고 크기 0, 디스크 내용은 빈 바이트다
    assert outcome.kind is UploadOutcomeKind.UPLOADED
    assert outcome.attachment.size == 0
    assert attachment_env.content_of(outcome.attachment) == b""


@pytest.mark.parametrize("name", ["a.tar.gz", "README", ".bashrc", "한글 이름 (1).docx", "x" * 255])
async def test_ordinary_names_are_accepted(attachment_env: AttachmentEnv, name: str) -> None:
    """확장자 없음·이중 확장자·점으로 시작·255자 이름은 그대로 올라간다.

    테스트 코드: AT-005
    """
    # when: 해당 이름의 파일을 올린다 (전제: 저장 위치가 설정된 Deal)
    outcome = await attachment_env.put(KIM, name, b"x")

    # then: 저장된 이름이 올린 이름과 같다
    assert outcome.attachment.file_name.value == name


async def test_the_description_defaults_to_empty(attachment_env: AttachmentEnv) -> None:
    """설명을 생략하면 빈 문자열로 저장한다.

    테스트 코드: AT-002
    """
    # when: 설명 없이 올린다 (전제: 저장 위치가 설정된 Deal)
    outcome = await attachment_env.put(KIM, "a.pdf")

    # then: 설명은 빈 문자열이다
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
    """mime은 요청 값이고, 없거나 255자를 넘으면 octet-stream이다.

    테스트 코드: AT-004
    """
    # when: 주어진 Content-Type으로 올린다 (전제: 저장 위치가 설정된 Deal)
    outcome = await attachment_env.put(KIM, "a.bin", b"x", mime=sent)

    # then: 저장된 mime이 기대 값이다
    assert outcome.attachment.mime == stored


async def test_one_history_entry_records_the_upload(attachment_env: AttachmentEnv) -> None:
    """업로드는 Deal History에 "업로드 <이름>" 1건을 남긴다.

    테스트 코드: AT-003
    """
    # when: 파일을 올린다 (전제: 저장 위치가 설정된 Deal)
    await attachment_env.put(KIM, "a.pdf")

    # then: 첨부 파일 대상·변경 전 ""·변경 후 "업로드 a.pdf" 한 건이다
    assert await attachment_env.history() == [(TARGET, "", "업로드 a.pdf")]
    # then: 변경자는 요청자이고 시각은 요청 시각이다
    (entry,) = await attachment_env.entries()
    assert entry.changed_by == KIM.user_id
    assert entry.changed_at == attachment_env.env.clock.now()


async def test_the_deal_modification_time_becomes_the_upload_time(
    attachment_env: AttachmentEnv,
) -> None:
    """업로드하면 Deal 수정 시각이 요청 시각이 된다.

    테스트 코드: AT-003
    """
    # given: 업로드 전 Deal 수정 시각
    before = await attachment_env.deal_updated_at()

    # when: 파일을 올린다
    await attachment_env.put(KIM, "a.pdf")

    # then: Deal 수정 시각이 이전보다 늦은 요청 시각이다
    now = attachment_env.env.clock.now()
    assert before < now
    assert await attachment_env.deal_updated_at() == now


async def test_the_upload_is_committed(attachment_env: AttachmentEnv) -> None:
    """업로드는 커밋된다.

    테스트 코드: AT-003
    """
    # given: 업로드 전 커밋 횟수
    commits = attachment_env.env.uow.commits

    # when: 파일을 올린다
    await attachment_env.put(KIM, "a.pdf")

    # then: 커밋 횟수가 늘었다
    assert attachment_env.env.uow.commits > commits


async def test_the_same_name_in_another_deal_is_a_separate_file(
    attachment_env: AttachmentEnv,
) -> None:
    """다른 Deal의 같은 이름은 별개 파일이다.

    테스트 코드: AT-021
    """
    # given: 다른 Deal과 이 Deal에 올라간 "a.pdf"
    other = await attachment_env.env.new_deal()
    first = await attachment_env.uploaded(KIM, "a.pdf", b"first")

    # when: 다른 Deal에 같은 이름 "a.pdf"를 올린다
    second = await attachment_env.put(KIM, "a.pdf", b"second", code=other.item.deal.id.value)

    # then: 새 업로드이고 첨부 id가 다르며 두 파일의 내용이 각각 그대로다
    assert second.kind is UploadOutcomeKind.UPLOADED
    assert second.attachment.id != first.id
    assert attachment_env.content_of(first) == b"first"
    location = deal_location(other.item.deal.id, second.attachment.storage_key)
    assert attachment_env.storage.contents_of(attachment_env.root, location) == b"second"


async def test_names_that_differ_only_by_case_are_separate_files(
    attachment_env: AttachmentEnv,
) -> None:
    """대소문자만 다른 이름은 별개 파일이다.

    테스트 코드: AT-021
    """
    # given: "Report.PDF"가 올라가 있다
    await attachment_env.uploaded(KIM, "Report.PDF", b"1")

    # when: "report.pdf"를 올린다
    outcome = await attachment_env.put(KIM, "report.pdf", b"2")

    # then: 새 업로드이고 첨부는 두 건이다
    assert outcome.kind is UploadOutcomeKind.UPLOADED
    assert len(await attachment_env.rows()) == 2


@pytest.mark.parametrize("on_exists", ["replace", "skip"])
async def test_replace_and_skip_still_upload_when_no_file_has_that_name(
    attachment_env: AttachmentEnv, on_exists: str
) -> None:
    """같은 이름이 없으면 replace·skip도 새 업로드다.

    테스트 코드: AT-020
    """
    from app.domain.attachment.values import OnExists  # noqa: PLC0415

    # when: 같은 이름이 없는 파일을 replace 또는 skip으로 올린다 (전제: 첨부가 없는 Deal)
    outcome = await attachment_env.put(KIM, "new.pdf", b"x", on_exists=OnExists(on_exists))

    # then: 새 업로드이고 파일이 저장되며 이력은 "업로드 new.pdf" 한 건이다
    assert outcome.kind is UploadOutcomeKind.UPLOADED
    assert attachment_env.content_of(outcome.attachment) == b"x"
    assert await attachment_env.history() == [(TARGET, "", "업로드 new.pdf")]
