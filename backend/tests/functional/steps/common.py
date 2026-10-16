"""영역에 묶이지 않는 공통 Then step: 상태 코드, Problem 응답, 응답 본문."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import Response

PROBLEM_CONTENT_TYPE = "application/problem+json"


def then_status_is(response: Response, status: int) -> None:
    assert response.status_code == status, f"{response.status_code}: {response.text}"


def then_problem_is(response: Response, *, status: int, type_suffix: str) -> None:
    """RFC 9457 Problem 응답이고 상태 코드와 type 끝부분(예: "not-ready")이 같다."""
    then_status_is(response, status)
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    assert str(response.json()["type"]).endswith(type_suffix), response.json()


def then_body_is(response: Response, expected: object) -> None:
    assert response.json() == expected


def then_body_includes(response: Response, **fields: object) -> None:
    """응답 JSON 객체에 주어진 필드가 그 값으로 들어 있다(나머지 필드는 보지 않는다)."""
    body = response.json()
    assert {key: body.get(key) for key in fields} == fields, body


def then_response_does_not_mention(response: Response, *fragments: str) -> None:
    """응답(본문·헤더 값)에 내부 정보 조각(비밀번호, 접속 문자열 등)이 드러나지 않는다."""
    exposed = response.text + " ".join(response.headers.values())
    for fragment in fragments:
        assert fragment not in exposed, fragment
