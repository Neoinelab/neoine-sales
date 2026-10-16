"""한국어 조사 도우미. 프런트 `shared/model/text.ts`와 같은 받침 규칙이다.

한글은 받침으로, 숫자는 0 1 3 6 7 8만 받침으로, 영문은 끝 글자가 l m n k p b g c x일 때만
받침이 있다고 본다(발음 규칙의 근사).
"""

_HANGUL_FIRST = 0xAC00
_HANGUL_LAST = 0xD7A3
_FINAL_CLUSTERS = 28  # 한글 음절 한 묶음의 받침 종류 수(받침 없음 포함)
_RIEUL = 8  # ㄹ 받침의 인덱스
_DIGITS_WITH_FINAL = "013678"
_LETTERS_WITH_FINAL = "lmnkpbgcx"


def _last_char(text: str) -> str:
    stripped = text.rstrip()
    return stripped[-1] if stripped else ""


def _is_hangul(char: str) -> bool:
    return _HANGUL_FIRST <= ord(char) <= _HANGUL_LAST


def _has_final_sound(text: str) -> bool:
    last = _last_char(text)
    if not last:
        return False
    if _is_hangul(last):
        return (ord(last) - _HANGUL_FIRST) % _FINAL_CLUSTERS != 0
    if last in "0123456789":
        return last in _DIGITS_WITH_FINAL
    return last.lower() in _LETTERS_WITH_FINAL


def _is_rieul_final(text: str) -> bool:
    last = _last_char(text)
    return (
        bool(last) and _is_hangul(last) and (ord(last) - _HANGUL_FIRST) % _FINAL_CLUSTERS == _RIEUL
    )


def with_ro(text: str) -> str:
    """'로' / '으로'. ㄹ 받침은 '로'."""
    if _has_final_sound(text) and not _is_rieul_final(text):
        return f"{text}으로"
    return f"{text}로"


def with_ga(text: str) -> str:
    """'가' / '이'."""
    return f"{text}이" if _has_final_sound(text) else f"{text}가"


def with_wa(text: str) -> str:
    """'와' / '과'."""
    return f"{text}과" if _has_final_sound(text) else f"{text}와"
