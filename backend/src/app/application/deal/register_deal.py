from typing import TYPE_CHECKING

from app.application.deal.code_issuer import add_with_issued_code
from app.application.deal.contact_draft import resolve_contacts
from app.application.deal.form import ALL_FIELDS, FormValues
from app.application.deal.history_writer import write_history
from app.application.deal.validation import validate_form
from app.application.deal.views import build_views
from app.domain.deal.entities import Deal
from app.domain.deal.history import created_draft

if TYPE_CHECKING:
    from app.application.deal.dto import DealView
    from app.application.deal.inputs import Actor, DealCreateInput
    from app.application.ports.clock import Clock
    from app.application.ports.deal_code_source import DealCodeSuffixSource
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class RegisterDeal:
    """Deal을 등록한다: 입력 검증, 연락처 선택·생성, code 발급, 저장, 등록 이력 한 건."""

    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, suffix_source: DealCodeSuffixSource
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._suffix_source = suffix_source

    async def execute(self, data: DealCreateInput, actor: Actor) -> DealView:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            form = await validate_form(uow, FormValues.of_create(data), ALL_FIELDS)
            contacts = await resolve_contacts(
                uow, (data.customer, data.partner), form.drafts, actor.user_id, now
            )
            deal = await add_with_issued_code(
                uow,
                self._suffix_source,
                now,
                lambda code: Deal.create(
                    code=code,
                    details=form.details,
                    sync=form.sync,
                    customer_id=contacts.require_customer(),
                    partner_id=contacts.partner_id,
                    bant=form.bant,
                    now=now,
                ),
            )
            await write_history(uow, deal.id, actor.user_id, [created_draft()], now)
            view = (await build_views(uow, [await uow.deals.get_item(deal.id)], now=now))[0]
            await uow.commit()
        return view
