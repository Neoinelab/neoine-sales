"""DeleteAttachment: 판정 순서 404 -> 권한 403, 행·파일 삭제, 이력, Deal 수정 시각."""

import logging
from typing import TYPE_CHECKING

import pytest

from app.application.attachment.delete_attachment import DeleteAttachment
from app.domain.attachment.errors import AttachmentDeleteForbiddenError, AttachmentNotFoundError
from app.domain.attachment.values import AttachmentId
from tests.fakes.commit_failure import COMMIT_FAILED, commit_failing_factory
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.attachment_env import (
    BOSS,
    DELETE_FORBIDDEN,
    GONE_ADMIN,
    GONE_SALES,
    GONE_VIEWER,
    KIM,
    NOT_FOUND,
    PARK,
    TARGET,
    VIEWER,
)

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from tests.unit.application.attachment_env import AttachmentEnv


async def test_the_uploader_deletes_the_row_and_the_disk_file(
    attachment_env: AttachmentEnv,
) -> None:
    """업로더가 지우면 행과 디스크 파일이 사라진다.

    테스트 코드: AT-036
    """
    # given: KIM이 올린 "a.pdf"
    attachment = await attachment_env.uploaded(KIM, "a.pdf", b"data")

    # when: KIM이 지운다
    await attachment_env.delete.execute(attachment.id, KIM)

    # then: 행은 조회되지 않고 디스크 파일도 없다
    with pytest.raises(AttachmentNotFoundError):
        await attachment_env.stored(attachment.id)
    assert attachment_env.content_of(attachment) is None
    assert attachment_env.storage.file_count() == 0


async def test_the_delete_is_recorded_in_the_deal_history_by_the_requester(
    attachment_env: AttachmentEnv,
) -> None:
    """삭제는 요청자를 변경자로 하는 "삭제 <이름>" 이력을 남긴다.

    테스트 코드: AT-036
    """
    # given: KIM이 올린 "a.pdf"이고 시계가 60초 흐른다
    attachment = await attachment_env.uploaded(KIM, "a.pdf")
    attachment_env.env.clock.advance(60)

    # when: admin이 지운다
    await attachment_env.delete.execute(attachment.id, BOSS)

    # then: 이력은 "업로드 a.pdf"에 이어 "삭제 a.pdf"다
    assert await attachment_env.history() == [
        (TARGET, "", "업로드 a.pdf"),
        (TARGET, "", "삭제 a.pdf"),
    ]
    # then: 삭제 이력의 변경자는 admin이고 시각은 요청 시각이다
    deleted = (await attachment_env.entries())[-1]
    assert deleted.changed_by == BOSS.user_id
    assert deleted.changed_at == attachment_env.env.clock.now()


async def test_the_deal_modification_time_becomes_the_delete_time(
    attachment_env: AttachmentEnv,
) -> None:
    """삭제하면 Deal 수정 시각이 요청 시각이 된다.

    테스트 코드: AT-036
    """
    # given: KIM이 올린 "a.pdf"이고 시계가 60초 흐른다
    attachment = await attachment_env.uploaded(KIM, "a.pdf")
    attachment_env.env.clock.advance(60)

    # when: KIM이 지운다
    await attachment_env.delete.execute(attachment.id, KIM)

    # then: Deal 수정 시각이 삭제 요청 시각이다
    assert await attachment_env.deal_updated_at() == attachment_env.env.clock.now()


async def test_only_the_named_file_is_removed(attachment_env: AttachmentEnv) -> None:
    """지정한 파일만 지워지고 다른 파일은 남는다.

    테스트 코드: AT-036
    """
    # given: KIM이 올린 "gone.pdf"와 "kept.pdf"
    gone = await attachment_env.uploaded(KIM, "gone.pdf", b"1")
    kept = await attachment_env.uploaded(KIM, "kept.pdf", b"2")

    # when: "gone.pdf"를 지운다
    await attachment_env.delete.execute(gone.id, KIM)

    # then: 행은 "kept.pdf"뿐이고 그 디스크 내용이 그대로다
    assert [a.id for a in await attachment_env.rows()] == [kept.id]
    assert attachment_env.content_of(kept) == b"2"


@pytest.mark.parametrize(
    ("uploader", "requester"),
    [
        (KIM, KIM),
        (KIM, BOSS),
        (BOSS, BOSS),
        (GONE_SALES, KIM),
        (GONE_ADMIN, BOSS),
        (GONE_VIEWER, BOSS),
    ],
)
async def test_delete_is_allowed_for_the_uploader_admins_and_sales_of_a_resigned_sales_file(
    attachment_env: AttachmentEnv, uploader: Actor, requester: Actor
) -> None:
    """업로더·admin·퇴사 sales 파일의 sales는 지울 수 있다.

    테스트 코드: AT-037
    """
    # given: 업로더가 올린 "a.pdf"
    attachment = await attachment_env.seed(uploader, "a.pdf")

    # when: 요청자가 지운다
    await attachment_env.delete.execute(attachment.id, requester)

    # then: 첨부 행이 없다
    assert await attachment_env.rows() == []


