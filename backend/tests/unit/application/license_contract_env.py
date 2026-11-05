"""라이선스 계약 유스케이스 단위 테스트의 공용 환경.

Deal 환경 위에 계약·첨부 유스케이스를 조립하고 준비 도우미(Won Deal, 계약·첨부 직접 저장,
파일 확인)를 둔다.

이 모듈은 구현을 모듈 수준에서 가져온다. 그래서 `conftest.py`의 `contract_env` fixture가 사용
시점에 가져온다(구현이 없어도 다른 테스트의 수집이 막히지 않는다). 요청자는 첨부 환경과 같다
(KIM·PARK sales, BOSS admin, VIEWER user, 퇴사한 GONE_SALES). 준비용 commit은 커밋 횟수 단언에
섞이지 않도록 0으로 되돌린다.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from app.application.deal_action.inputs import DealActionInput, StatusChangeInput
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.license_contract.delete_license_contract import DeleteLicenseContract
from app.application.license_contract.end_license_contract import EndLicenseContract
from app.application.license_contract.get_license_contract import GetLicenseContract
from app.application.license_contract.inputs import LicenseIssueInput
from app.application.license_contract.issue_license import IssueLicense
from app.application.license_contract.list_license_contracts import ListLicenseContracts
from app.application.license_contract.renew_license import RenewLicense
from app.application.license_contract.update_license_contract import UpdateLicenseContract
from app.application.license_contract_attachment.delete_contract_attachment import (
    DeleteContractAttachment,
)
from app.application.license_contract_attachment.download_contract_attachment import (
    DownloadContractAttachment,
)
from app.application.license_contract_attachment.list_contract_attachments import (
    ListContractAttachments,
)
from app.application.license_contract_attachment.upload_contract_attachment import (
    UploadContractAttachment,
)
from app.application.ports.license_contract_repository import LicenseContractQuery
from app.domain.attachment.values import OnExists
from app.domain.deal.sync import SyncResolution
from app.domain.license_contract.values import (
    ContractFields,
    InspectionCycle,
    LicenseTerm,
    TermUnit,
)
from tests.factories import make_deal_action_input
from tests.factories_attachment import make_attachment
from tests.factories_deal import SALES, make_create_input
from tests.factories_license_contract import make_contract, make_contract_attachment
from tests.fakes.file_storage import (
    BytesSource,
    contract_folder_of,
    contract_location,
    deal_folder_of,
    deal_location,
)
from tests.unit.application.attachment_env import (
    BOSS,
    GONE_SALES,
    KIM,
    PARK,
    ROOT_PATH,
    VIEWER,
    prepare_users,
)

if TYPE_CHECKING:
    import builtins

    from app.application.attachment.inputs import UploadAttachmentInput
    from app.application.deal.inputs import Actor
    from app.application.ports.file_storage import StoredFileLocation
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.attachment.entities import Attachment
    from app.domain.license_contract.attachment import ContractAttachment
    from app.domain.license_contract.entities import LicenseContract
    from app.domain.license_contract.values import LicenseContractId
    from app.domain.storage.path import StoragePath
    from tests.fakes.file_storage import FakeFileStorage
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
    from tests.unit.application.deal_env import DealEnv

__all__ = [
    "BOSS",
    "GONE_SALES",
    "KIM",
    "PARK",
    "ROOT_PATH",
    "VIEWER",
    "ContractEnv",
    "build_contract_env",
]

CLOSING = SyncResolution(revenue_amount=900_000_000, revenue_date=date(2026, 10, 20))
LEAVE_WON = SyncResolution(
    status_key="poc_completed"
)  # Forecast를 Won 밖으로 옮길 때 고르는 Status


@dataclass
class ContractEnv:
    env: DealEnv
    uow: FakeUnitOfWork
    uow_factory: UnitOfWorkFactory
    clock: FixedClock
    storage: FakeFileStorage
    root: StoragePath
    list: ListLicenseContracts
    get: GetLicenseContract
    update: UpdateLicenseContract
    issue: IssueLicense
    renew: RenewLicense
    end: EndLicenseContract
    delete: DeleteLicenseContract
    register_action: RegisterDealAction
    upload: UploadContractAttachment
    download: DownloadContractAttachment
    delete_file: DeleteContractAttachment
    list_files: ListContractAttachments

    # --- Deal 준비 ---

    async def won_deal(self, actor: Actor = KIM, **overrides: Any) -> str:  # noqa: ANN401
        """처음부터 Won으로 등록한 Deal(등록 경로가 계약을 자동으로 만든다). code를 돌려준다."""
        self.clock.advance(1)
        view = await self.env.register.execute(
            make_create_input(status_key="contract_completed", forecast_key="won", **overrides),
            actor,
        )
        return view.item.deal.id.value

    async def won_deal_without_contract(self, actor: Actor = KIM, **overrides: Any) -> str:  # noqa: ANN401
        """Won Deal에서 자동 생성된 계약을 지운 상태(계약을 직접 심는 준비). code를 돌려준다."""
        code = await self.won_deal(actor, **overrides)
        for contract in await self.contracts_of(code):
            await self.uow.license_contracts.delete(contract.id)
        return code

    async def open_deal(self, actor: Actor = SALES, **overrides: Any) -> str:  # noqa: ANN401
        """Won이 아닌 Deal(Status prospecting / Forecast pipeline)의 code."""
        view = await self.env.new_deal(actor=actor, **overrides)
        return view.item.deal.id.value

    async def forecast_of(self, code: str) -> str:
        from app.domain.deal.code import DealCode  # noqa: PLC0415

        return (await self.uow.deals.get(DealCode(code))).sync.forecast_key

    # --- 계약 준비·조회 ---

    async def contracts_of(self, code: str) -> builtins.list[LicenseContract]:
        """그 Deal의 계약 전부(id 오름차순)."""
        from app.domain.deal.code import DealCode  # noqa: PLC0415

        rows = await self.uow.license_contracts.search(LicenseContractQuery(limit=200))
        found = [r.contract for r in rows if r.contract.deal_code == DealCode(code)]
        return sorted(found, key=lambda c: c.id)

    async def seed_contract(self, code: str, **overrides: Any) -> LicenseContract:  # noqa: ANN401
        """유스케이스를 거치지 않고 계약을 직접 둔다(overrides는 `make_contract`와 같다)."""
        from app.domain.deal.code import DealCode  # noqa: PLC0415

        overrides.setdefault("by", KIM.user_id)
        contract = make_contract(deal_code=DealCode(code), now=self.clock.now(), **overrides)
        await self.uow.license_contracts.add(contract)
        return contract

    async def stored(self, contract_id: LicenseContractId) -> LicenseContract:
        return await self.uow.license_contracts.get(contract_id)

    def issue_input(
        self,
        start: date = date(2026, 1, 1),
        amount: int = 1,
        unit: str = "year",
        **fields: Any,  # noqa: ANN401 - tech_owner·inspection·note
    ) -> LicenseIssueInput:
        return LicenseIssueInput(
            fields=ContractFields(
                tech_owner=fields.get("tech_owner", ""),
                inspection=InspectionCycle(fields.get("inspection", "none")),
                note=fields.get("note", ""),
            ),
            start=start,
            term=LicenseTerm(amount=amount, unit=TermUnit(unit)),
        )

    # --- 첨부·파일 준비 ---

    def upload_input(
        self,
        name: str | None = "a.pdf",
        data: bytes = b"hello",
        **overrides: Any,  # noqa: ANN401
    ) -> UploadAttachmentInput:
        from app.application.attachment.inputs import UploadAttachmentInput  # noqa: PLC0415

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

    async def put_file(
        self,
        contract_id: LicenseContractId,
        actor: Actor = KIM,
        name: str | None = "a.pdf",
        data: bytes = b"hello",
        **overrides: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401 - UploadOutcome
        self.clock.advance(60)
        return await self.upload.execute(
            contract_id, self.upload_input(name, data, **overrides), actor
        )

    async def seed_file(
        self,
        contract: LicenseContract,
        actor: Actor = KIM,
        name: str = "a.pdf",
        data: bytes = b"hello",
        *,
        at: int = 0,
    ) -> ContractAttachment:
        """디스크 파일과 행을 직접 둔다(퇴사한 업로더의 파일 등)."""
        attachment = make_contract_attachment(
            contract,
            name=name,
            size=len(data),
            uploaded_by=actor.user_id,
            now=self.clock.now() + timedelta(seconds=at),
        )
        await self._write(contract_location(attachment.contract_id, attachment.storage_key), data)
        await self.uow.license_contract_attachments.add(attachment)
        return attachment

    async def seed_deal_file(
        self, code: str, name: str = "deal.pdf", data: bytes = b"deal"
    ) -> Attachment:
        """Deal 자체의 첨부(계약 첨부가 아님)를 같은 디렉터리에 둔다."""
        from app.domain.deal.code import DealCode  # noqa: PLC0415

        attachment = make_attachment(
            self.clock.now(),
            deal_code=DealCode(code),
            name=name,
            size=len(data),
            uploaded_by=KIM.user_id,
        )
        await self._write(deal_location(attachment.deal_code, attachment.storage_key), data)
        await self.uow.attachments.add(attachment)
        return attachment

    async def _write(self, location: StoredFileLocation, data: bytes) -> None:
        await self.storage.save(self.root, location, BytesSource(data), max_bytes=max(len(data), 1))

    def content_of(self, attachment: ContractAttachment | Attachment) -> bytes | None:
        """디스크의 그 첨부 내용(없으면 None). 계약 첨부는 계약 폴더, Deal 첨부는 Deal 폴더."""
        contract_id = getattr(attachment, "contract_id", None)
        if contract_id is not None:
            location = contract_location(contract_id, attachment.storage_key)
        else:
            location = deal_location(attachment.deal_code, attachment.storage_key)
        return self.storage.contents_of(self.root, location)

    def contract_folder_exists(self, contract_id: LicenseContractId) -> bool:
        return self.storage.folder_exists(self.root, contract_folder_of(contract_id))

    def deal_folder_exists(self, code: str) -> bool:
        from app.domain.deal.code import DealCode  # noqa: PLC0415

        return self.storage.folder_exists(self.root, deal_folder_of(DealCode(code)))

    async def files_of(self, contract_id: LicenseContractId) -> builtins.list[ContractAttachment]:
        return list(await self.uow.license_contract_attachments.list_by_contract(contract_id))

    async def all_file_rows(self) -> builtins.list[ContractAttachment]:
        return list(self.uow.license_contract_attachments._items.values())

    async def remove_storage_settings(self) -> None:
        """저장 위치 설정이 없는 상태로 만든다."""
        async with self.uow_factory() as active:
            active.storage_settings._items.clear()  # type: ignore[attr-defined]
            await active.commit()

    # --- Won 이탈 요청 도우미 ---

    async def leave_won_by_change(
        self, code: str, actor: Actor = KIM, *, delete_contracts: bool | None = None
    ) -> Any:  # noqa: ANN401 - ApplyChangeResult
        """목록 인라인 변경: Forecast를 commit으로 바꾼다(Status는 poc_completed로 함께)."""
        from app.application.deal.inputs import DealChangeInput  # noqa: PLC0415

        extra: dict[str, Any] = (
            {} if delete_contracts is None else {"delete_license_contracts": delete_contracts}
        )
        change = DealChangeInput(
            field="forecast_key", value="commit", resolution=LEAVE_WON, **extra
        )
        return await self.env.apply.execute(code, change, actor)

    async def leave_won_by_form(
        self, code: str, actor: Actor = KIM, *, delete_contracts: bool | None = None
    ) -> Any:  # noqa: ANN401 - DealView
        """Deal 폼 수정: Status·Forecast를 함께 Won 밖으로 바꾼다."""
        from app.application.deal.inputs import DealPatchInput  # noqa: PLC0415

        fields: dict[str, Any] = {"status_key": "poc_completed", "forecast_key": "commit"}
        extra: dict[str, Any] = (
            {} if delete_contracts is None else {"delete_license_contracts": delete_contracts}
        )
        patch = DealPatchInput(provided=frozenset(fields), **fields, **extra)
        return await self.env.update.execute(code, patch, actor)

    async def leave_won_by_action(
        self, code: str, actor: Actor = KIM, *, delete_contracts: bool | None = None
    ) -> Any:  # noqa: ANN401 - DealAction
        """Action 등록의 status_changes: Forecast를 commit으로 바꾼다."""
        self.clock.advance(60)
        change = StatusChangeInput(field="forecast_key", value="commit", resolution=LEAVE_WON)
        extra: dict[str, Any] = (
            {} if delete_contracts is None else {"delete_license_contracts": delete_contracts}
        )
        data = DealActionInput(content=make_deal_action_input(), status_changes=(change,), **extra)
        return await self.register_action.execute(code, data, actor)


async def build_contract_env(env: DealEnv) -> ContractEnv:
    from app.domain.storage.path import StoragePath  # noqa: PLC0415

    await prepare_users(env)  # 요청자 사용자 행과 저장 위치 설정(준비용 commit은 0으로 되돌린다)
    factory, clock, storage = env.uow_factory, env.clock, env.storage
    return ContractEnv(
        env=env,
        uow=env.uow,
        uow_factory=factory,
        clock=clock,
        storage=storage,
        root=StoragePath.parse(ROOT_PATH),
        list=ListLicenseContracts(factory),
        get=GetLicenseContract(factory),
        update=UpdateLicenseContract(factory, clock),
        issue=IssueLicense(factory, clock),
        renew=RenewLicense(factory, clock),
        end=EndLicenseContract(factory, clock),
        delete=DeleteLicenseContract(factory, storage),
        register_action=RegisterDealAction(factory, clock, storage),
        upload=UploadContractAttachment(factory, clock, storage),
        download=DownloadContractAttachment(factory, storage),
        delete_file=DeleteContractAttachment(factory, storage),
        list_files=ListContractAttachments(factory),
    )
