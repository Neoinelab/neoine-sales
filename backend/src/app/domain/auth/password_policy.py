"""로컬 계정 비밀번호 정책: 8자 이상(최대는 Password가 검사), 아이디와 같으면 거부."""

from typing import TYPE_CHECKING

from app.domain.auth.errors import WeakPasswordError

if TYPE_CHECKING:
    from app.domain.auth.credentials import LoginId, Password

PASSWORD_MIN = 8


def ensure_acceptable_password(password: Password, login_id: LoginId) -> None:
    text = password.reveal()
    if len(text) < PASSWORD_MIN:
        raise WeakPasswordError(f"비밀번호는 {PASSWORD_MIN}자 이상이어야 합니다")
    if text.strip().lower() == login_id.value:
        raise WeakPasswordError("비밀번호는 아이디와 같을 수 없습니다")
