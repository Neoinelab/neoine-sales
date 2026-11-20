"""Deals 목록 조건 전체를 CSV 칸 값(문자열)으로 만든다. CSV 바이트 조립은 web의 일이다."""

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from app.application.deal.views import build_views, load_thresholds
from app.domain.code.values import CodeKind
from app.domain.common.business_date import business_date
from app.domain.deal.export import (
    EXPORT_HEADER,
    check_export_size,
    export_file_name,
    neutralize_formula,
)
from app.domain.deal.risk import RiskBasis

if TYPE_CHECKING:
    from datetime import date

    from app.application.deal.dto import DealView
    from app.application.ports.clock import Clock
    from app.application.ports.deal_repository import DealQuery
    from app.application.ports.unit_of_work import UnitOfWorkFactory

_CHUNK = 200


@dataclass(frozen=True, slots=True)
class DealExport:
    file_name: str
    header: tuple[str, ...]
    rows: list[tuple[str, ...]]


def _iso(day: date | None) -> str:
    return "" if day is None else day.isoformat()


def _row(view: DealView, names: dict[CodeKind, dict[str, str]]) -> tuple[str, ...]:
    deal = view.item.deal
    details = deal.details
    partner_id = deal.active_partner_id()
    partner = view.partner_contacts[partner_id].details.company if partner_id is not None else ""
    vendor = view.vendor.name if view.vendor else ""
    action = view.item.next_action
    status, forecast = deal.sync.status_key, deal.sync.forecast_key
    return (
        neutralize_formula(details.name),
        neutralize_formula(view.owner.label),
        neutralize_formula(view.customer.details.company),
        neutralize_formula(partner),
        neutralize_formula(vendor),
        neutralize_formula(details.product),
        neutralize_formula(names[CodeKind.STATUS].get(status, status)),
        neutralize_formula(names[CodeKind.FORECAST].get(forecast, forecast)),
        f"{details.revenue_amount.value:,}",
        _iso(details.revenue_date),
        _iso(view.item.last_updated_on),
        neutralize_formula(action.text) if action else "",
        _iso(action.due_date) if action else "",
        neutralize_formula(action.status.label) if action else "",
    )


class ExportDeals:
    """조건에 맞는 모든 Deal을 목록과 같은 정렬·해석으로 낸다(상한 초과는 거절)."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, query: DealQuery) -> DealExport:
        now = self._clock.now()
        today = business_date(now)
        query = query.with_year_for(today).with_today(today)
        async with self._uow_factory() as uow:
            thresholds = await load_thresholds(uow)
            query = query.with_risk_basis(RiskBasis(today, thresholds.stale_days))
            check_export_size(await uow.deals.count(query))
            codes = await uow.codes.list()
            names = {
                kind: {c.key.value: c.name for c in codes if c.kind is kind} for kind in CodeKind
            }
            rows: list[tuple[str, ...]] = []
            offset = 0
            while True:
                items = await uow.deals.search(replace(query, offset=offset, limit=_CHUNK))
                views = await build_views(uow, items, now=now, thresholds=thresholds)
                rows += [_row(view, names) for view in views]
                if len(items) < _CHUNK:
                    break
                offset += _CHUNK
        return DealExport(export_file_name(today), EXPORT_HEADER, rows)
