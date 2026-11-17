"""DeleteDeal과 첨부: 커밋 뒤 Deal 디렉터리 삭제, 실패는 경고 로그만, 삭제 영향 건수."""

import logging
from typing import TYPE_CHECKING

import pytest

from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.inputs import Actor
from app.application.ports.deal_repository import DealDeletionImpact
from app.domain.attachment.values import OnExists
from app.domain.auth.principal import Role
from app.domain.deal.errors import DealCodeMismatchError, DealDeleteForbiddenError
from tests.factories_deal import SALES
from tests.fakes.commit_failure import COMMIT_FAILED, commit_failing_factory
from tests.support.auth_seed import seed_user
from tests.support.expect import raises_with
from tests.unit.application.attachment_env import KIM, ROOT_PATH

if TYPE_CHECKING:
    from tests.unit.application.attachment_env import AttachmentEnv


async def _delete(attachment_env: AttachmentEnv, code: str | None = None) -> None:
    target = code or attachment_env.code
    await attachment_env.env.delete.execute(target, target, SALES)


async def test_deleting_the_deal_removes_its_attachment_rows_and_its_directory(
    attachment_env: AttachmentEnv,
) -> None:
    """저장 위치가 있으면 삭제 뒤 첨부 행과 그 Deal 폴더가 지워진다.

    테스트 코드: DD-060
    """
    # given: 첨부 파일 두 개가 올라간 Deal
    await attachment_env.uploaded(KIM, "a.pdf", b"1")
    await attachment_env.uploaded(KIM, "b.pdf", b"2")
    directory = f"{ROOT_PATH}/{attachment_env.code}"
    assert attachment_env.storage.entries(directory) != []

    # when: Deal을 삭제한다
    await _delete(attachment_env)

    # then: 첨부 행·Deal 폴더·파일이 모두 없다
    assert attachment_env.env.uow.attachments._items == {}
    assert not attachment_env.storage.dir_exists(directory)
    assert attachment_env.storage.file_count() == 0


async def test_other_deals_files_and_the_storage_root_stay(attachment_env: AttachmentEnv) -> None:
    """다른 Deal의 파일과 저장 위치 루트는 남는다.

    테스트 코드: DD-060
    """
    # given: Deal 두 건에 각각 첨부가 있다
    other = await attachment_env.env.new_deal()
    other_code = other.item.deal.id.value
    await attachment_env.uploaded(KIM, "a.pdf", b"mine")
    kept = await attachment_env.put(KIM, "b.pdf", b"theirs", code=other_code)

    # when: 한 Deal을 삭제한다
    await _delete(attachment_env)

    # then: 다른 Deal의 파일 내용과 루트가 남고 첨부 행은 그것뿐이다
    assert attachment_env.content_of(kept.attachment) == b"theirs"
    assert attachment_env.storage.dir_exists(ROOT_PATH)
    assert [a.id for a in attachment_env.env.uow.attachments._items.values()] == [
        kept.attachment.id
    ]


async def test_a_deal_without_files_is_deleted_without_trouble(
    attachment_env: AttachmentEnv,
) -> None:
    """파일이 없는 Deal도 문제없이 지워진다.

    테스트 코드: DD-060
    """
    # when: Deal을 삭제한다
    await _delete(attachment_env)

    # then: Deal이 지워진다
    assert attachment_env.env.uow.deals._items == {}


async def test_the_deal_is_deleted_even_when_its_directory_cannot_be_removed(
    attachment_env: AttachmentEnv, caplog: pytest.LogCaptureFixture
) -> None:
    """폴더를 지우지 못해도 Deal은 지워지고 경고 로그만 남는다.

    테스트 코드: DD-061
    """
    # given: 폴더 삭제가 실패하도록 한 저장소
    await attachment_env.uploaded(KIM, "a.pdf", b"stuck")
    attachment_env.storage.fail_deletes = True
    caplog.set_level(logging.WARNING)

    # when: Deal을 삭제한다
    await _delete(attachment_env)

    # then: Deal이 지워지고 code가 든 경고 로그가 있다
    assert attachment_env.env.uow.deals._items == {}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(attachment_env.code in r.getMessage() for r in warnings)


