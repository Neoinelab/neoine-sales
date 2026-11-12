"""OpenAPI 계약 파일과 공통 문서화 규칙(PL-034~PL-038, PL-040).

계약은 local 설정·Fake 유스케이스로 조립한 앱의 `openapi()`다. 경로별 역할 분류는
`tests/support/permission_table.py`가 정한다. id 표기(PL-039)는 test_openapi_ids.py가 본다.
"""

from tests.support.openapi_spec import (
    api_routes_of,
    app_contract,
    committed_contract,
    operation_of,
    reachable_properties,
    response_schema_names,
)
from tests.support.permission_table import (
    ADMIN_ONLY,
    BUSINESS_READS,
    BUSINESS_WRITES,
    protected_routes,
)


def test_committed_openapi_matches_the_application_contract() -> None:
    """커밋된 계약 파일은 앱이 만드는 계약과 같다.

    테스트 코드: PL-034
    """
    # given: 커밋된 backend/openapi.json
    committed = committed_contract()
    # when: 앱 계약과 비교한다
    application = app_contract()
    # then: 둘이 같다(다르면 갱신 안내와 함께 실패한다)
    assert application == committed, (
        "API가 바뀌었습니다. `uv run python scripts/export_openapi.py`로 openapi.json을 갱신하세요."
    )


def test_every_endpoint_except_auth_documents_401_and_422_when_it_has_input() -> None:
    """인증 API를 뺀 모든 엔드포인트가 401과(입력이 있으면) 422를 문서화한다.

    테스트 코드: PL-035
    """
    # given: 앱 계약
    contract = app_contract()
    missing: list[str] = []
    # when: /api/v1/auth/**를 뺀 /api/v1 엔드포인트의 응답 목록을 본다
    for method, path in sorted(api_routes_of(contract)):
        if not path.startswith("/api/v1/") or path.startswith("/api/v1/auth/"):
            continue
        operation = operation_of(contract, method, path)
        responses = operation["responses"]
        has_input = "parameters" in operation or "requestBody" in operation
        # then: 모두 401이 있고 입력이 있으면 422도 있다
        if "401" not in responses:
            missing.append(f"{method} {path}: 401")
        if has_input and "422" not in responses:
            missing.append(f"{method} {path}: 422")
    assert missing == []


def test_every_protected_route_documents_401() -> None:
    """보호 경로는 모두 401을 문서화한다.

    테스트 코드: PL-036
    """
    # given: 앱 계약과 권한 표
    contract = app_contract()
    protected = protected_routes()
    # when: 권한 표의 보호 경로(내 정보 계열 포함) 응답 목록을 본다
    undocumented = [
        route for route in protected if "401" not in operation_of(contract, *route)["responses"]
    ]
    # then: 모두 401이 있다
    assert len(protected) > 80
    assert undocumented == []


def test_write_and_admin_endpoints_document_403_with_the_problem_schema() -> None:
    """업무 쓰기·관리자 전용 엔드포인트는 403을 Problem 스키마로 문서화한다.

    테스트 코드: PL-037
    """
    # given: 앱 계약과 권한 표
    contract = app_contract()
    wrong: list[str] = []
    # when: 업무 쓰기·관리자 전용 엔드포인트의 403 응답을 본다
    for route in [*BUSINESS_WRITES, *ADMIN_ONLY]:
        documented = operation_of(contract, *route)["responses"].get("403")
        # then: 있고 그 스키마가 Problem이다
        ref = documented["content"]["application/json"]["schema"]["$ref"] if documented else ""
        if ref != "#/components/schemas/Problem":
            wrong.append(f"{route}: {ref or '403 없음'}")
    assert wrong == []


def test_read_endpoints_for_every_role_do_not_document_403() -> None:
    """모든 역할이 쓰는 조회 엔드포인트는 403을 문서화하지 않는다.

    테스트 코드: PL-038
    """
    # given: 앱 계약과 권한 표
    contract = app_contract()
    # when: 업무 조회 엔드포인트의 응답 목록을 본다
    documented = [r for r in BUSINESS_READS if "403" in operation_of(contract, *r)["responses"]]
    # then: 403이 없다
    assert documented == []


def test_no_response_schema_has_a_password_value_field() -> None:
    """어떤 응답 스키마에도 비밀번호 값 필드가 없다.

    테스트 코드: PL-040
    """
    # given: 앱 계약
    contract = app_contract()
    # when: 응답이 참조하는 모든 스키마(중첩 포함)의 속성 이름을 본다
    leaked = {
        f"{name} -> {qualified}"
        for name in response_schema_names(contract)
        for qualified, prop in reachable_properties(contract, name).items()
        if "password" in qualified.rsplit(".", 1)[-1].lower() and prop.get("type") != "boolean"
    }
    # then: password가 들어간 속성은 boolean 플래그뿐이다
    assert leaked == set()
