"""Deal 목록 CSV 내보내기 규칙: 행 수 상한, 파일 이름, 수식 방지, 머리글 (DL-R33~R36)."""

from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from datetime import date

EXPORT_MAX_ROWS = 10_000

EXPORT_HEADER: tuple[str, ...] = (
    "Deal", "담당자", "고객사", "파트너사", "Vendor", "Product", "Status", "Forecast",
    "금액(단위:원)", "Expected Close", "최종 업데이트", "Next Action", "Due",
    "Next Action 상태",
)  # fmt: skip

_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def export_file_name(day: date) -> str:
    return f"Deals_{day:%Y%m%d}.csv"


def check_export_size(total: int) -> None:
    """상한을 넘으면 건수를 알려 주고 거절한다."""
    if total > EXPORT_MAX_ROWS:
        raise InvalidValueError(
            f"내려받을 Deal이 {EXPORT_MAX_ROWS:,}건을 넘습니다({total:,}건). "
            "조건을 좁혀 다시 시도하세요."
        )


def neutralize_formula(text: str) -> str:
    """스프레드시트가 수식으로 해석할 글자로 시작하면 앞에 '를 붙인다."""
    return f"'{text}" if text.startswith(_FORMULA_STARTS) else text
