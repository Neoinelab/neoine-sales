"""UploadAttachment - 같은 이름: ask/skip/replace 결과와 교체 권한."""

import unicodedata
from typing import TYPE_CHECKING

import pytest

from app.application.attachment.inputs import UploadOutcomeKind
from app.domain.attachment.errors import AttachmentNameTakenError, AttachmentReplaceForbiddenError
from app.domain.attachment.values import OnExists
from tests.support.expect import raises_with
from tests.unit.application.attachment_env import (
    BOSS,
    GONE_ADMIN,
    GONE_SALES,
    GONE_VIEWER,
    KIM,
    PARK,
    REPLACE_FORBIDDEN,
    TARGET,
)

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from tests.unit.application.attachment_env import AttachmentEnv


async def test_ask_conflicts_and_changes_nothing(attachment_env: AttachmentEnv) -> None:
    """ask로 같은 이름을 올리면 충돌 오류이고 아무것도 바뀌지 않는다.

    테스트 코드: AT-017
    """
    # given: "a.pdf"(내용 old)가 올라가 있고 그 상태를 기록한다
    original = await attachment_env.uploaded(KIM, "a.pdf", b"old")
    before = await attachment_env.snapshot()

    # when·then: ask로 같은 이름(내용 new)을 올리면 file-exists 오류다
    with raises_with(AttachmentNameTakenError, "같은 이름의 파일이 이미 있습니다: a.pdf"):
        await attachment_env.put(KIM, "a.pdf", b"new", on_exists=OnExists.ASK)

    # then: 첨부·이력·Deal 수정 시각이 그대로이고 내용은 old다
    assert await attachment_env.snapshot() == before
    assert attachment_env.content_of(original) == b"old"


async def test_ask_is_the_default_when_the_choice_is_not_made(
    attachment_env: AttachmentEnv,
) -> None:
    """선택을 생략하면 ask처럼 충돌 오류다.

    테스트 코드: AT-002
    """
    # given: "a.pdf"가 올라가 있다
    await attachment_env.uploaded(KIM, "a.pdf", b"old")

    # when·then: on_exists 없이 같은 이름을 올리면 충돌 오류다
    with pytest.raises(AttachmentNameTakenError):
        await attachment_env.put(KIM, "a.pdf", b"new")


async def test_skip_returns_no_attachment_and_changes_nothing(
    attachment_env: AttachmentEnv,
) -> None:
    """skip으로 같은 이름을 올리면 skipped이고 아무것도 바뀌지 않는다.

    테스트 코드: AT-018
    """
    # given: "a.pdf"(내용 old)가 올라가 있고 그 상태를 기록한다
    await attachment_env.uploaded(KIM, "a.pdf", b"old")
    before = await attachment_env.snapshot()

    # when: skip으로 같은 이름(내용 new)을 올린다
    outcome = await attachment_env.put(KIM, "a.pdf", b"new", on_exists=OnExists.SKIP)

    # then: 건너뜀이고 첨부는 없으며 저장 상태가 그대로다
    assert outcome.kind is UploadOutcomeKind.SKIPPED
    assert outcome.attachment is None
    assert await attachment_env.snapshot() == before


async def test_replace_keeps_the_id_and_swaps_content_description_and_time(
    attachment_env: AttachmentEnv,
) -> None:
    """replace는 같은 id를 두고 내용·설명·mime·업로드 시각을 바꾼다.

    테스트 코드: AT-019
    """
    # given: "a.pdf"가 올라가 있다
    original = await attachment_env.uploaded(KIM, "a.pdf", b"old")

    # when: 새 내용·설명·mime으로 replace 업로드한다
    outcome = await attachment_env.put(
        KIM,
        "a.pdf",
        b"newer content",
        on_exists=OnExists.REPLACE,
        description="새 설명",
        mime="text/plain",
    )

    # then: 교체 결과이고 id가 같으며 설명·크기(13)·mime·업로드·수정 시각이 새 값이다
    replaced = outcome.attachment
    now = attachment_env.env.clock.now()
    assert outcome.kind is UploadOutcomeKind.REPLACED
    assert replaced.id == original.id
    assert (replaced.description, replaced.size, replaced.mime) == ("새 설명", 13, "text/plain")
    assert replaced.uploaded_at == replaced.updated_at == now
    assert replaced.created_at == original.created_at
    # then: 생성 시각은 그대로이고 저장소 행도 갱신되며 행은 한 건이다
    assert (await attachment_env.stored(original.id)).size == 13
    assert len(await attachment_env.rows()) == 1


