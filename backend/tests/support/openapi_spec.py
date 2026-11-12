"""OpenAPI 계약 해석 도우미(PL-R20~R23): 앱이 만드는 계약을 읽고 경로·스키마를 훑는다.

계약은 local 설정과 Fake 유스케이스로 조립한 앱의 `openapi()`다(DB에 접속하지 않는다).
"""

import json
from pathlib import Path
from typing import Any

from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

Spec = dict[str, Any]
UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
COMMITTED = Path(__file__).resolve().parents[2] / "openapi.json"
HTTP_METHODS = frozenset({"get", "put", "post", "delete", "patch", "options", "head"})


def app_contract() -> Spec:
    """앱이 만드는 계약(local 설정·Fake 유스케이스·문서 노출 켬)."""
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    return app.openapi()


def committed_contract() -> Spec:
    """저장소에 커밋된 `backend/openapi.json`."""
    loaded: Spec = json.loads(COMMITTED.read_text(encoding="utf-8"))
    return loaded


def api_routes_of(spec: Spec) -> set[tuple[str, str]]:
    """OpenAPI에 문서화된 (메서드, 경로) 중 헬스체크와 /api/v1 아래의 것."""
    return {
        (method.upper(), path)
        for path, item in spec["paths"].items()
        for method in item
        if path in {"/healthz", "/readyz"} or path.startswith("/api/v1")
    }


def operation_of(spec: Spec, method: str, path: str) -> dict[str, Any]:
    operation: dict[str, Any] = spec["paths"][path][method.lower()]
    return operation


def response_schema_names(spec: Spec) -> set[str]:
    """응답 본문(JSON)이 직접 참조하는 스키마 이름 전부."""
    names: set[str] = set()
    for item in spec["paths"].values():
        for operation in item.values():
            for response in operation.get("responses", {}).values():
                ref = response.get("content", {}).get("application/json", {}).get("schema", {})
                if "$ref" in ref:
                    names.add(ref["$ref"].rsplit("/", 1)[-1])
    return names


def reachable_properties(
    spec: Spec, schema: str, seen: set[str] | None = None
) -> dict[str, dict[str, Any]]:
    """스키마와 그것이 참조하는 모든 스키마의 속성(`스키마.이름` -> 정의). 순환은 한 번만 본다."""
    seen = seen if seen is not None else set()
    if schema in seen:
        return {}
    seen.add(schema)
    found: dict[str, dict[str, Any]] = {}
    properties = spec["components"]["schemas"][schema].get("properties", {})
    for name, prop in properties.items():
        found[f"{schema}.{name}"] = prop
        refs = [prop.get("$ref"), prop.get("items", {}).get("$ref")]
        refs += [option.get("$ref") for option in prop.get("anyOf", [])]
        for ref in filter(None, refs):
            found |= reachable_properties(spec, ref.rsplit("/", 1)[-1], seen)
    return found


def id_path_routes(spec: Spec) -> list[tuple[str, str, list[str]]]:
    """정수 id 경로 파라미터를 가진 (메서드, 경로 템플릿, id 파라미터 이름들). 정렬해서 돌려준다."""
    found = []
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method not in HTTP_METHODS:
                continue
            names = [
                p["name"]
                for p in operation.get("parameters", [])
                if p["in"] == "path" and "integer" in str(p["schema"])
            ]
            if names:
                found.append((method.upper(), path, names))
    return sorted(found)
