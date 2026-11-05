"""계약 라우터 단위 테스트 공용 도우미: FakeUseCases 위의 ASGI 클라이언트와 시드.

클라이언트(사용자별 세션)와 Problem 단언은 저장 리포트 라우터 테스트의 도우미를 그대로 쓴다.
Deal은 `seed_deal`(고객 연락처 포함)로, 계약은 Fake 저장소에 직접 둔다.
"""

from typing import TYPE_CHECKING, Any, Final

from tests.factories import NOW
from tests.factories_deal import seed_deal
from tests.factories_license_contract import make_contract
from tests.support.user_ids import OWNER_ID
from tests.support.user_seed import ensure_users
from tests.unit.web.saved_report_http import clients, problem

if TYPE_CHECKING:
    from app.domain.license_contract.entities import LicenseContract
    from tests.fakes.use_cases import FakeUseCases

__all__ = [
    "ATTACHMENTS",
    "ATTACHMENT_URL",
    "BASE",
    "CONTRACT_KEYS",
    "ID_URL",
    "READ_ONLY",
    "WON_DEAL",
    "clients",
    "problem",
    "seed_contract",
]

BASE: Final = "/api/v1/license-contracts"
ID_URL: Final = BASE + "/{id}"
ATTACHMENTS: Final = BASE + "/{id}/attachments"
ATTACHMENT_URL: Final = "/api/v1/license-contract-attachments/{id}"
READ_ONLY: Final = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"
WON_DEAL: Final = {"status_key": "contract_completed", "forecast_key": "won"}
CONTRACT_KEYS: Final = {
    "id",
    "deal_code",
    "deal_name",
    "customer",
    "vendor",
    "product",
    "partner",
    "sales_owner",
    "status",
    "license_start",
    "license_end",
    "term",
    "tech_owner",
    "inspection_cycle",
    "note",
    "renewed_from_id",
    "ended_at",
    "attachment_count",
    "deal_is_won",
    "created_by",
    "updated_by",
    "created_at",
    "updated_at",
}


async def seed_contract(use_cases: FakeUseCases, **overrides: Any) -> LicenseContract:  # noqa: ANN401
    """Deal(고객 포함)과 그 Deal의 계약 하나를 둔다. overrides는 `make_contract`와 같다.

    `deal_overrides`는 Deal 값(`make_deal`과 같다). 발급·갱신은 Won Deal에서만 되므로 그 경로는
    `deal_overrides=WON_DEAL`로 둔다(기본은 Won이 아닌 Deal).
    """
    deal_overrides = overrides.pop("deal_overrides", {})
    async with use_cases.uow as uow:
        await ensure_users(uow.users, OWNER_ID)
        deal = await seed_deal(uow, code="20261016-A001", commit=False, **deal_overrides)
        contract = make_contract(deal_code=deal.id, by=OWNER_ID, now=NOW, **overrides)
        await uow.license_contracts.add(contract)
        await uow.commit()
    return contract
