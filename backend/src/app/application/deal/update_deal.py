from typing import TYPE_CHECKING

from app.application.deal.contact_draft import resolve_contacts
from app.application.deal.form import FormValues
from app.application.deal.history_writer import build_name_lookup, write_history
from app.application.deal.validation import validate_form
from app.application.deal.views import build_views
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.history import diff_deal

if TYPE_CHECKING:
    from app.application.deal.dto import DealView
    from app.application.deal.inputs import Actor, DealPatchInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class UpdateDeal:
    """Deal 폼 저장. 보낸 필드만 검증·반영하고, 바뀐 필드마다 History 한 건을 남긴다.

    바뀐 것이 없으면 이력도 수정 시각 변경도 없다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, code: str, patch: DealPatchInput, actor: Actor) -> DealView:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        now = self._clock.now()
        async with self._uow_factory() as uow:
            deal = await uow.deals.get(deal_code, for_update=True)
            before = deal.snapshot()
            values = FormValues.of_patch(deal, patch)
            form = await validate_form(uow, values, patch.provided)
            contacts = await resolve_contacts(
                uow, (values.customer, values.partner), form.drafts, actor.user_id, now
            )
            deal.revise(
                details=form.details,
                sync=form.sync,
                customer_id=contacts.customer_id or deal.customer_id,
                bant=form.bant,
            )
            if "partner" in patch.provided:
                deal.replace_partner(contacts.partner_id, now)
            after = deal.snapshot()
            lookup = await build_name_lookup(uow, [before, after])
            drafts = diff_deal(before, after, lookup)
            if drafts or deal.id in contacts.touched:
                deal.touch(now)
                await uow.deals.update(deal)
                await write_history(uow, deal.id, actor.user_id, drafts, now)
            view = (await build_views(uow, [await uow.deals.get_item(deal.id)], now=now))[0]
            await uow.commit()
        return view