@pytest.mark.parametrize(
    ("uploader", "requester"),
    [
        (KIM, PARK),
        (BOSS, KIM),
        (GONE_ADMIN, KIM),
        (GONE_VIEWER, KIM),
        (KIM, VIEWER),
        (VIEWER, VIEWER),
    ],
)
async def test_delete_by_someone_without_the_right_is_forbidden_and_keeps_everything(
    attachment_env: AttachmentEnv, uploader: Actor, requester: Actor
) -> None:
    """다른 재직 sales·퇴사 admin 파일 등은 삭제가 거절되고 아무것도 바뀌지 않는다.

    테스트 코드: AT-037
    """
    # given: 업로더의 "a.pdf"와 현재 상태
    attachment = await attachment_env.seed(uploader, "a.pdf", b"keep")
    before = await attachment_env.snapshot()

    # when·then: 권한 없는 요청자가 지우면 삭제 권한 오류다
    with raises_with(AttachmentDeleteForbiddenError, DELETE_FORBIDDEN):
        await attachment_env.delete.execute(attachment.id, requester)

    # then: 저장 상태와 디스크 내용이 그대로다
    assert await attachment_env.snapshot() == before
    assert attachment_env.content_of(attachment) == b"keep"


async def test_an_unknown_id_is_not_found_whoever_asks(attachment_env: AttachmentEnv) -> None:
    """없는 id의 삭제는 누가 해도 첨부 없음 오류다.

    테스트 코드: AT-038
    """
    # given: 존재하지 않는 첨부 id
    missing = AttachmentId(new_id())

    # when·then: 각 역할이 지우면 첨부 없음 오류다
    for actor in (KIM, PARK, BOSS, VIEWER):
        with raises_with(AttachmentNotFoundError, NOT_FOUND):
            await attachment_env.delete.execute(missing, actor)


async def test_deleting_twice_is_not_found_the_second_time(attachment_env: AttachmentEnv) -> None:
    """이미 지운 첨부를 다시 지우면 첨부 없음 오류다.

    테스트 코드: AT-038
    """
    # given: 이미 지운 첨부
    attachment = await attachment_env.uploaded(KIM, "a.pdf")
    await attachment_env.delete.execute(attachment.id, KIM)

    # when·then: 다시 지우면 첨부 없음 오류다
    with raises_with(AttachmentNotFoundError, NOT_FOUND):
        await attachment_env.delete.execute(attachment.id, KIM)


async def test_the_row_is_deleted_even_when_the_disk_file_cannot_be_removed(
    attachment_env: AttachmentEnv, caplog: pytest.LogCaptureFixture
) -> None:
    """디스크 파일을 지우지 못해도 행은 지워지고 경고 로그가 남는다.

    테스트 코드: AT-039
    """
    # given: "a.pdf"가 있고 디스크 삭제가 실패하게 한다
    attachment = await attachment_env.uploaded(KIM, "a.pdf", b"stuck")
    attachment_env.storage.fail_deletes = True
    caplog.set_level(logging.WARNING)

    # when: KIM이 지운다
    await attachment_env.delete.execute(attachment.id, KIM)

    # then: 행이 없고 경고 로그가 있으며 이력에 "삭제 a.pdf"가 남는다
    with pytest.raises(AttachmentNotFoundError):
        await attachment_env.stored(attachment.id)
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert await attachment_env.history() == [
        (TARGET, "", "업로드 a.pdf"),
        (TARGET, "", "삭제 a.pdf"),
    ]


async def test_the_row_is_deleted_when_no_storage_location_is_configured(
    attachment_env: AttachmentEnv,
) -> None:
    """저장 위치 설정이 없어도 행은 지워진다.

    테스트 코드: AT-039
    """
    # given: "a.pdf"가 있고 저장 위치 설정이 없다
    attachment = await attachment_env.uploaded(KIM, "a.pdf")
    await attachment_env.remove_storage_settings()

    # when: KIM이 지운다
    await attachment_env.delete.execute(attachment.id, KIM)

    # then: 첨부 행이 없다
    assert await attachment_env.rows() == []


async def test_a_failed_commit_keeps_the_row_and_the_disk_file(
    attachment_env: AttachmentEnv,
) -> None:
    """커밋이 실패하면 행과 디스크 파일이 남는다.

    테스트 코드: AT-039
    """
    # given: "a.pdf"와 커밋만 실패하는 삭제 유스케이스
    attachment = await attachment_env.uploaded(KIM, "a.pdf", b"data")
    env = attachment_env.env
    broken = DeleteAttachment(commit_failing_factory(env.uow), env.clock, attachment_env.storage)
    before = await attachment_env.snapshot()

    # when·then: 지우면 커밋 실패 오류다
    with raises_with(RuntimeError, COMMIT_FAILED):
        await broken.execute(attachment.id, KIM)

    # then: 저장 상태와 디스크 내용이 그대로다
    assert await attachment_env.snapshot() == before
    assert attachment_env.content_of(attachment) == b"data"
