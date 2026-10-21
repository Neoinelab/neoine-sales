"""계층 규칙(AC-21): domain은 uuid를 쓰지 않고, application의 uuid4는 첨부 저장 키 하나뿐이다.

id는 application이 `IdAllocator` Port로 먼저 받아 엔티티 팩토리에 넘긴다. 첨부 저장 키
(`upload_attachment.py`)는 디스크 파일 이름이라 PK와 별개로 무작위 값을 유지한다.
소스를 직접 읽어(ast) 검사하므로 import 방식(`import uuid`, `from uuid import ...`)을 가리지 않는다.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "src" / "app"
STORAGE_KEY_MODULE = "attachment/upload_attachment.py"


def _uuid_uses(path: Path) -> list[str]:
    """파일에서 uuid 모듈을 가져오거나 `uuid4`/`UUID`/`uuid.` 이름을 쓰는 곳."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [f"import {a.name}" for a in node.names if a.name.split(".")[0] == "uuid"]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "uuid":
            found += [f"from uuid import {a.name}" for a in node.names]
    return found


def _files(layer: str) -> list[Path]:
    return sorted((APP / layer).rglob("*.py"))


def test_domain_modules_do_not_import_uuid() -> None:
    files = _files("domain")

    assert files, "domain 소스를 찾지 못했다"
    offenders = {str(p.relative_to(APP)): _uuid_uses(p) for p in files if _uuid_uses(p)}
    assert offenders == {}


def test_application_uses_uuid4_only_for_the_attachment_storage_key() -> None:
    files = _files("application")

    assert files, "application 소스를 찾지 못했다"
    offenders = {
        str(p.relative_to(APP / "application")): _uuid_uses(p) for p in files if _uuid_uses(p)
    }
    assert offenders == {STORAGE_KEY_MODULE: ["from uuid import uuid4"]}
