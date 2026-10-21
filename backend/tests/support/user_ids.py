"""결정적 사용자 id. 이름(= 로그인 아이디)마다 프로세스 안에서 항상 같은 정수를 돌려준다."""

from typing import Final

from app.domain.user.value_objects import UserId
from tests.support.ids import new_id

_IDS: dict[str, UserId] = {}
_NAMES: dict[UserId, str] = {}


def uid(name: str) -> UserId:
    """로그인 아이디 형식의 이름으로 결정적 UserId를 만든다(같은 이름은 같은 id, 10억대 번호)."""
    if name not in _IDS:
        _IDS[name] = UserId(new_id())
        _NAMES[_IDS[name]] = name
    return _IDS[name]


def login_of(user_id: UserId) -> str:
    """uid()로 만든 id의 로그인 아이디. 모르는 id는 id에서 유도한 값."""
    return _NAMES.get(user_id) or f"u{user_id}"


OWNER_ID: Final = uid("owner")  # 팩토리 기본 Deal 담당자
ACTOR_ID: Final = uid("actor")  # 팩토리 기본 활동자
CHANGER_ID: Final = uid("changer")  # 팩토리 기본 단계 변경자
