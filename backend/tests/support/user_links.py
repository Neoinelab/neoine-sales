"""사용자를 FK로 참조하는 행을 하나씩 만드는 도우미(퇴사/물리 삭제 분기와 has_links 검증용).

Fake와 SQL UoW 어느 쪽에나 쓴다. 참조 대상 사용자 외에 필요한 보조 사용자·고객·Deal은 함께 만든다.
LINK_KINDS가 users를 가리키는 FK 종류의 전부여야 한다(스키마 점검 테스트가 FK 집합과 대조한다).
Deal 모델 모듈은 사용 시점에 가져온다(사용자 테스트의 수집이 Deal 구현에 묶이지 않게 한다).
"""

from typing import TYPE_CHECKING, Final
from uuid import uuid4

from tests.factories import (
    NOW,
    later,
    make_deal,
    make_deal_action,
)
from tests.factories_action_type import attach_catalog_type, make_action_type
from tests.factories_auth import make_directory_settings, make_user
from tests.factories_catalog import make_label

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
    from app.domain.deal.entities import Deal
    from app.domain.user.entities import User
    from app.domain.user.value_objects import UserId

LINK_KINDS: Final = (
    "deal_owner",  # deals.owner_user_id
    "history_author",  # deal_history.changed_by_user_id
    "action_actor",  # deal_actions.actor_user_id
    "created_user",  # users.created_by_user_id (다른 사용자의 등록자)
    "directory_settings",  # directory_settings.updated_by_user_id
    "label_creator",  # bant_labels.created_by_user_id (직접 만든 Label의 생성자)
    "action_type_creator",  # action_types.created_by_user_id (직접 만든 Action 유형의 생성자)
    "storage_settings",  # storage_settings.updated_by_user_id (P2b: 저장 위치를 저장한 admin)
    "attachment_uploader",  # deal_attachments.uploaded_by_user_id (P2b: 첨부를 올린 사용자)
    "alert_settings",  # alert_settings.updated_by_user_id (P3: 경고 기준을 저장한 admin)
    "forecast_snapshot",  # forecast_snapshot_cells.owner_user_id (P6 R2: 스냅숏에만 남은 담당자)
    "report_owner",  # reports.owner_user_id (Reports 3단계: 리포트를 만든 사람)
    "report_editor",  # reports.updated_by_user_id (Reports 3단계: 리포트를 마지막으로 수정한 사람)
    "meeting_author",  # partner_meetings.created_by_user_id (파트너 Activity: 미팅을 기록한 사람)
)


# LINK_KINDS 각각이 가리키는 (테이블, 컬럼). 세션 FK는 삭제 때 행을 먼저 지우므로 연결이 아니다.
LINK_COLUMNS: Final = {
    "deal_owner": ("deals", "owner_user_id"),
    "history_author": ("deal_history", "changed_by_user_id"),
    "action_actor": ("deal_actions", "actor_user_id"),
    "created_user": ("users", "created_by_user_id"),
    "directory_settings": ("directory_settings", "updated_by_user_id"),
    "label_creator": ("bant_labels", "created_by_user_id"),
    "action_type_creator": ("action_types", "created_by_user_id"),
    "storage_settings": ("storage_settings", "updated_by_user_id"),
    "attachment_uploader": ("deal_attachments", "uploaded_by_user_id"),
    "alert_settings": ("alert_settings", "updated_by_user_id"),
    "forecast_snapshot": ("forecast_snapshot_cells", "owner_user_id"),
    "report_owner": ("reports", "owner_user_id"),
    "report_editor": ("reports", "updated_by_user_id"),
    "meeting_author": ("partner_meetings", "created_by_user_id"),
}
SESSION_COLUMN: Final = ("auth_sessions", "user_id")
EXPECTED_USER_FKS: Final = frozenset({*LINK_COLUMNS.values(), SESSION_COLUMN})


async def _helper_user(uow: UnitOfWork) -> User:
    helper = make_user(f"h{uuid4().hex[:12]}", now=NOW)
    await uow.users.add(helper)
    return helper


async def _deal(uow: UnitOfWork, *, owner: UserId) -> Deal:
    from tests.factories_contact import make_customer  # noqa: PLC0415 - 연락처 구현 지연 import

    customer = make_customer()
    await uow.contacts.add(customer)
    deal = make_deal(
        code=f"20261016-{uuid4().hex[:4].upper()}",
        customer_id=customer.id,
        owner_user_id=owner,
    )
    await uow.deals.add(deal)
    return deal


async def link_user(uow_factory: UnitOfWorkFactory, user: User, kind: str) -> None:
    """user를 `kind` 방식으로 참조하는 행을 하나 만들고 commit한다."""
    async with uow_factory() as uow:
        await _create_link(uow, user, kind)
        await uow.commit()


