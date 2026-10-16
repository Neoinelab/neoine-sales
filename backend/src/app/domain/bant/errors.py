from app.domain.common.errors import AlreadyExistsError, InvalidStateError, NotFoundError


class BantLabelNotFoundError(NotFoundError):
    def __init__(self, label_id: object) -> None:
        super().__init__("BANT Label", label_id)


class DuplicateLabelNameError(AlreadyExistsError):
    """같은 구분 안에 대소문자 무시로 같은 Label 이름이 있다."""

    def __init__(self, name: object) -> None:
        super().__init__("Label 이름", name)
        self.args = ("같은 구분에 이미 있는 Label 이름입니다.",)


class LabelInUseError(InvalidStateError):
    def __init__(self, usage: int) -> None:
        super().__init__(f"사용 중인 Label은 삭제할 수 없습니다. (Deal {usage}건)")
        self.usage = usage
