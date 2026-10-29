"""파트너 Activity 라우터 단위 테스트 공용 도우미: FakeUseCases 위의 ASGI 클라이언트와 시드.

클라이언트(사용자별 세션)와 Problem 단언은 저장 리포트 라우터 테스트의 도우미를 그대로 쓴다.
Deal·파트너 연락처는 Fake 저장소에 직접 두고, 미팅은 API(POST)로 만든다.
"""

from typing import TYPE_CHECKING, Any, Final

from tests.factories import make_deal, make_deal_code
from tests.factories_contact import make_customer, make_partner
from tests.unit.web.saved_report_http import clients, problem

if TYPE_CHECKING:
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

__all__ = [
    "DETAIL_KEYS",
    "HANBIT",
    "READ_ONLY",
    "URL",
    "clients",
    "item",
    "post_one",
    "problem",
    "seed_deals",
]

URL: Final = "/api/v1/partner-meetings"
OPTIONS_URL: Final = f"{URL}/deal-options"
HANBIT: Final = "한빛파트너스"
READ_ONLY: Final = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"
DETAIL_KEYS: Final = {
    "id",
    "partner_company",
    "deal",
    "meeting_date",
    "content",
    "author",
    "created_at",
    "updated_at",
}


async def seed_deals(
    use_cases: FakeUseCases, *names: str, company: str | None = HANBIT
) -> list[str]:
    """이름마다 Deal 하나(company의 새 담당자가 활성 파트너). Deal code 문자열 목록을 돌려준다."""
    codes: list[str] = []
    for name in names or ("ERP 구축",):
        code = make_deal_code(f"W{len(use_cases.uow.deals._items) + 1:03d}")
        customer = make_customer(
            company="네오인", name=f"고객{code.value[-4:]}", email=f"{code.value[-4:]}@c.test"
        )
        await use_cases.uow.contacts.add(customer)
        partner = None
        if company is not None:
            partner = make_partner(
                company=company, name=f"담당{code.value[-4:]}", email=f"{code.value[-4:]}@p.test"
            )
            await use_cases.uow.contacts.add(partner)
        await use_cases.uow.deals.add(
            make_deal(
                code=code,
                name=name,
                customer_id=customer.id,
                partner_id=None if partner is None else partner.id,
            )
        )
        codes.append(code.value)
    return codes


def item(code: str, /, **overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    """요청 항목 하나(MeetingItemRequest)."""
    return {
        "partner_company": HANBIT,
        "deal_code": code,
        "meeting_date": "2026-10-01",
        "content": "킥오프 미팅",
        **overrides,
    }


async def post_one(http: AsyncClient, code: str, /, **overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    """미팅 한 건을 만들고 응답 항목을 돌려준다."""
    response = await http.post(URL, json={"items": [item(code, **overrides)]})
    assert response.status_code == 201, response.text
    return dict(response.json()["items"][0])
