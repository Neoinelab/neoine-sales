"""API 계약의 id 표기(AC-20): `"format": "uuid"`가 없고 id 필드·파라미터는 정수다.

앱이 만든 계약(`app.openapi()`)과 커밋된 `backend/openapi.json` 둘 다 확인한다. 둘이 같은지는
functional/platform의 드리프트 시나리오가 본다.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings
from tests.support.ids import MAX_ID

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
COMMITTED = Path(__file__).resolve().parents[3] / "openapi.json"
# id를 담는 속성·파라미터 이름. login_id(로그인 아이디 문자열)와 deal_code는 해당하지 않는다.
ID_NAMES = {
    "id",
    "user_id",
    "owner_user_id",
    "contact_id",
    "vendor_id",
    "action_type_id",
    "actor_user_id",
    "created_by_user_id",
    "action_id",
    "attachment_id",
    "type_id",
    "code_id",
    "label_id",
    "ordered_ids",
}


@pytest.fixture(scope="module", params=["app", "committed"])
def contract(request: pytest.FixtureRequest) -> dict[str, Any]:
    if request.param == "committed":
        loaded: dict[str, Any] = json.loads(COMMITTED.read_text(encoding="utf-8"))
        return loaded
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


def _types(schema: dict[str, Any]) -> set[str]:
    """스키마(anyOf·배열 항목 포함)에 나오는 type 값 전부."""
    found = {schema["type"]} if "type" in schema else set()
    for option in schema.get("anyOf", []):
        found |= _types(option)
    if "items" in schema:
        found |= _types(schema["items"])
    return found


def test_the_contract_has_no_uuid_format(contract: dict[str, Any]) -> None:
    assert '"format": "uuid"' not in json.dumps(contract, ensure_ascii=False)


def test_every_id_property_is_an_integer(contract: dict[str, Any]) -> None:
    wrong = {}
    for name, schema in contract["components"]["schemas"].items():
        for prop, definition in schema.get("properties", {}).items():
            if prop in ID_NAMES and "$ref" not in definition:
                types = _types(definition) - {"null"}
                if types not in ({"integer"}, {"array", "integer"}):
                    wrong[f"{name}.{prop}"] = sorted(types)

    assert wrong == {}


def test_every_id_path_and_query_parameter_is_an_integer(contract: dict[str, Any]) -> None:
    wrong = {}
    for path, operations in contract["paths"].items():
        for method, operation in operations.items():
            for parameter in operation.get("parameters", []):
                if parameter["name"] in ID_NAMES:
                    types = _types(parameter["schema"]) - {"null"}
                    if types != {"integer"}:
                        wrong[f"{method.upper()} {path} {parameter['name']}"] = sorted(types)

    assert wrong == {}


def test_id_path_parameters_document_the_allowed_range(contract: dict[str, Any]) -> None:
    ranges = {}
    for path, operations in contract["paths"].items():
        for method, operation in operations.items():
            for parameter in operation.get("parameters", []):
                if parameter["in"] == "path" and parameter["name"] in ID_NAMES:
                    schema = parameter["schema"]
                    ranges[f"{method.upper()} {path} {parameter['name']}"] = (
                        schema.get("minimum"),
                        schema.get("maximum"),
                    )

    assert ranges
    assert set(ranges.values()) == {(1, MAX_ID)}