async def test_replace_writes_the_new_content_and_removes_the_old_disk_file(
    attachment_env: AttachmentEnv,
) -> None:
    """replace하면 새 내용 파일이 저장되고 이전 디스크 파일이 지워진다.

    테스트 코드: AT-019
    """
    # given: "a.pdf"(내용 old)가 올라가 있다
    original = await attachment_env.uploaded(KIM, "a.pdf", b"old")

    # when: replace로 새 내용을 올린다
    outcome = await attachment_env.put(KIM, "a.pdf", b"new", on_exists=OnExists.REPLACE)

    # then: 이전 파일은 없고 새 파일에 새 내용이 있으며 키가 바뀌고 파일은 하나뿐이다
    assert attachment_env.content_of(original) is None
    assert attachment_env.content_of(outcome.attachment) == b"new"
    assert outcome.attachment.storage_key != original.storage_key
    assert attachment_env.storage.file_count() == 1


async def test_replace_records_one_replace_entry_and_touches_the_deal(
    attachment_env: AttachmentEnv,
) -> None:
    """replace는 "교체" 이력 1건을 남기고 Deal 수정 시각을 바꾼다.

    테스트 코드: AT-019
    """
    # given: "a.pdf"가 올라가 있다
    await attachment_env.uploaded(KIM, "a.pdf", b"old")

    # when: replace로 같은 이름을 올린다
    await attachment_env.put(KIM, "a.pdf", b"new", on_exists=OnExists.REPLACE)

    # then: 이력은 "업로드 a.pdf"에 이어 "교체 a.pdf" 한 건이 더해진다
    assert await attachment_env.history() == [
        (TARGET, "", "업로드 a.pdf"),
        (TARGET, "", "교체 a.pdf"),
    ]
    # then: Deal 수정 시각이 요청 시각이다
    assert await attachment_env.deal_updated_at() == attachment_env.env.clock.now()


async def test_an_admin_replacing_takes_over_as_the_uploader(attachment_env: AttachmentEnv) -> None:
    """admin이 교체하면 업로더가 요청자로 바뀐다.

    테스트 코드: AT-022
    """
    # given: sales KIM이 올린 "a.pdf"
    await attachment_env.uploaded(KIM, "a.pdf", b"old")

    # when: admin이 replace로 올린다
    outcome = await attachment_env.put(BOSS, "a.pdf", b"new", on_exists=OnExists.REPLACE)

    # then: 첨부 업로더와 교체 이력 변경자가 admin이다
    assert outcome.attachment.uploaded_by == BOSS.user_id
    # then: 교체 이력의 변경자가 admin이다
    (_, replaced) = await attachment_env.entries()
    assert replaced.changed_by == BOSS.user_id


async def test_the_name_is_compared_after_nfc_normalization(attachment_env: AttachmentEnv) -> None:
    """이름은 NFC로 정규화해 비교한다.

    테스트 코드: AT-021
    """
    # given: NFC "한글.pdf"가 올라가 있고 NFD 표기를 준비한다
    await attachment_env.uploaded(KIM, "한글.pdf", b"old")
    decomposed = unicodedata.normalize("NFD", "한글.pdf")

    # when·then: NFD 이름을 ask로 올리면 충돌 오류다
    with pytest.raises(AttachmentNameTakenError):
        await attachment_env.put(KIM, decomposed, b"new")
    # when: 같은 NFD 이름을 replace로 올린다
    outcome = await attachment_env.put(KIM, decomposed, b"new", on_exists=OnExists.REPLACE)

    # then: 교체되고 저장된 이름은 NFC "한글.pdf"다
    assert outcome.kind is UploadOutcomeKind.REPLACED
    assert outcome.attachment.file_name.value == "한글.pdf"


