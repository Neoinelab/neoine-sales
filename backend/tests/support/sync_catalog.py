"""동기화 규칙 테스트용 코드 목록(`CodeCatalog`): 기본 Status 7·Forecast 6 (order 순)."""

from app.domain.deal.sync import CodeCatalog, CodeName, SyncState
from tests.fakes.catalog_seed import DEFAULT_FORECASTS, DEFAULT_STATUSES

OPEN = SyncState(status_key="price_negotiation", forecast_key="commit")
WON = SyncState(status_key="contract_completed", forecast_key="won")
LOST = SyncState(status_key="price_negotiation", forecast_key="lost")


def default_catalog(**renamed: str) -> CodeCatalog:
    """기본 코드 목록. renamed는 key -> 새 이름(예: contract_completed="수주확정")."""
    return CodeCatalog(
        statuses=tuple(CodeName(key, renamed.get(key, name)) for key, name in DEFAULT_STATUSES),
        forecasts=tuple(
            CodeName(key, renamed.get(key, name)) for key, name, _, _ in DEFAULT_FORECASTS
        ),
    )
