"""첨부 유스케이스 단위 테스트의 공용 환경(P2b R2): Deal 하나, 저장 위치, 요청자들, 유스케이스 묶음.

이 모듈은 첨부 유스케이스를 모듈 수준에서 가져온다. 그래서 `conftest.py`의 `attachment_env`
fixture가 사용 시점에 가져온다(구현이 없어도 다른 테스트의 수집이 막히지 않는다).

요청자(Actor)는 role이 있다: 교체·삭제 권한이 업로더 본인·퇴사한 sales의 파일·admin으로 갈린다.
퇴사한 업로더는 role별로 하나씩 둔다(GONE_*): 같은 sales가 퇴사한 sales의 파일만 대신 지울 수 있다.
디스크 파일은 `FakeFileStorage`가 가진다(`<root>/<deal_code>/<저장 키>`).
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final, cast

from app.application.attachment.delete_attachment import DeleteAttachment
from app.application.attachment.download_attachment import DownloadAttachment
from app.application.attachment.get_attachment import GetAttachment
from app.application.attachment.inputs import UploadAttachmentInput
from app.application.attachment.list_attachments import ListAttachments
from app.application.attachment.upload_attachment import UploadAttachment
from app.application.deal.inputs import Actor
from app.application.ports.file_storage import StoredFileLocation
from app.domain.attachment.values import OnExists
from app.domain.auth.principal import Role
from app.domain.storage.path import StoragePath
from tests.factories_attachment import make_attachment
from tests.factories_auth import make_resigned_user, make_user
from tests.fakes.file_storage import BytesSource
from tests.fakes.storage_settings_repository import FakeStorageSettingsRepository
from tests.support.auth_seed import seed_storage
from tests.support.user_ids import uid

if TYPE_CHECKING:
    import builtins

    from app.application.deal.dto import DealView
    from app.domain.attachment.entities import Attachment
    from app.domain.attachment.values import AttachmentId
    from app.domain.deal.history import DealHistoryEntry
    from tests.fakes.file_storage import FakeFileStorage
    from tests.unit.application.deal_env import DealEnv

ROOT_PATH: Final = "/data/neoine-sales/files"
KIM = Actor(user_id=uid("kim"), role=Role.SALES)
PARK = Actor(user_id=uid("park"), role=Role.SALES)
BOSS = Actor(user_id=uid("boss"), role=Role.ADMIN)
VIEWER = Actor(user_id=uid("viewer"), role=Role.USER)
GONE_SALES = Actor(user_id=uid("gone-sales"), role=Role.SALES)  # 퇴사한 sales(업로더 역할만)
GONE_ADMIN = Actor(user_id=uid("gone-admin"), role=Role.ADMIN)
GONE_VIEWER = Actor(user_id=uid("gone-viewer"), role=Role.USER)
ACTIVE: Final = (KIM, PARK, BOSS, VIEWER)
RESIGNED: Final = (GONE_SALES, GONE_ADMIN, GONE_VIEWER)
NOT_FOUND: Final = "첨부 파일을 찾을 수 없습니다."
CONTENT_MISSING: Final = "첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요."
DELETE_FORBIDDEN: Final = "본인이 올린 파일만 삭제할 수 있습니다."
REPLACE_FORBIDDEN: Final = "본인이 올린 파일만 교체할 수 있습니다."
DEAL_NOT_FOUND: Final = "Deal을 찾을 수 없습니다."
TARGET: Final = "첨부 파일"


@dataclass
class AttachmentEnv:
    env: DealEnv
    deal: DealView
    storage: FakeFileStorage
    root: StoragePath
    upload: UploadAttachment
    delete: DeleteAttachment
    download: DownloadAttachment
    list: ListAttachments
    get: GetAttachment

    @property
    def code(self) -> str:
        return self.deal.item.deal.id.value

    def make_input(
        self,
        name: str | None = "a.pdf",
        data: bytes = b"hello",
        **overrides: Any,  # noqa: ANN401 - UploadAttachmentInput 필드를 그대로 넘긴다
    ) -> UploadAttachmentInput:
        """업로드 입력. name이 None이면 파일 파트가 없다. declared_size 기본은 data 길이."""
        values: dict[str, Any] = {
            "file_name": name,
            "declared_size": None if name is None else len(data),
            "mime": "application/pdf",
            "description": "",
            "on_exists": OnExists.ASK,
            "source": None if name is None else BytesSource(data),
            **overrides,
        }
        return UploadAttachmentInput(**values)

    async def put(
        self,
        actor: Actor = KIM,
        name: str | None = "a.pdf",
        data: bytes = b"hello",
        *,
        code: str | None = None,
        advance: int = 60,
        **overrides: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401 - UploadOutcome
        """업로드 유스케이스를 부른다(기본은 시계가 60초 흐른 뒤라 시각이 서로 다르다)."""
        self.env.clock.advance(advance)
        return await self.upload.execute(
            self.code if code is None else code, self.make_input(name, data, **overrides), actor
        )

    async def uploaded(
        self, actor: Actor = KIM, name: str = "a.pdf", data: bytes = b"hello"
    ) -> Attachment:
        """업로드해서 새 파일이 만들어진 첨부(outcome이 uploaded가 아니면 실패)."""
        outcome = await self.put(actor, name, data)
        assert outcome.attachment is not None
        return cast("Attachment", outcome.attachment)

    async def seed(
        self, actor: Actor = KIM, name: str = "a.pdf", data: bytes = b"hello", *, at: int = 0
    ) -> Attachment:
        """유스케이스를 거치지 않고 디스크 파일과 행을 직접 둔다(퇴사한 업로더의 파일 등)."""
        attachment = make_attachment(
            self.env.clock.now() + timedelta(seconds=at),
            deal_code=self.deal.item.deal.id,
            name=name,
            size=len(data),
            uploaded_by=actor.user_id,
        )
        await self.storage.save(
            self.root,
            StoredFileLocation(deal_code=attachment.deal_code, key=attachment.storage_key),
            BytesSource(data),
            max_bytes=len(data),
        )
        async with self.env.uow_factory() as uow:
            await uow.attachments.add(attachment)
            await uow.commit()
        return attachment

    async def stored(self, attachment_id: AttachmentId) -> Attachment:
        return await self.env.uow.attachments.get(attachment_id)

    async def rows(self) -> builtins.list[Attachment]:
        return list(await self.env.uow.attachments.list_by_deal(self.deal.item.deal.id))

    def content_of(self, attachment: Attachment) -> bytes | None:
        """디스크에 있는 그 첨부의 내용(없으면 None)."""
        location = StoredFileLocation(deal_code=attachment.deal_code, key=attachment.storage_key)
        return self.storage.contents_of(self.root, location)

    async def entries(self) -> builtins.list[DealHistoryEntry]:
        """첨부 이력(category=attachment)을 오래된 순서로."""
        found = await self.env.uow.deal_history.list(self.deal.item.deal.id)
        return [e for e in reversed(found) if str(e.draft.category) == "attachment"]

    async def history(self) -> builtins.list[tuple[str, str, str]]:
        """첨부 이력의 (target, before, after)를 오래된 순서로."""
        return [(e.draft.target, e.draft.before, e.draft.after) for e in await self.entries()]

    async def remove_storage_settings(self) -> None:
        """저장 위치 설정이 없는 상태로 만든다(최초 설정 전이나 DB에서 지워진 상황)."""
        async with self.env.uow_factory() as uow:
            fake = uow.storage_settings
            assert isinstance(fake, FakeStorageSettingsRepository)
            fake._items.clear()
            await uow.commit()

    async def snapshot(self) -> tuple[Any, ...]:
        """첨부 상태 전체(행, 디스크 파일 수, 이력, Deal 수정 시각)를 비교할 수 있게 담는다."""
        rows = [
            (
                a.id,
                a.file_name.value,
                a.description,
                a.size,
                a.mime,
                a.storage_key,
                a.uploaded_by,
                a.uploaded_at,
                a.updated_at,
            )
            for a in await self.rows()
        ]
        contents = sorted(self.storage._files.items())
        return (rows, contents, await self.history(), await self.deal_updated_at())

    async def deal_updated_at(self) -> Any:  # noqa: ANN401 - datetime
        return (await self.env.uow.deals.get(self.deal.item.deal.id)).updated_at


async def prepare_users(env: DealEnv) -> None:
    """요청자 사용자 행을 role대로 둔다(퇴사자는 퇴사 처리된 행). 준비용 commit은 0으로 되돌린다."""
    async with env.uow_factory() as active:
        for actor, name in (
            (KIM, "kim"),
            (PARK, "park"),
            (BOSS, "boss"),
            (VIEWER, "viewer"),
        ):
            await active.users.add(make_user(name, actor.role, entity_id=actor.user_id))
        for actor, name in (
            (GONE_SALES, "gone-sales"),
            (GONE_ADMIN, "gone-admin"),
            (GONE_VIEWER, "gone-viewer"),
        ):
            await active.users.add(make_resigned_user(name, actor.role, entity_id=actor.user_id))
        await active.commit()
    await seed_storage(env.uow_factory, ROOT_PATH)
    env.uow.commits = 0


def build_attachment_env(env: DealEnv, deal: DealView) -> AttachmentEnv:
    factory, clock, storage = env.uow_factory, env.clock, env.storage
    return AttachmentEnv(
        env=env,
        deal=deal,
        storage=storage,
        root=StoragePath.parse(ROOT_PATH),
        upload=UploadAttachment(factory, clock, storage),
        delete=DeleteAttachment(factory, clock, storage),
        download=DownloadAttachment(factory, storage),
        list=ListAttachments(factory),
        get=GetAttachment(factory),
    )
