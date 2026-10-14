"""결정적 사용자 id. 이름(= 로그인 아이디)마다 항상 같은 UUID를 돌려준다."""

from typing import Final
from uuid import NAMESPACE_URL, uuid5

from app.domain.user.value_objects import UserId

_NAMES: dict[UserId, str] = {}


def uid(name: str) -> UserId:
    """로그인 아이디 형식의 이름으로 결정적 UserId를 만든다(같은 이름은 같은 id)."""
    value = UserId(uuid5(NAMESPACE_URL, f"neoine-test-user:{name}"))
    _NAMES[value] = name
    return value


def login_of(user_id: UserId) -> str:
    """uid()로 만든 id의 로그인 아이디. 모르는 id는 id에서 유도한 값."""
    return _NAMES.get(user_id) or f"u{user_id.hex[:12]}"


OWNER_ID: Final = uid("owner")  # 팩토리 기본 Deal 담당자
ACTOR_ID: Final = uid("actor")  # 팩토리 기본 활동자
CHANGER_ID: Final = uid("changer")  # 팩토리 기본 단계 변경자
