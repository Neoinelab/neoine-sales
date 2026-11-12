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
    """리비전 그래프의 base와 head가 모두 기준선 하나다.

    테스트 코드: SC-001
    """
    # given: backend/alembic의 리비전 그래프
    script = ScriptDirectory.from_config(_alembic_config())

    # when: head와 base 목록을 읽는다
    heads, bases = script.get_heads(), script.get_bases()

    # then: 둘 다 기준선 하나이고 리비전은 1개뿐이다
    assert heads == [BASELINE]
    assert bases == [BASELINE]
    assert len(list(script.walk_revisions())) == 1


def test_the_baseline_has_no_parent_branch_or_dependency() -> None:
    """기준선에는 부모·브랜치 라벨·의존 리비전이 없다.

    테스트 코드: SC-002
    """
    # when: 기준선 리비전 정보를 읽는다
    revision = _baseline()

    # then: 부모 None, 브랜치 라벨 없음, 의존 None
    assert revision.down_revision is None
    assert not revision.branch_labels
    assert revision.dependencies is None


def test_the_baseline_file_is_named_after_its_purpose() -> None:
    """기준선 파일 이름이 20261105_00c3126aa926_baseline.py다.

    테스트 코드: SC-003
    """
    # when: 기준선 리비전의 파일 경로를 읽는다
    path = _baseline().path

    # then: 경로가 정해진 파일 이름으로 끝난다
    assert path.endswith("20261105_00c3126aa926_baseline.py")


def test_the_baseline_downgrade_refuses_before_touching_the_database() -> None:
    """기준선 downgrade 함수는 DB를 건드리기 전에 안내 문구와 함께 거부한다.

    테스트 코드: SC-009
    """
    # given: DB 연결 없이 불러온 기준선 모듈
    module = _baseline().module

    # when: downgrade()를 호출한다
    with pytest.raises(RuntimeError) as raised:
        module.downgrade()

    # then: 안내 문구가 들어 있다
    assert "최초 리비전" in str(raised.value)
    assert "DB를 새로 만드세요" in str(raised.value)


def test_the_baseline_upgrade_never_removes_rows_or_columns() -> None:
    """기준선 upgrade 본문에는 행·컬럼을 지우거나 바꾸는 문장이 없다.

    테스트 코드: SC-011
    """
    # given: downgrade를 뺀 함수들의 본문(docstring 제외, 소문자)
    module = _baseline().module
    tree = ast.parse(inspect.getsource(module))
    body: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name != "downgrade":
            if ast.get_docstring(node) is not None:
                node.body = node.body[1:]  # docstring은 문장 검사에서 뺀다
            body.append(ast.unparse(node).lower())
    source = "\n".join(body)

    # when·then: 금지 토큰을 찾으면 하나도 없다
    assert "def upgrade" in source
    for token in FORBIDDEN_IN_UPGRADE:
        assert re.search(token, source) is None, f"upgrade가 {token!r}를 사용한다"
