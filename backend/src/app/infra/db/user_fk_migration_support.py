"""사용자 FK 마이그레이션(0d248153ec93)이 쓰는 매칭 로직과 SQL 도우미. ORM 모델에 의존하지 않는다.

문자열로 저장된 사용자 참조(로그인 id 또는 자유 입력 이름)를 users.id로 바꾸기 위한 규칙과,
변환 불가 데이터의 보고 형식을 한 곳에 둔다. 이미 적용된 리비전이 import하므로 동작을 바꾸지 않는다.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import sqlalchemy as sa

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping
    from uuid import UUID

EXAMPLE_LIMIT = 10
BLANK = "(빈 값)"


@dataclass(frozen=True, slots=True)
class DirectoryUser:
    id: UUID
    login_id: str
    display_name: str | None


def load_name_map(path: str | None) -> dict[str, str]:
    """`-x name_map=<json 경로>`: 사람이 검토한 {"이름": "login_id"}. 없으면 빈 매핑."""
    if not path:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError(f"name_map 파일을 읽을 수 없습니다: {path} ({error})") from error
    if not isinstance(data, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in data.items()
    ):
        raise RuntimeError('name_map은 {"이름": "login_id"} 형태의 JSON 객체여야 합니다')
    return {key.strip().lower(): value.strip().lower() for key, value in data.items()}


class UserMatcher:
    """login_id 일치 또는 이름(표시 이름 유일 일치, name_map 우선)으로 users.id를 찾는다."""

    def __init__(self, users: Iterable[DirectoryUser], name_map: Mapping[str, str]) -> None:
        self._by_login: dict[str, UUID] = {}
        names: defaultdict[str, list[UUID]] = defaultdict(list)
        for user in users:
            self._by_login[user.login_id.strip().lower()] = user.id
            if user.display_name and user.display_name.strip():
                names[user.display_name.strip().lower()].append(user.id)
        self._by_name = {name: ids[0] for name, ids in names.items() if len(ids) == 1}
        unknown = sorted(set(name_map.values()) - set(self._by_login))
        if unknown:
            raise RuntimeError(f"name_map이 users에 없는 login_id를 가리킵니다: {unknown}")
        self._name_map = dict(name_map)

    def by_login(self, value: str | None) -> UUID | None:
        return self._by_login.get((value or "").strip().lower())

    def by_name(self, value: str | None) -> UUID | None:
        key = (value or "").strip().lower()
        if key in self._name_map:
            return self._by_login[self._name_map[key]]
        return self._by_login.get(key) or self._by_name.get(key)


@dataclass
class Findings:
    """변환 불가 데이터: `<테이블.컬럼>=<건수> (예: ...)` 형태로 보고한다."""

    rows: dict[str, int] = field(default_factory=dict)
    examples: dict[str, list[str]] = field(default_factory=dict)

    def add(self, label: str, raw: str | None, count: int) -> None:
        self.rows[label] = self.rows.get(label, 0) + count
        shown = self.examples.setdefault(label, [])
        text = repr(raw) if raw and raw.strip() else BLANK
        if text not in shown and len(shown) < EXAMPLE_LIMIT:
            shown.append(text)

    def merge(self, other: Findings) -> None:
        for label, count in other.rows.items():
            self.rows[label] = self.rows.get(label, 0) + count
            shown = self.examples.setdefault(label, [])
            shown.extend(e for e in other.examples[label] if e not in shown)

    def __bool__(self) -> bool:
        return bool(self.rows)

    def message(self) -> str:
        return "; ".join(
            f"{label}={count} (예: {', '.join(self.examples[label])})"
            for label, count in self.rows.items()
        )


def resolve_column(
    label: str,
    counted_values: Iterable[tuple[str | None, int]],
    find: Callable[[str | None], UUID | None],
    findings: Findings,
    *,
    required: bool,
) -> dict[str, UUID]:
    """(원본 값, 행 수) 목록을 {원본 값: users.id}로 바꾼다. 못 맞춘 값은 findings에 쌓는다.

    NULL·빈 값은 required(NOT NULL이 될 컬럼)일 때만 변환 불가이고, 아니면 NULL로 둔다.
    """
    resolved: dict[str, UUID] = {}
    for raw, count in counted_values:
        if raw is None or not raw.strip():
            if required:
                findings.add(label, raw, count)
            continue
        found = find(raw)
        if found is None:
            findings.add(label, raw, count)
        else:
            resolved[raw] = found
    return resolved


Plan = dict[str, dict[str, "UUID"]]
SESSIONS = "auth_sessions.subject"
# (테이블.컬럼, 이름 계열인가, NOT NULL이 될 컬럼인가)
PLAN_COLUMNS = (
    ("deals.owner", True, True),
    ("deals.owner_user_id", False, False),  # 구 컬럼(등록자 login id)
    ("deal_actions.actor", True, True),
    ("deal_stage_changes.changed_by_subject", False, True),
    ("users.created_by", False, True),
    ("directory_settings.updated_by", False, False),
)
ABORT_MESSAGE = (
    "사용자로 변환할 수 없는 데이터가 있어 중단합니다"
    "(데이터는 지우지 않았고 스키마도 그대로입니다): {detail}. "
    "사용자를 등록하거나 -x name_map=<json 경로>로 이름을 지정한 뒤 다시 실행하세요. "
    "변환 불가 세션만 지워도 된다면 사람이 확인한 뒤 -x drop_orphan_sessions=1."
)


def build_plan(connection: sa.Connection, options: Mapping[str, str]) -> tuple[Plan, list[str]]:
    """문자열 사용자 참조를 {원본 값: users.id}로 푼다. 변환 불가가 있으면 RuntimeError.

    두 번째 값은 승인 옵션(drop_orphan_sessions=1)이 있을 때 삭제할 세션의 subject 목록이다.
    """
    users = [
        DirectoryUser(row[0], row[1], row[2])
        for row in connection.execute(sa.text("SELECT id, login_id, display_name FROM users"))
    ]
    matcher = UserMatcher(users, load_name_map(options.get("name_map")))
    findings = Findings()
    plan: Plan = {}
    for label, by_name, required in PLAN_COLUMNS:
        table, column = label.split(".")
        find = matcher.by_name if by_name else matcher.by_login
        values = counted_values(connection, table, column)
        plan[label] = resolve_column(label, values, find, findings, required=required)
    subjects = counted_values(connection, "auth_sessions", "subject")
    session_findings = Findings()
    plan[SESSIONS] = resolve_column(
        SESSIONS, subjects, matcher.by_login, session_findings, required=True
    )
    orphans = [raw for raw, _ in subjects if raw is not None and raw not in plan[SESSIONS]]
    if options.get("drop_orphan_sessions") != "1":
        findings.merge(session_findings)
        orphans = []
    if findings:
        raise RuntimeError(ABORT_MESSAGE.format(detail=findings.message()))
    return plan, orphans


def guard_downgrade(connection: sa.Connection) -> None:
    """퇴사자가 있거나 재직자 login_id가 겹치면(유니크 복구 불가) 아무것도 바꾸지 않고 중단."""
    resigned = connection.execute(
        sa.text("SELECT count(*) FROM users WHERE deleted_at IS NOT NULL")
    ).scalar_one()
    if resigned:
        raise RuntimeError(
            f"퇴사 처리된 사용자가 {resigned}명 있어 downgrade를 중단합니다"
            "(구 스키마에서 되살아나거나 login_id가 겹칩니다. 데이터는 바꾸지 않았습니다). "
            "사람이 퇴사 행을 정리한 뒤 다시 실행하세요."
        )
    duplicates = connection.execute(
        sa.text(
            "SELECT lower(login_id), count(*) FROM users"
            " GROUP BY lower(login_id) HAVING count(*) > 1"
        )
    ).all()
    if duplicates:
        detail = ", ".join(f"{login}={count}" for login, count in duplicates)
        raise RuntimeError(
            f"재직자 login_id가 대소문자 무시로 겹쳐 유니크를 복구할 수 없어 중단합니다: {detail}"
        )


def lock_tables(connection: sa.Connection, tables: Iterable[str]) -> None:
    """고정 순서로 ACCESS EXCLUSIVE 잠금(교착 방지). 테이블 이름은 호출한 리비전의 상수다."""
    for table in tables:
        connection.execute(sa.text(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE"))


def counted_values(
    connection: sa.Connection, table: str, column: str
) -> list[tuple[str | None, int]]:
    rows = connection.execute(
        sa.text(f"SELECT {column}, count(*) FROM {table} GROUP BY {column}")  # noqa: S608
    )
    return [(value, int(count)) for value, count in rows]


def fill_from_mapping(
    connection: sa.Connection, table: str, old: str, new: str, mapping: Mapping[str, UUID]
) -> None:
    """old 값이 키와 같은 행의 new 컬럼을 users.id로 채운다."""
    if mapping:
        connection.execute(
            sa.text(f"UPDATE {table} SET {new} = :uid WHERE {old} = :raw"),  # noqa: S608
            [{"uid": uid, "raw": raw} for raw, uid in mapping.items()],
        )
