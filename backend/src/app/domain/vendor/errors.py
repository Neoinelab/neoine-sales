from app.domain.common.errors import AlreadyExistsError, InvalidStateError, NotFoundError


class VendorNotFoundError(NotFoundError):
    def __init__(self, vendor_id: object) -> None:
        super().__init__("Vendor", vendor_id)


class SolutionNotFoundError(NotFoundError):
    def __init__(self, solution_id: object) -> None:
        super().__init__("Solution", solution_id)


class DuplicateVendorNameError(AlreadyExistsError):
    """다른 Vendor와 대소문자 무시로 같은 이름이다."""

    def __init__(self, name: object) -> None:
        super().__init__("Vendor 이름", name, message="이미 있는 Vendor 이름입니다.")


class DuplicateSolutionNameError(AlreadyExistsError):
    """같은 Vendor 안에 대소문자 무시로 같은 Solution 이름이 있다."""

    def __init__(self, name: object) -> None:
        super().__init__(
            "Solution 이름", name, message="이 Vendor에 이미 있는 Solution 이름입니다."
        )


class VendorInUseError(InvalidStateError):
    def __init__(self, usage: int) -> None:
        super().__init__(f"사용 중인 Vendor는 삭제할 수 없습니다. (Deal {usage}건)")
        self.usage = usage


class SolutionInUseError(InvalidStateError):
    def __init__(self, usage: int) -> None:
        super().__init__(f"사용 중인 Solution은 삭제할 수 없습니다. (Deal {usage}건)")
        self.usage = usage
