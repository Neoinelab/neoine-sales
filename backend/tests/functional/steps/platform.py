"""플랫폼 공통 step: Problem 종류 확인, OpenAPI 조회·해석, 문서·CORS 호출.

OpenAPI 계약은 앱이 HTTP로 돌려주는 `/openapi.json`을 읽어 검증한다(local 프로파일은 문서 노출).
"""

from typing import TYPE_CHECKING, Any

from tests.functional.steps.common import then_status_is

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

PROBLEM_PREFIX = "https://neoine-sales.example/problems/"
PROBLEM_CONTENT_TYPE = "application/problem+json"
Spec = dict[str, Any]


def problem_type(response: Response) -> str:
    """Problem 문서의 type에서 공통 접두사를 뗀 종류 이름(예: `forbidden`)."""
    return str(response.json()["type"]).removeprefix(PROBLEM_PREFIX)


def then_problem_kind_is(response: Response, *, status: int, kinds: tuple[str, ...]) -> None:
    """Problem 응답이고 상태 코드가 같으며 type 종류가 정확히 주어진 것 중 하나다."""
    then_status_is(response, status)
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    assert problem_type(response) in kinds, response.json()


async def when_fetch_openapi(api: Api) -> Response:
    return await api.get("/openapi.json")


def spec_of(response: Response) -> Spec:
    then_status_is(response, 200)
    spec: Spec = response.json()
    return spec


def operation_of(spec: Spec, method: str, path: str) -> dict[str, Any]:
    operation: dict[str, Any] = spec["paths"][path][method.lower()]
    return operation


def schema_name_of(operation: dict[str, Any], *, request: bool) -> str:
    """요청 본문 또는 첫 2xx JSON 응답이 참조하는 스키마 이름."""
    if request:
        ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    else:
        ref = next(
            r["content"]["application/json"]["schema"]["$ref"]
            for code, r in operation["responses"].items()
            if code.startswith("2") and "content" in r
        )
    return str(ref).rsplit("/", 1)[-1]


def api_routes_of(spec: Spec) -> set[tuple[str, str]]:
    """OpenAPI에 문서화된 (메서드, 경로) 중 헬스체크와 /api/v1 아래의 것."""
    return {
        (method.upper(), path)
        for path, item in spec["paths"].items()
        for method in item
        if path in {"/healthz", "/readyz"} or path.startswith("/api/v1")
    }


def response_schema_names(spec: Spec) -> set[str]:
    names: set[str] = set()
    for item in spec["paths"].values():
        for operation in item.values():
            for response in operation.get("responses", {}).values():
                ref = response.get("content", {}).get("application/json", {}).get("schema", {})
                if "$ref" in ref:
                    names.add(ref["$ref"].rsplit("/", 1)[-1])
    return names


def property_names_of(spec: Spec, schema: str, seen: set[str] | None = None) -> set[str]:
    """스키마와 그것이 참조하는 모든 스키마의 속성 이름(순환 참조는 한 번만)."""
    seen = seen if seen is not None else set()
    if schema in seen:
        return set()
    seen.add(schema)
    properties = spec["components"]["schemas"][schema].get("properties", {})
    names = set(properties)
    for prop in properties.values():
        refs = [prop.get("$ref"), prop.get("items", {}).get("$ref")]
        refs += [option.get("$ref") for option in prop.get("anyOf", [])]
        for ref in filter(None, refs):
            names |= property_names_of(spec, ref.rsplit("/", 1)[-1], seen)
    return names


async def given_documentation_disabled(api: Api) -> None:
    """문서 노출이 꺼진 설정으로 앱이 떠 있다."""
    await api.reopen(enable_docs=False)


async def when_open(api: Api, path: str) -> Response:
    return await api.get(path)


async def when_preflight(api: Api, *, origin: str, path: str = "/api/v1/users") -> Response:
    """브라우저가 보내는 CORS 사전 요청(OPTIONS)."""
    return await api.request(
        "OPTIONS",
        path,
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
