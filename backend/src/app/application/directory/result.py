from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from app.application.ports.directory import VerificationStage

SUCCESS_MESSAGE: Final = "AD 설정을 확인했습니다"


@dataclass(frozen=True, slots=True)
class TestResult:
    __test__ = False
    success: bool
    stage: VerificationStage | None
    message: str
    base_dn: str | None = None
    test_token: str | None = field(default=None, repr=False)
