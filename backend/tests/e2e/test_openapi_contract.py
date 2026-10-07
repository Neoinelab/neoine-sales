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
        if not path.startswith("/api/v1/"):
            continue
        for method, operation in operations.items():
            assert "422" in operation["responses"], (
                f"{method.upper()} {path}에 422 응답 문서가 없다"
            )
