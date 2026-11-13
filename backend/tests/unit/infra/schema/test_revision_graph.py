"""마이그레이션 리비전 그래프: 최초 리비전(baseline)과 그 뒤의 세 리비전(DB 불필요).

과거 리비전 체인(30개)은 2026-11-05에 `00c3126aa926` 하나로 통합되었다. 이 리비전은 데이터를
지우지 않고, 되돌릴 수 없다. 2026-11-13에 업무 날짜 컬럼을 date로 바꾸는 `b4d7e2a9c613`이
그 뒤에 붙었고, 같은 날 사용자 등록자·퇴사 사유를 없애는 `c8e3f1a7d295`가 head가 되었다
(SC-R20, SC-R21). 같은 날 `deals.vendor_id`를 NOT NULL로 바꾸는 `e6b1d4f8a302`가 head가 되었다
(SC-R22).
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
DATE_REVISION = "b4d7e2a9c613"
USER_COLUMNS_REVISION = "c8e3f1a7d295"
HEAD = "e6b1d4f8a302"
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


def test_the_history_has_the_baseline_as_base_and_the_vendor_required_revision_as_head() -> None:
    """리비전 그래프의 base는 기준선, head는 Deal Vendor 필수 리비전 하나다.

    테스트 코드: SC-001
    """
    # given: backend/alembic의 리비전 그래프
    script = ScriptDirectory.from_config(_alembic_config())

    # when: head와 base 목록을 읽는다
    heads, bases = script.get_heads(), script.get_bases()

    # then: head는 Deal Vendor 필수 리비전, base는 기준선이고 리비전은 4개다
    assert heads == [HEAD]
    assert bases == [BASELINE]
    assert len(list(script.walk_revisions())) == 4
    # then: 날짜 전환 리비전 → 사용자 컬럼 정리 리비전 → Deal Vendor 필수 리비전으로 이어진다
    dates = script.get_revision(DATE_REVISION)
    users = script.get_revision(USER_COLUMNS_REVISION)
    head = script.get_revision(HEAD)
    assert dates is not None
    assert users is not None
    assert head is not None
    assert dates.down_revision == BASELINE
    assert users.down_revision == DATE_REVISION
    assert head.down_revision == USER_COLUMNS_REVISION


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


def test_the_date_revision_follows_the_baseline_and_has_a_downgrade() -> None:
    """날짜 전환 리비전은 기준선을 부모로 하고 정해진 파일 이름이며 downgrade 함수가 있다.

    테스트 코드: SC-039
    """
    # given: DB 없이 읽은 날짜 전환 리비전 정보와 모듈
    revision = ScriptDirectory.from_config(_alembic_config()).get_revision(DATE_REVISION)
    assert revision is not None

    # when: 부모·브랜치 라벨·파일 경로·downgrade 함수를 읽는다
    module = revision.module

    # then: 부모는 기준선, 브랜치 라벨은 비고, 파일 이름은 정해진 값이다
    assert revision.down_revision == BASELINE
    assert not revision.branch_labels
    assert revision.path.endswith("20261113_b4d7e2a9c613_business_dates.py")
    # then: downgrade와 upgrade 함수가 있고 downgrade는 거부 문구가 소스에 없다(되돌릴 수 있다)
    assert callable(module.downgrade)
    assert callable(module.upgrade)
    assert "최초 리비전" not in inspect.getsource(module.downgrade)


def test_the_user_columns_revision_follows_the_date_revision_and_has_a_downgrade() -> None:
    """사용자 컬럼 정리 리비전은 날짜 전환 리비전을 부모로 하고 파일 이름·downgrade가 정해져 있다.

    테스트 코드: SC-040
    """
    # given: DB 없이 읽은 사용자 컬럼 정리 리비전 정보와 모듈
    revision = ScriptDirectory.from_config(_alembic_config()).get_revision(USER_COLUMNS_REVISION)
    assert revision is not None

    # when: 부모·브랜치 라벨·파일 경로·downgrade 함수를 읽는다
    module = revision.module

    # then: 부모는 날짜 전환 리비전, 브랜치 라벨은 비고, 파일 이름은 정해진 값이다
    assert revision.down_revision == DATE_REVISION
    assert not revision.branch_labels
    assert revision.path.endswith("20261113_c8e3f1a7d295_drop_user_creator_and_reason.py")
    # then: downgrade와 upgrade 함수가 있고 downgrade는 거부 문구가 소스에 없다(되돌릴 수 있다)
    assert callable(module.downgrade)
    assert callable(module.upgrade)
    assert "최초 리비전" not in inspect.getsource(module.downgrade)


def test_the_user_columns_upgrade_drops_only_the_two_columns_and_changes_no_rows() -> None:
    """사용자 컬럼 정리 upgrade에는 행을 지우거나 바꾸는 문장이 없고 drop_column은 두 컬럼뿐이다.

    테스트 코드: SC-043
    """
    # given: 리비전 c8e3f1a7d295 모듈 소스의 upgrade 함수 본문(docstring 제외, 소문자)
    revision = ScriptDirectory.from_config(_alembic_config()).get_revision(USER_COLUMNS_REVISION)
    assert revision is not None
    tree = ast.parse(inspect.getsource(revision.module))
    upgrade = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    if ast.get_docstring(upgrade) is not None:
        upgrade.body = upgrade.body[1:]
    source = ast.unparse(upgrade).lower()

    # when: 금지 토큰과 drop_column 호출을 찾는다
    forbidden = [t for t in FORBIDDEN_IN_UPGRADE if t != r"drop_column"]
    drops = re.findall(r"drop_column\(\s*['\"](\w+)['\"]\s*,\s*['\"](\w+)['\"]", source)

    # then: 행을 바꾸는 토큰이 없고 drop_column은 users의 두 컬럼뿐이다
    for token in forbidden:
        assert re.search(token, source) is None, f"upgrade가 {token!r}를 사용한다"
    assert sorted(drops) == [("users", "created_by_user_id"), ("users", "delete_reason")]


def test_the_vendor_required_revision_follows_the_user_columns_revision() -> None:
    """Deal Vendor 필수 리비전은 사용자 컬럼 정리 리비전을 부모로 하고 파일 이름·downgrade가 있다.

    테스트 코드: SC-044
    """
    # given: DB 없이 읽은 Deal Vendor 필수 리비전 정보와 모듈
    revision = ScriptDirectory.from_config(_alembic_config()).get_revision(HEAD)
    assert revision is not None

    # when: 부모·브랜치 라벨·파일 경로·downgrade 함수를 읽는다
    module = revision.module

    # then: 부모는 사용자 컬럼 정리 리비전, 브랜치 라벨은 비고, 파일 이름은 정해진 값이다
    assert revision.down_revision == USER_COLUMNS_REVISION
    assert not revision.branch_labels
    assert revision.path.endswith("20261113_e6b1d4f8a302_deal_vendor_required.py")
    # then: downgrade와 upgrade 함수가 있고 downgrade는 거부 문구가 소스에 없다(되돌릴 수 있다)
    assert callable(module.downgrade)
    assert callable(module.upgrade)
    assert "최초 리비전" not in inspect.getsource(module.downgrade)


def test_the_vendor_required_upgrade_never_removes_or_rewrites_rows_or_columns() -> None:
    """Deal Vendor 필수 upgrade 본문에는 행·컬럼을 지우거나 바꾸는 문장이 없다.

    테스트 코드: SC-048
    """
    # given: 리비전 e6b1d4f8a302 모듈 소스의 upgrade 함수 본문(docstring 제외, 소문자)
    revision = ScriptDirectory.from_config(_alembic_config()).get_revision(HEAD)
    assert revision is not None
    tree = ast.parse(inspect.getsource(revision.module))
    upgrade = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    if ast.get_docstring(upgrade) is not None:
        upgrade.body = upgrade.body[1:]
    source = ast.unparse(upgrade).lower()

    # when: 금지 토큰을 찾는다(행을 지우거나 바꾸는 문장, 테이블·컬럼 drop, insert)
    # then: 하나도 없고 NOT NULL 변경(alter_column)은 있다
    for token in (*FORBIDDEN_IN_UPGRADE, r"\binsert\b"):
        assert re.search(token, source) is None, f"upgrade가 {token!r}를 사용한다"
    assert "alter_column" in source
