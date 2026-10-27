"""Deal 필드 key -> SQL 식 (계획 4.3). 식은 처음 쓸 때만 만들어 필요한 JOIN만 추가된다."""

from typing import TYPE_CHECKING

from app.domain.report.catalog import find_field
from app.infra.db.deal_derived import last_updated_scalar
from app.infra.db.report_fields import FieldSql, option_labels, static_code, user_name
from app.infra.db.report_joins import (
    DEALS,
    Joins,
    deal_bant,
    deal_customer,
    deal_forecast_code,
    deal_owner,
    deal_partner,
    deal_status_code,
    deal_vendor,
)
from app.infra.db.report_risk import RiskExprs, status_days

if TYPE_CHECKING:
    from app.domain.report.resolve import ReportContext

_BANT_CATEGORIES = ("budget", "authority", "need", "timeline")
_RISK_LABELS = [
    ("overdue", "기한초과"),
    ("stale", "미업데이트"),
    ("overdue_stale", "기한초과·미업데이트"),
]


def _labels(key: str) -> list[tuple[str, str]]:
    """카탈로그의 정적 선택지 (값, 라벨)."""
    spec = find_field(key)
    return option_labels(spec.options if spec else None)


def _static(key: str, column_name: str) -> FieldSql:
    """정적 선택지를 가진 Deals 열(카탈로그의 선택지 라벨을 그대로 쓴다)."""
    return static_code(lambda: DEALS.c[column_name], _labels(key))


def _plain(column_name: str) -> FieldSql:
    return FieldSql(lambda: DEALS.c[column_name])


def deal_fields(joins: Joins, context: ReportContext, risk: RiskExprs) -> dict[str, FieldSql]:
    c = DEALS.c
    fields = {
        "deal.code": _plain("deal_code"),
        "deal.name": _plain("name"),
        "deal.solution": _plain("solution"),
        "deal.procurement": _plain("procurement"),
        "deal.owner": FieldSql(lambda: c.owner_user_id, value=lambda: user_name(deal_owner(joins))),
        "deal.customer_company": FieldSql(lambda: deal_customer(joins).c.company),
        "deal.customer_contact": FieldSql(lambda: deal_customer(joins).c.name),
        "deal.partner_company": FieldSql(lambda: deal_partner(joins).c.company),
        "deal.vendor": FieldSql(lambda: c.vendor_id, value=lambda: deal_vendor(joins).c.name),
        "deal.status": FieldSql(
            lambda: c.status_key,
            value=lambda: deal_status_code(joins).c.name,
            order=lambda: deal_status_code(joins).c.sort_order,
        ),
        "deal.forecast": FieldSql(
            lambda: c.forecast_key,
            value=lambda: deal_forecast_code(joins).c.name,
            order=lambda: deal_forecast_code(joins).c.sort_order,
        ),
        "deal.forecast_outcome": static_code(
            lambda: deal_forecast_code(joins).c.outcome,
            _labels("deal.forecast_outcome"),
        ),
        "deal.quote_submitted": _static("deal.quote_submitted", "quote_submitted"),
        "deal.poc_state": _static("deal.poc_state", "poc_state"),
        "deal.risk": static_code(risk.value, _RISK_LABELS),
        "deal.amount": _plain("revenue_amount"),
        "deal.users": _plain("users"),
        "deal.status_days": FieldSql(lambda: status_days(context)),
        "deal.expected_close": _plain("revenue_date"),
        "deal.quote_submitted_date": _plain("quote_submitted_date"),
        "deal.poc_completed_date": _plain("poc_completed_date"),
        "deal.created_at": _plain("created_at"),
        "deal.last_updated_at": FieldSql(last_updated_scalar),
        "deal.status_changed_at": _plain("status_changed_at"),
    }
    for category in _BANT_CATEGORIES:
        fields[f"deal.bant_{category}"] = _bant(joins, category)
    return fields


def _bant(joins: Joins, category: str) -> FieldSql:
    """BANT 구분: 조건·그룹은 선택한 Label id, 표시는 Label 이름."""
    return FieldSql(
        lambda: deal_bant(joins, category)[0].c.label_id,
        value=lambda: deal_bant(joins, category)[1].c.name,
    )
