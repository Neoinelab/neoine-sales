/** 연락처 정렬·묶음 규칙: 서버(`lower()` + 코드 포인트 순, CT-R13~R15)와 같다. 브라우저 로케일에 따라 달라지지 않는다. */

import type { Contact, ContactKind } from '../../../shared/model/types'

/** 문자열을 코드 포인트 순으로 비교한다(UTF-16 단위가 아니라 서버 DB와 같은 기준). */
export function compareCodePoints(a: string, b: string): number {
  const left = Array.from(a)
  const right = Array.from(b)
  const length = Math.min(left.length, right.length)
  for (let i = 0; i < length; i += 1) {
    const diff = (left[i] as string).codePointAt(0)! - (right[i] as string).codePointAt(0)!
    if (diff !== 0) return diff
  }
  return left.length - right.length
}

const byId = (a: Contact, b: Contact) => a.id - b.id
const lower = (text: string) => text.toLowerCase()

/** 목록 정렬: 고객 먼저 → lower(회사명) → lower(담당자명) → id. */
export function compareForList(a: Contact, b: Contact): number {
  return (
    (a.kind === b.kind ? 0 : a.kind === 'customer' ? -1 : 1) ||
    compareCodePoints(lower(a.company), lower(b.company)) ||
    compareCodePoints(lower(a.name), lower(b.name)) ||
    byId(a, b)
  )
}

/** 회사 목록: lower(회사명)이 같으면 하나로 묶고 표기는 먼저 등록된 연락처(createdAt, id)의 것. 정렬은 lower(회사명) 코드 포인트 순. */
export function companiesOf(contacts: readonly Contact[], kind: ContactKind): string[] {
  const first = new Map<string, Contact>()
  for (const c of [...contacts].filter((x) => x.kind === kind).sort((a, b) => a.createdAt.localeCompare(b.createdAt) || byId(a, b))) {
    if (!first.has(lower(c.company))) first.set(lower(c.company), c)
  }
  return [...first.entries()].sort(([a], [b]) => compareCodePoints(a, b)).map(([, c]) => c.company)
}

/** 회사별 담당자: 회사명 대소문자 무시, lower(담당자명) 코드 포인트 순 → id. */
export function peopleOf(contacts: readonly Contact[], kind: ContactKind, company: string): Contact[] {
  return contacts
    .filter((c) => c.kind === kind && lower(c.company) === lower(company))
    .sort((a, b) => compareCodePoints(lower(a.name), lower(b.name)) || byId(a, b))
}
