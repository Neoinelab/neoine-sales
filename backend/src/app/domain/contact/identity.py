"""같은 사람 판정. 프런트 `findSamePerson`과 같은 3단계 규칙이다."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.contact.entities import Contact
    from app.domain.contact.values import ContactDetails, ContactId, ContactKind


def find_same_person(
    candidates: Sequence[Contact],
    kind: ContactKind,
    details: ContactDetails,
    exclude_id: ContactId | None = None,
) -> Contact | None:
    """후보 중 같은 사람을 고른다.

    후보는 `ContactRepository.same_identity`가 이미 같은 종류·회사·이름으로 거른 것이다.
    같은 회사·이름·kind 정의는 `ContactRepository.same_identity` 한 곳이며 여기서 다시
    비교하지 않는다. `kind`는 호출부 호환을 위해 받기만 한다.

    1. 입력에 이메일이 있으면 같은 이메일(대소문자 무시)을 가진 후보
    2. 없으면 이메일이 없는 후보(이메일을 채워 넣는 경우)
    3. 입력에 이메일이 없으면 후보 중 첫째
    `exclude_id`는 제외하고, 동률은 id 숫자 오름차순.
    """
    same = sorted((c for c in candidates if c.id != exclude_id), key=lambda c: c.id)
    if details.email is None:
        return same[0] if same else None
    email = details.email.value.lower()
    for contact in same:
        if contact.details.email is not None and contact.details.email.value.lower() == email:
            return contact
    return next((c for c in same if c.details.email is None), None)
