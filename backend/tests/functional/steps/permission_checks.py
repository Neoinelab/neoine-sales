"""권한 표 시나리오의 Then step."""

from typing import TYPE_CHECKING

from tests.functional.steps.platform import then_problem_kind_is

if TYPE_CHECKING:
    from httpx import Response


def then_route_access_is(response: Response, *, allowed: bool) -> None:
    """허용된 역할에는 경로가 열리고(401/403 아님) 아닌 역할에는 403(forbidden)이다."""
    if allowed:
        assert response.status_code not in {401, 403}, response.text
        return
    then_problem_kind_is(response, status=403, kinds=("forbidden",))
    assert "권한" in response.json()["detail"]
