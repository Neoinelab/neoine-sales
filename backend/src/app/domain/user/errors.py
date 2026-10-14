from app.domain.common.errors import InvalidStateError, NotFoundError


class UserNotFoundError(NotFoundError):
    def __init__(self, user_id: object) -> None:
        super().__init__("사용자", user_id)


class UserInUseError(InvalidStateError):
    """다른 데이터가 참조하는 사용자는 물리 삭제할 수 없다(저장소 delete가 FK 때문에 던진다)."""

    def __init__(self, user_id: object) -> None:
        super().__init__(f"다른 데이터가 참조하고 있어 삭제할 수 없습니다: {user_id}")


class AmbiguousLoginIdError(InvalidStateError):
    """같은 login_id의 재직 행이 둘 이상이라 한 사람으로 특정할 수 없다(정합 위반).

    메시지에는 건수만 담는다. login_id 값은 넣지 않는다.
    """

    def __init__(self, count: int) -> None:
        super().__init__(f"같은 로그인 아이디의 재직 사용자가 {count}건 있습니다")
        self.count = count
