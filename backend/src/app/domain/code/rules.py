"""코드 이름 정규화·중복·key 생성·순서 규칙."""

import re
from typing import TYPE_CHECKING

from app.domain.code.errors import DuplicateCodeNameError
from app.domain.code.values import CODE_NAME_MAX, CodeKey
from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import reject_nul

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence
    from datetime import datetime

    from app.domain.code.entities import Code
    from app.domain.code.values import CodeId

KEY_MAX = 50
_REORDER_MESSAGE = "순서 목록이 올바르지 않습니다."


def normalize_code_name(raw: str) -> str:
    reject_nul(raw, "이름")
    name = raw.strip()
    if not name:
        raise InvalidValueError("이름을 입력하세요.")
    if len(name) > CODE_NAME_MAX:
        raise InvalidValueError(f"이름은 {CODE_NAME_MAX}자 이내로 입력하세요.")
    return name


def ensure_unique_name(siblings: Sequence[Code], name: str, self_id: CodeId | None = None) -> None:
    """같은 종류 코드 중 대소문자 무시로 같은 이름이 있으면 DuplicateCodeNameError."""
    lowered = name.lower()
    if any(c.id != self_id and c.name.lower() == lowered for c in siblings):
        raise DuplicateCodeNameError(name)


def _with_suffix(base: str, suffix: str) -> str:
    return base[: KEY_MAX - len(suffix)] + suffix


def generate_key(name: str, used_keys: Collection[str]) -> CodeKey:
    """이름에서 key를 만든다. 영문이 없으면 code_N, 충돌하면 _2, _3을 붙인다."""
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not base:
        number = 1
        while f"code_{number}" in used_keys:
            number += 1
        return CodeKey(f"code_{number}")
    if base[0].isdigit():
        base = f"c_{base}"
    base = base[:KEY_MAX]
    candidate, number = base, 1
    while candidate in used_keys:
        number += 1
        candidate = _with_suffix(base, f"_{number}")
    return CodeKey(candidate)


def reorder(codes: Sequence[Code], ordered_ids: Sequence[CodeId], now: datetime) -> list[Code]:
    """같은 종류 코드 전부를 ordered_ids 순서로 1부터 다시 매긴다(바뀐 코드만 갱신 시각 변경)."""
    by_id = {c.id: c for c in codes}
    if len(ordered_ids) != len(codes) or set(ordered_ids) != by_id.keys():
        raise InvalidValueError(_REORDER_MESSAGE)
    result: list[Code] = []
    for order, code_id in enumerate(ordered_ids, start=1):
        code = by_id[code_id]
        if code.order != order:
            code.place(order, now)
        result.append(code)
    return result
