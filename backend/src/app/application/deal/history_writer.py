"""History를 남기는 도우미: 이름 조회(`NameLookup`)를 만들고 항목을 저장한다."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.deal.sync_change import load_catalog
from app.domain.bant.values import BantCategory
from app.domain.deal.history import DealHistoryEntry, diff_deal

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from datetime import datetime

    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.bant.values import BantLabelId
    from app.domain.contact.values import ContactId
    from app.domain.deal.code import DealCode
    from app.domain.deal.entities import Deal
    from app.domain.deal.history import DealSnapshot, HistoryDraft
    from app.domain.deal.sync import CoChange, CodeCatalog
    from app.domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class NameLookup:
    """`HistoryLookup` 구현: 미리 읽어 둔 이름으로 표기를 만든다. 모르는 값은 id를 그대로 쓴다."""

    statuses: Mapping[str, str]
    forecasts: Mapping[str, str]
    users: Mapping[UserId, str]
    contacts: Mapping[ContactId, str]
    labels: Mapping[BantLabelId, str]

    def status_name(self, key: str) -> str:
        return self.statuses.get(key, key)

    def forecast_name(self, key: str) -> str:
        return self.forecasts.get(key, key)

    def user_label(self, user_id: UserId) -> str:
        return self.users.get(user_id, str(user_id))

    def contact_name(self, contact_id: ContactId) -> str:
        return self.contacts.get(contact_id, str(contact_id))

    def label_name(self, label_id: BantLabelId | None) -> str:
        if label_id is None:
            return "선택 안 함"
        return self.labels.get(label_id, str(label_id))


def _label_ids(snapshots: Iterable[DealSnapshot]) -> set[BantLabelId]:
    return {
        label_id
        for snapshot in snapshots
        for category in BantCategory
        if (label_id := snapshot.bant.get(category)) is not None
    }


async def build_name_lookup(
    uow: UnitOfWork, snapshots: Sequence[DealSnapshot], *, catalog: CodeCatalog | None = None
) -> NameLookup:
    """비교할 스냅숏들에 나오는 사용자·연락처·Label과 모든 코드의 이름을 읽는다.

    이미 읽어 둔 코드 목록(catalog)을 주면 코드를 다시 읽지 않는다.
    """
    catalog = catalog or await load_catalog(uow)
    user_ids = {s.details.owner_user_id for s in snapshots}
    contact_ids = {s.customer_id for s in snapshots}
    contact_ids |= {s.active_partner_id for s in snapshots if s.active_partner_id is not None}
    refs = await uow.users.get_refs(user_ids)
    contacts = await uow.contacts.get_many(contact_ids)
    wanted = _label_ids(snapshots)
    return NameLookup(
        statuses={c.key: c.name for c in catalog.statuses},
        forecasts={c.key: c.name for c in catalog.forecasts},
        users={uid: ref.label for uid, ref in refs.items()},
        contacts={cid: f"{c.details.company} {c.details.name}" for cid, c in contacts.items()},
        labels={
            label.id: label.name for label in await uow.bant_labels.list() if label.id in wanted
        },
    )


async def write_history(
    uow: UnitOfWork,
    code: DealCode,
    changed_by: UserId,
    drafts: Sequence[HistoryDraft],
    now: datetime,
) -> None:
    """주어진 순서대로 저장한다(나중에 기록한 항목이 목록에서 위에 온다)."""
    if drafts:
        await uow.deal_history.add_many(
            [DealHistoryEntry(None, code, now, changed_by, draft) for draft in drafts]
        )


async def record_deal_diff(  # noqa: PLR0913
    uow: UnitOfWork,
    deal: Deal,
    before: DealSnapshot,
    *,
    actor_id: UserId,
    now: datetime,
    catalog: CodeCatalog,
    co_changed: Sequence[CoChange] = (),
) -> bool:
    """차이가 있으면 수정 시각 갱신·저장·History 기록을 하고 변경 여부를 돌려준다."""
    after = deal.snapshot()
    lookup = await build_name_lookup(uow, [before, after], catalog=catalog)
    drafts = diff_deal(before, after, lookup, co_changed)
    if not drafts:
        return False
    deal.touch(now)
    await uow.deals.update(deal)
    await write_history(uow, deal.id, actor_id, drafts, now)
    return True
