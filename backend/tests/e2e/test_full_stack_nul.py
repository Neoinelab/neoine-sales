"""실제 PostgreSQL에서도 NUL 문자 검색은 500이 아니라 422다."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.mark.integration
async def test_deal_search_with_nul_keyword_is_422_not_500(stack: AsyncClient) -> None:
    response = await stack.get("/api/v1/deals", params={"keyword": "a\x00b"})

    assert response.status_code == 422, response.text
    assert response.json()["type"].endswith("invalid-value")
