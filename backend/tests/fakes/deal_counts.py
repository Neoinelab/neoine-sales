"""FakeDealRepository의 집계(count_by_*) 메서드. 저장된 Deal(`self._items`)에서 센다."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.domain.bant.values import BantLabelId
    from app.domain.contact.values import ContactId
    from app.domain.vendor.values import VendorId


class DealCountsMixin:
    _items: dict[Any, Any]
    forecast_counts: dict[str, int] | None
    bant_label_counts: dict[BantLabelId, int] | None

    async def count_by_status(self) -> Mapping[str, int]:
        counts: dict[str, int] = {}
        for deal in self._items.values():
            counts[deal.sync.status_key] = counts.get(deal.sync.status_key, 0) + 1
        return counts

    async def count_by_forecast(self) -> Mapping[str, int]:
        if self.forecast_counts is not None:
            return dict(self.forecast_counts)
        counts: dict[str, int] = {}
        for deal in self._items.values():
            counts[deal.sync.forecast_key] = counts.get(deal.sync.forecast_key, 0) + 1
        return counts

    async def count_by_bant_label(self) -> Mapping[BantLabelId, int]:
        if self.bant_label_counts is not None:
            return dict(self.bant_label_counts)
        counts: dict[BantLabelId, int] = {}
        for deal in self._items.values():
            for category in ("budget", "authority", "need", "timeline"):
                label_id = getattr(deal.bant, category)
                if label_id is not None:
                    counts[label_id] = counts.get(label_id, 0) + 1
        return counts

    async def count_by_vendor(self) -> Mapping[VendorId, int]:
        counts: dict[VendorId, int] = {}
        for deal in self._items.values():
            if deal.details.vendor_id is not None:
                counts[deal.details.vendor_id] = counts.get(deal.details.vendor_id, 0) + 1
        return counts

    async def count_by_contacts(self, contact_ids: Sequence[ContactId]) -> Mapping[ContactId, int]:
        """고객 또는 파트너 링크(비활성 포함)로 참조하는 Deal 수. 한 Deal은 연락처당 1건이다."""
        counts: dict[ContactId, int] = {}
        for contact_id in contact_ids:
            counts[contact_id] = sum(
                1
                for d in self._items.values()
                if contact_id == d.customer_id
                or any(link.contact_id == contact_id for link in d.partner_links)
            )
        return counts

    async def earliest_revenue_year(self) -> int | None:
        """모든 Deal의 Expected Close(revenue_date) 중 가장 이른 연도. Deal이 없으면 None."""
        years = [d.details.revenue_date.year for d in self._items.values()]
        return min(years) if years else None