async def _create_link(uow: UnitOfWork, user: User, kind: str) -> None:
    if kind == "deal_owner":
        await _deal(uow, owner=user.id)
    elif kind == "history_author":
        from app.domain.deal.history import (  # noqa: PLC0415
            DealHistoryEntry,
            HistoryCategory,
            HistoryDraft,
        )

        helper = await _helper_user(uow)
        deal = await _deal(uow, owner=helper.id)
        draft = HistoryDraft(HistoryCategory.CREATED, "Deal 등록", "", "Deal 등록")
        await uow.deal_history.add_many([DealHistoryEntry(None, deal.id, later(5), user.id, draft)])
    elif kind == "action_actor":
        helper = await _helper_user(uow)
        deal = await _deal(uow, owner=helper.id)
        action = make_deal_action(deal_code=deal.id, actor_user_id=user.id)
        await attach_catalog_type(uow.action_types, action)  # 실제 DB 시드 유형으로 맞춘다
        await uow.deal_actions.add(action)
    elif kind == "created_user":
        await uow.users.add(make_user(f"c{uuid4().hex[:12]}", created_by_user_id=user.id))
    elif kind == "directory_settings":
        # 이미 설정이 있는 환경(e2e admin 앱)에서는 현재 revision으로 갱신한다.
        stored = await uow.directory_settings.get()
        await uow.directory_settings.save(
            make_directory_settings(),
            expected_revision=None if stored is None else stored.revision,
            updated_by=user.id,
            now=NOW,
        )
    elif kind == "label_creator":
        await uow.bant_labels.add(make_label(name=f"L{uuid4().hex[:12]}", created_by=user.id))
    elif kind == "action_type_creator":
        await uow.action_types.add(make_action_type(f"T{uuid4().hex[:12]}", created_by=user.id))
    else:
        await _create_file_or_setting_link(uow, user, kind)


async def _create_file_or_setting_link(uow: UnitOfWork, user: User, kind: str) -> None:
    if kind == "storage_settings":
        from app.domain.storage.path import StoragePath  # noqa: PLC0415

        # 이미 저장 위치가 있는 환경(functional 최초 설정을 마친 앱)에서는 저장자만 바뀐다(upsert).
        await uow.storage_settings.save(
            StoragePath.parse("/data/neoine-sales/files"), updated_by=user.id, now=NOW
        )
    elif kind == "attachment_uploader":
        from tests.factories_attachment import make_attachment  # noqa: PLC0415

        helper = await _helper_user(uow)
        deal = await _deal(uow, owner=helper.id)
        await uow.attachments.add(make_attachment(deal_code=deal.id, uploaded_by=user.id))
    elif kind == "alert_settings":
        from app.domain.alert.thresholds import AlertThresholds  # noqa: PLC0415

        # 이미 경고 기준이 있는 환경에서는 저장자만 바뀐다(upsert).
        await uow.alert_settings.save(AlertThresholds(stale_days=7), updated_by=user.id, now=NOW)
    elif kind == "forecast_snapshot":
        await _create_snapshot_link(uow, user)
    elif kind in {"report_owner", "report_editor"}:
        await _create_report_link(uow, user, kind)
    elif kind == "meeting_author":
        await _create_meeting_link(uow, user)
    else:
        raise AssertionError(kind)


async def _create_snapshot_link(uow: UnitOfWork, user: User) -> None:
    from app.domain.code.values import ForecastOutcome  # noqa: PLC0415
    from app.domain.forecast.snapshot import (  # noqa: PLC0415
        ForecastSnapshot,
        SnapshotCell,
        SnapshotColumn,
        YearMonth,
    )
    from app.domain.forecast.summary import Tally  # noqa: PLC0415

    cell = SnapshotCell(
        revenue_year=2026,
        revenue_month=9,
        owner_id=user.id,
        forecast_key="pipeline",
        tally=Tally(1, 100),
    )
    column = SnapshotColumn(key="pipeline", name="Pipeline", outcome=ForecastOutcome.OPEN, order=1)
    # 같은 기준 월이 이미 있으면 대체된다(replace는 upsert).
    await uow.forecast_snapshots.replace(
        ForecastSnapshot(period=YearMonth(2026, 9), taken_at=NOW, columns=[column], cells=[cell])
    )


async def _create_report_link(uow: UnitOfWork, user: User, kind: str) -> None:
    """report_owner: user가 만든 리포트. report_editor: 남이 만들고 user가 마지막 수정한 리포트."""
    from tests.factories_report import make_report  # noqa: PLC0415 - 리포트 구현 지연 import

    name = f"R{uuid4().hex[:12]}"
    if kind == "report_owner":
        await uow.saved_reports.add(make_report(name, owner=user.id))
        return
    helper = await _helper_user(uow)
    await uow.saved_reports.add(make_report(name, owner=helper.id, editor=user.id, revision=2))


async def _create_meeting_link(uow: UnitOfWork, user: User) -> None:
    """user가 작성한 파트너 미팅 기록(파트너가 연결된 Deal은 보조 사용자가 담당한다)."""
    from tests.factories_contact import (  # noqa: PLC0415 - 연락처 구현 지연 import
        make_customer,
        make_partner,
    )
    from tests.factories_partner_meeting import make_meeting  # noqa: PLC0415

    helper = await _helper_user(uow)
    customer, partner = make_customer(), make_partner()
    await uow.contacts.add(customer)
    await uow.contacts.add(partner)
    deal = make_deal(
        code=f"20261016-{uuid4().hex[:4].upper()}",
        customer_id=customer.id,
        partner_id=partner.id,
        owner_user_id=helper.id,
    )
    await uow.deals.add(deal)
    await uow.partner_meetings.add(
        make_meeting(deal_code=deal.id, company=partner.details.company, author=user.id)
    )