@pytest.mark.parametrize(
    ("uploader", "requester"),
    [
        (KIM, KIM),
        (KIM, BOSS),
        (BOSS, BOSS),
        (GONE_SALES, KIM),
        (GONE_SALES, BOSS),
    ],
)
async def test_replace_is_allowed_for_the_uploader_an_admin_and_for_sales_of_a_resigned_sales_file(
    attachment_env: AttachmentEnv, uploader: Actor, requester: Actor
) -> None:
    """본인·admin·퇴사 sales 파일의 다른 sales는 교체할 수 있다.

    테스트 코드: AT-022
    """
    # given: 업로더가 올린 "a.pdf"
    original = await attachment_env.seed(uploader, "a.pdf", b"old")

    # when: 요청자가 replace로 올린다
    outcome = await attachment_env.put(
        requester,
        "a.pdf",
        b"new",
        on_exists=OnExists.REPLACE,
    )

    # then: 교체되고 같은 id이며 새 내용이 저장된다
    assert outcome.kind is UploadOutcomeKind.REPLACED
    assert outcome.attachment.id == original.id
    assert attachment_env.content_of(outcome.attachment) == b"new"


@pytest.mark.parametrize(
    ("uploader", "requester"),
    [
        (KIM, PARK),
        (BOSS, KIM),
        (GONE_ADMIN, KIM),
        (GONE_VIEWER, KIM),
    ],
)
async def test_replace_by_someone_who_may_not_delete_the_file_is_forbidden_and_changes_nothing(
    attachment_env: AttachmentEnv, uploader: Actor, requester: Actor
) -> None:
    """다른 재직 sales·퇴사 admin 파일 등은 교체가 거절되고 아무것도 바뀌지 않는다.

    테스트 코드: AT-023
    """
    # given: 업로더의 "a.pdf"와 현재 상태
    await attachment_env.seed(uploader, "a.pdf", b"old")
    before = await attachment_env.snapshot()

    # when·then: 권한 없는 요청자가 replace로 올리면 교체 권한 오류다
    with raises_with(AttachmentReplaceForbiddenError, REPLACE_FORBIDDEN):
        await attachment_env.put(
            requester,
            "a.pdf",
            b"new",
            on_exists=OnExists.REPLACE,
        )

    # then: 저장 상태가 그대로다
    assert await attachment_env.snapshot() == before


async def test_ask_by_another_sales_is_a_conflict_not_a_permission_error(
    attachment_env: AttachmentEnv,
) -> None:
    """다른 sales의 ask는 권한 오류가 아니라 충돌 오류다.

    테스트 코드: AT-023
    """
    # given: KIM이 올린 "a.pdf"
    await attachment_env.uploaded(KIM, "a.pdf", b"old")

    # when·then: 다른 sales PARK이 ask로 올리면 충돌 오류다
    with pytest.raises(AttachmentNameTakenError):
        await attachment_env.put(PARK, "a.pdf", b"new", on_exists=OnExists.ASK)


async def test_skip_by_another_sales_is_allowed_whoever_owns_the_file(
    attachment_env: AttachmentEnv,
) -> None:
    """다른 sales의 skip은 건너뜀으로 끝난다.

    테스트 코드: AT-023
    """
    # given: KIM이 올린 "a.pdf"
    await attachment_env.uploaded(KIM, "a.pdf", b"old")

    # when: 다른 sales PARK이 skip으로 올린다
    outcome = await attachment_env.put(PARK, "a.pdf", b"new", on_exists=OnExists.SKIP)

    # then: 건너뜀이다
    assert outcome.kind is UploadOutcomeKind.SKIPPED
