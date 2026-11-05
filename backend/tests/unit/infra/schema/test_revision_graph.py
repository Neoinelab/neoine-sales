"""마이그레이션 최초 리비전(baseline): 이력은 하나로 통합되어 있고 빈 DB 생성 전용이다(DB 불필요).

과거 리비전 체인(30개)은 2026-11-05에 `00c3126aa926` 하나로 통합되었다. 이 리비전은 데이터를
지우지 않고, 되돌릴 수 없다.
"""

import ast
import inspect
import re
from typing import TYPE_CHECKING

import pytest
from alembic.script import ScriptDirectory

from tests.support.database import _alembic_config

if TYPE_CHECKING:
    from alembic.script import Script

BASELINE = "00c3126aa926"
# ondelete·onupdate 같은 FK 규칙 인자는 단어 경계로 구분한다
FORBIDDEN_IN_UPGRADE = (
    r"\bdelete\b",
    r"\btruncate\b",
    r"\bupdate\b",
    r"drop_table",
    r"drop_column",
    r"op\.execute",
)


def _baseline() -> Script:
    revision = ScriptDirectory.from_config(_alembic_config()).get_revision(BASELINE)
    assert revision is not None
    return revision


def test_the_history_has_one_revision_that_is_both_base_and_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    assert script.get_heads() == [BASELINE]
    assert script.get_bases() == [BASELINE]
    assert len(list(script.walk_revisions())) == 1


def test_the_baseline_has_no_parent_branch_or_dependency() -> None:
    revision = _baseline()

    assert revision.down_revision is None
    assert not revision.branch_labels
    assert revision.dependencies is None


def test_the_baseline_file_is_named_after_its_purpose() -> None:
    assert _baseline().path.endswith("20261105_00c3126aa926_baseline.py")


def test_the_baseline_downgrade_refuses_before_touching_the_database() -> None:
    module = _baseline().module

    with pytest.raises(RuntimeError) as raised:
        module.downgrade()

    assert "최초 리비전" in str(raised.value)
    assert "DB를 새로 만드세요" in str(raised.value)


def test_the_baseline_upgrade_never_removes_rows_or_columns() -> None:
    module = _baseline().module
    tree = ast.parse(inspect.getsource(module))
    body: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name != "downgrade":
            if ast.get_docstring(node) is not None:
                node.body = node.body[1:]  # docstring은 문장 검사에서 뺀다
            body.append(ast.unparse(node).lower())
    source = "\n".join(body)

    assert "def upgrade" in source
    for token in FORBIDDEN_IN_UPGRADE:
        assert re.search(token, source) is None, f"upgrade가 {token!r}를 사용한다"