async def test_a_deal_is_deleted_without_a_storage_location_and_files_are_left_alone(
    attachment_env: AttachmentEnv,
) -> None:
    """저장 위치가 없으면 Deal만 지우고 파일은 건드리지 않는다.

    테스트 코드: DD-060
    """
    # given: 저장 위치가 설정되지 않은 환경과 이미 올라간 파일
    uploaded = await attachment_env.uploaded(KIM, "a.pdf", b"stays")
    await attachment_env.remove_storage_settings()

    # when: Deal을 삭제한다
    await _delete(attachment_env)

    # then: Deal은 지워지고 파일 내용은 그대로다
    assert attachment_env.env.uow.deals._items == {}
    assert attachment_env.content_of(uploaded) == b"stays"


async def test_a_refused_delete_does_not_touch_the_files(attachment_env: AttachmentEnv) -> None:
    """거절된 삭제(권한 없음·확인 code 불일치)는 파일을 건드리지 않는다.

    테스트 코드: DD-061
    """
    # given: 첨부가 있는 Deal, 다른 영업
    uploaded = await attachment_env.uploaded(KIM, "a.pdf", b"keep")
    stranger = await seed_user(attachment_env.env.uow_factory, "stranger")
    code = attachment_env.code
    # when: 권한 없이, 틀린 확인 code로 삭제한다
    with pytest.raises(DealDeleteForbiddenError):
        await attachment_env.env.delete.execute(code, code, Actor(stranger.id, Role.SALES))
    with pytest.raises(DealCodeMismatchError):
        await attachment_env.env.delete.execute(code, "wrong", SALES)

    # then: 파일 내용과 첨부 행이 그대로다
    assert attachment_env.content_of(uploaded) == b"keep"
    assert len(attachment_env.env.uow.attachments._items) == 1


async def test_a_failed_commit_keeps_the_deal_and_its_files(attachment_env: AttachmentEnv) -> None:
    """커밋이 실패하면 Deal과 파일이 모두 남는다.

    테스트 코드: DD-061
    """
    # given: 커밋이 실패하는 UoW와 첨부가 있는 Deal
    uploaded = await attachment_env.uploaded(KIM, "a.pdf", b"keep")
    env = attachment_env.env
    broken = DeleteDeal(commit_failing_factory(env.uow), env.clock, attachment_env.storage)

    # when: 삭제한다
    with raises_with(RuntimeError, COMMIT_FAILED):
        await broken.execute(attachment_env.code, attachment_env.code, SALES)

    # then: 파일 내용과 Deal이 그대로다
    assert attachment_env.content_of(uploaded) == b"keep"
    assert len(env.uow.deals._items) == 1


async def test_the_deletion_impact_counts_the_attachments_of_that_deal(
    attachment_env: AttachmentEnv,
) -> None:
    """삭제 영향의 첨부 건수는 그 Deal의 첨부 수다(다른 Deal 파일은 세지 않는다).

    테스트 코드: AT-040
    """
    # given: 첨부가 올라간 Deal
    other = await attachment_env.env.new_deal()
    await attachment_env.uploaded(KIM, "a.pdf")
    await attachment_env.uploaded(KIM, "b.pdf")
    await attachment_env.put(KIM, "c.pdf", code=other.item.deal.id.value)

    # when: 삭제 영향을 읽는다
    impact = await attachment_env.env.impact.execute(attachment_env.code)

    # then: 첨부 건수가 올린 수와 같다
    assert impact == DealDeletionImpact(
        history_count=3,
        action_count=0,
        attachment_count=2,
        license_contract_count=0,
        comment_count=0,
    )


async def test_the_impact_counts_a_replaced_file_once_and_drops_a_deleted_one(
    attachment_env: AttachmentEnv,
) -> None:
    """교체한 파일은 한 번만 세고 삭제한 파일은 세지 않는다.

    테스트 코드: AT-040
    """
    # given: 파일을 교체하고 다른 파일을 삭제했다
    first = await attachment_env.uploaded(KIM, "a.pdf")
    await attachment_env.put(KIM, "a.pdf", b"v2", on_exists=OnExists.REPLACE)
    second = await attachment_env.uploaded(KIM, "b.pdf")
    await attachment_env.delete.execute(second.id, KIM)

    # when: 삭제 영향을 읽는다
    impact = await attachment_env.env.impact.execute(attachment_env.code)

    # then: 첨부 건수가 1이다
    assert impact.attachment_count == 1
    assert first.id in attachment_env.env.uow.attachments._items
