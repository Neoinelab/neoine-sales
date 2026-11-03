"""파트너 Activity 라우터 단위 테스트 공용 도우미: FakeUseCases 위의 ASGI 클라이언트와 시드.

클라이언트(사용자별 세션)와 Problem 단언은 저장 리포트 라우터 테스트의 도우미를 그대로 쓴다.
파트너 연락처는 Fake 저장소에 직접 두고(Deal은 필요 없다), 미팅은 API(POST)로 만든다.
"""

from typing import TYPE_CHECKING, Any, Final
from uuid import uuid4

from tests.factories_contact import make_partner
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
    "seed_partners",
]

URL: Final = "/api/v1/partner-meetings"
HANBIT: Final = "한빛파트너스"
READ_ONLY: Final = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"
DETAIL_KEYS: Final = {
    "id",
    "partner_company",
    "meeting_date",
    "content",
    "author",
    "created_at",
    "updated_at",
}


async def seed_partners(use_cases: FakeUseCases, *companies: str) -> None:
    """회사마다 파트너 연락처 하나(파트너 회사 목록의 원본). Deal은 만들지 않는다."""
    for company in companies or (HANBIT,):
        tag = uuid4().hex[:8]
        await use_cases.uow.contacts.add(
            make_partner(company=company, name=f"담당{tag}", email=f"{tag}@p.test")
        )


def item(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    """요청 항목 하나(MeetingItemRequest)."""
    return {
        "partner_company": HANBIT,
        "meeting_date": "2026-10-01",
        "content": "킥오프 미팅",
        **overrides,
    }


async def post_one(http: AsyncClient, **overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    """미팅 한 건을 만들고 응답 항목을 돌려준다."""
    response = await http.post(URL, json={"items": [item(**overrides)]})
    assert response.status_code == 201, response.text
    return dict(response.json()["items"][0])
