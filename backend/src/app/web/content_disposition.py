"""다운로드 `Content-Disposition` 헤더 값(RFC 6266, 5987)."""

from urllib.parse import quote

_PRINTABLE_ASCII_MIN = 0x20
_PRINTABLE_ASCII_MAX = 0x7E


def _fallback_name(file_name: str) -> str:
    """ASCII만 남긴 대체 이름. 비ASCII·제어 문자·`"`·`\\`는 코드 포인트마다 `_`로 바꾼다."""
    return "".join(
        char
        if _PRINTABLE_ASCII_MIN <= ord(char) <= _PRINTABLE_ASCII_MAX and char not in '"\\'
        else "_"
        for char in file_name
    )


def attachment_disposition(file_name: str) -> str:
    """`attachment; filename="<ASCII 대체>"; filename*=UTF-8''<퍼센트 인코딩>`."""
    return (
        f'attachment; filename="{_fallback_name(file_name)}"; '
        f"filename*=UTF-8''{quote(file_name, safe='')}"
    )
