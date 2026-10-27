"""Deal 필드 28개 (계획 4.3 표 순서)."""

from app.domain.report.fields import (
    CodeSource,
    FieldSpec,
    code_field,
    date_field,
    datetime_field,
    number_field,
    text_field,
    user_field,
)
from app.domain.report.vocabulary import Aggregate, Format, OptionsSource

_BANT = [
    ("budget", "BANT Budget"),
    ("authority", "BANT Authority"),
    ("need", "BANT Need"),
    ("timeline", "BANT Timeline"),
]

DEAL_FIELDS: tuple[FieldSpec, ...] = (
    text_field("deal.code", "Deal code"),
    text_field("deal.name", "Deal 이름"),
    text_field("deal.solution", "Solution"),
    text_field("deal.procurement", "구매절차"),
    user_field("deal.owner", "담당자"),
    text_field("deal.customer_company", "고객사"),
    text_field("deal.customer_contact", "고객 담당자"),
    text_field("deal.partner_company", "파트너사(현재)"),
    code_field("deal.vendor", "Vendor", CodeSource.by_id(OptionsSource.VENDORS)),
    code_field("deal.status", "Status", CodeSource.by_key(OptionsSource.STATUS_CODES)),
    code_field("deal.forecast", "Forecast", CodeSource.by_key(OptionsSource.FORECAST_CODES)),
    code_field(
        "deal.forecast_outcome",
        "Forecast 구분",
        CodeSource.static(("open", "Open"), ("won", "Won"), ("lost", "Lost")),
    ),
    code_field(
        "deal.quote_submitted",
        "견적 제출",
        CodeSource.static(("YES", "YES"), ("NO", "NO")),
    ),
    code_field(
        "deal.poc_state",
        "POC 상태",
        CodeSource.static(("YES", "YES"), ("ING", "ING"), ("NO", "NO")),
    ),
    *(
        code_field(
            f"deal.bant_{category}", label, CodeSource.by_id(OptionsSource.BANT_LABELS, category)
        )
        for category, label in _BANT
    ),
    code_field(
        "deal.risk",
        "경고",
        CodeSource.static(("overdue", "기한초과"), ("stale", "미업데이트")),
    ),
    number_field("deal.amount", "금액(원)", default_format=Format.KRW_THOUSAND),
    number_field("deal.users", "Users"),
    number_field("deal.status_days", "Status 체류 일수", default_aggregate=Aggregate.AVG),
    date_field("deal.expected_close", "Expected Close"),
    date_field("deal.quote_submitted_date", "견적 제출일"),
    date_field("deal.poc_completed_date", "POC 완료일"),
    datetime_field("deal.created_at", "등록일"),
    datetime_field("deal.last_updated_at", "최종 업데이트"),
    datetime_field("deal.status_changed_at", "Status 진입 시각"),
)
