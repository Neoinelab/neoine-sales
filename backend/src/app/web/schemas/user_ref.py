"""응답에서 사용자를 가리키는 공통 형태. 표기(label)는 도메인 UserRef가 만든 값을 그대로 쓴다."""

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from app.domain.user.value_objects import UserId
    from app.domain.user.value_objects import UserRef as DomainUserRef
    from app.web.use_case_provider import UseCaseProvider


class UserRef(BaseModel):
    """OpenAPI 스키마 이름이 `UserRef`다(프런트가 이 이름으로 생성 타입을 쓴다)."""

    id: str
    name: str
    resigned: bool
    label: str

    @classmethod
    def from_domain(cls, ref: DomainUserRef) -> UserRef:
        return cls(
            id=str(ref.id),
            name=ref.name,
            resigned=ref.resigned,
            label=ref.label,
        )


async def resolve_refs(
    provider: UseCaseProvider, user_ids: Collection[UserId | None]
) -> Mapping[UserId, DomainUserRef]:
    """응답에 나올 사용자 id를 한 번에 표시용 참조로 바꾼다(퇴사자 포함, None은 무시)."""
    ids = {user_id for user_id in user_ids if user_id is not None}
    return await provider.resolve_user_refs().execute(ids)


def ref_of(refs: Mapping[UserId, DomainUserRef], user_id: UserId) -> UserRef:
    """FK가 보장하므로 항상 있다. 없으면 정합이 깨진 것이라 KeyError로 드러낸다."""
    return UserRef.from_domain(refs[user_id])
