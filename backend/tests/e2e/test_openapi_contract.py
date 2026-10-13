"""API 계약 드리프트 검사: 코드가 만드는 OpenAPI가 커밋된 backend/openapi.json과 같아야 한다.

API를 바꾸면 `scripts/export_openapi.py`로 파일을 갱신하고 프론트엔드 타입을 다시 생성한다.
"""

import json
from pathlib import Path

from app.main import create_app
from tests.e2e.conftest import make_settings
from tests.fakes.use_cases import FakeUseCases

COMMITTED = Path(__file__).resolve().parents[2] / "openapi.json"


def test_committed_openapi_matches_the_application() -> None:
    generated = create_app(settings=make_settings(), use_cases=FakeUseCases()).openapi()

    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))

    assert generated == committed, (
        "API가 바뀌었습니다. `uv run python scripts/export_openapi.py`로 openapi.json을 갱신하세요."
    )


def test_every_endpoint_documents_its_error_responses() -> None:
    schema = create_app(settings=make_settings(), use_cases=FakeUseCases()).openapi()

    for path, operations in schema["paths"].items():
        if not path.startswith("/api/v1/") or path.startswith("/api/v1/auth/"):
            continue
        for method, operation in operations.items():
            responses = operation["responses"]
            has_input = "parameters" in operation or "requestBody" in operation
            if has_input:  # 입력이 없는 엔드포인트(GET /settings/directory)는 422가 나올 수 없다
                assert "422" in responses, f"{method.upper()} {path}에 422 응답 문서가 없다"
            assert "401" in responses, f"{method.upper()} {path}에 401 응답 문서가 없다"


def test_deal_search_text_params_document_max_length() -> None:
    schema = create_app(settings=make_settings(), use_cases=FakeUseCases()).openapi()

    params = {p["name"]: p for p in schema["paths"]["/api/v1/deals"]["get"]["parameters"]}

    for name in ("keyword", "owner", "vendor"):
        lengths = [
            option["maxLength"]
            for option in params[name]["schema"]["anyOf"]
            if "maxLength" in option
        ]
        assert lengths == [100], f"{name} 파라미터에 maxLength 100이 없다"


def test_customer_and_partner_search_params_document_max_length() -> None:
    schema = create_app(settings=make_settings(), use_cases=FakeUseCases()).openapi()

    for path in ("/api/v1/customers", "/api/v1/partners"):
        params = {p["name"]: p for p in schema["paths"][path]["get"]["parameters"]}
        assert {"keyword", "offset", "limit"} <= set(params), path
        lengths = [
            option["maxLength"]
            for option in params["keyword"]["schema"]["anyOf"]
            if "maxLength" in option
        ]
        assert lengths == [100], f"{path}의 keyword 파라미터에 maxLength 100이 없다"


def test_stage_endpoints_share_the_deals_tag() -> None:
    schema = create_app(settings=make_settings(), use_cases=FakeUseCases()).openapi()

    tags = {
        path: operation["tags"]
        for path in (
            "/api/v1/deals/{deal_id}/stage",
            "/api/v1/deals/{deal_id}/stage-changes",
            "/api/v1/deals/pipeline",
        )
        for operation in schema["paths"][path].values()
    }

    assert tags == {
        "/api/v1/deals/{deal_id}/stage": ["deals"],
        "/api/v1/deals/{deal_id}/stage-changes": ["deals"],
        "/api/v1/deals/pipeline": ["deals"],
    }


def test_customer_and_partner_delete_document_the_409_for_referencing_deals() -> None:
    schema = create_app(settings=make_settings(), use_cases=FakeUseCases()).openapi()

    for path in ("/api/v1/customers/{customer_id}", "/api/v1/partners/{partner_id}"):
        responses = schema["paths"][path]["delete"]["responses"]
        assert "409" in responses, f"DELETE {path}에 409 응답 문서가 없다"
