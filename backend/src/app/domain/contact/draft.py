"""ContactDraft 병합 규칙. 프런트 `mock/gateway/contactPlan.ts`의 같은 사람 병합과 같다."""

from app.domain.contact.values import ContactDetails


def merge_same_person(existing: ContactDetails, incoming: ContactDetails) -> ContactDetails:
    """같은 사람으로 판정된 기존 연락처에 입력을 합친다.

    회사명·담당자명은 기존 표기를 쓰고, 입력이 비어 있는 직급·이메일·전화는 기존 값을 지우지 않는다.
    """
    return ContactDetails(
        company=existing.company,
        name=existing.name,
        title=incoming.title if incoming.title else existing.title,
        email=incoming.email if incoming.email is not None else existing.email,
        phone=incoming.phone if incoming.phone is not None else existing.phone,
    )
