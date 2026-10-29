/** Deal History 기록 규칙(A-0 계약, 구현은 A-1). 게이트웨이가 모든 변경에서 이 diff로 HistoryEntry를 만든다. */

import { BANT_CATEGORIES, BANT_CATEGORY_NAMES } from './constants'
import { AMOUNT_LABEL, formatThousandWon } from './money'
import { withWa } from './text'
import type { Deal, HistoryCategory } from './types'

export const HISTORY_CATEGORY_LABELS: Record<HistoryCategory, string> = {
  created: 'Deal 등록',
  status: 'Status',
  forecast: 'Forecast',
  amount: '금액',
  expectedClose: 'Expected Close',
  owner: 'Owner',
  partner: '파트너',
  contact: '고객 연락처',
  bant: 'BANT Label',
  action: 'Action',
  attachment: '첨부 파일',
  other: '기타',
}

/** HistoryEntry 한 건의 내용(id·시각·변경자·dealCode는 게이트웨이가 채운다). */
export interface HistoryDraft {
  category: HistoryCategory
  target: string
  before: string
  after: string
}

/** 값을 사람이 읽는 text로 바꾸기 위한 조회 함수들(코드 이름·사용자 표시명·연락처 표기·Label 이름). */
export interface HistoryLookup {
  statusName(key: string): string
  forecastName(key: string): string
  /** `userLabel` 규칙(퇴사자는 이름(퇴사)). */
  userName(id: number): string
  /** '회사명 담당자명' 형식. */
  contactName(id: number): string
  bantLabelName(id: number | null): string
  /** Vendor 이름. id가 null이거나 없으면 '선택 안 함'. */
  vendorName(id: number | null): string
}

/**
 * 변경 전/후 Deal을 비교해 History 초안 목록을 만든다.
 * 불변식
 * - 바뀐 필드마다 1건. 바뀌지 않았으면 0건(빈 배열).
 * - 이름·Vendor·Solution·Users count·견적·POC·구매절차는 category 'other'(target은 필드 표시명).
 * - 활성 파트너가 바뀌면 category 'partner', before/after는 contactName(없으면 '없음').
 * - `coChanged`가 있으면 요청 필드가 아닌 쪽의 after를 "계약완료 (Forecast Won과 함께 변경)"처럼 표기하거나
 *   별도 행으로 남긴다(구현 재량, 단 둘 다 기록되어야 한다).
 * - 금액·날짜는 콤마 숫자 + '원' / 'YYYY-MM-DD' text.
 */
export function diffDeal(
  before: Deal,
  after: Deal,
  lookup: HistoryLookup,
  coChanged?: readonly { field: 'statusKey' | 'forecastKey' }[],
): HistoryDraft[] {
  const out: HistoryDraft[] = []
  const push = (category: HistoryCategory, target: string, b: string, a: string): void => {
    if (b !== a) out.push({ category, target, before: b, after: a })
  }
  const co = new Set((coChanged ?? []).map((c) => c.field))

  push('status', 'Status', lookup.statusName(before.statusKey), withNote(lookup.statusName(after.statusKey), co.has('statusKey'), `Forecast ${lookup.forecastName(after.forecastKey)}`))
  push('forecast', 'Forecast', lookup.forecastName(before.forecastKey), withNote(lookup.forecastName(after.forecastKey), co.has('forecastKey'), `Status ${lookup.statusName(after.statusKey)}`))
  push('amount', AMOUNT_LABEL, formatThousandWon(before.revenueAmount), formatThousandWon(after.revenueAmount))
  push('expectedClose', 'Expected Close', before.revenueDate, after.revenueDate)
  push('owner', 'Owner', lookup.userName(before.ownerId), lookup.userName(after.ownerId))
  push('partner', '파트너', partnerText(before, lookup), partnerText(after, lookup))
  push('contact', '고객 연락처', lookup.contactName(before.customerContactId), lookup.contactName(after.customerContactId))
  for (const category of BANT_CATEGORIES) {
    push('bant', `BANT Label: ${BANT_CATEGORY_NAMES[category]}`, lookup.bantLabelName(before.bant[category]), lookup.bantLabelName(after.bant[category]))
  }
  push('other', 'Deal Name', before.name, after.name)
  push('other', 'Vendor', lookup.vendorName(before.vendorId), lookup.vendorName(after.vendorId))
  push('other', 'Solution', before.solution || '-', after.solution || '-')
  push('other', 'Users count', numberText(before.users), numberText(after.users))
  push('other', '견적', quoteText(before), quoteText(after))
  push('other', 'POC', pocText(before), pocText(after))
  push('other', '구매절차', before.procurement || '-', after.procurement || '-')
  return out
}

function withNote(name: string, coChanged: boolean, other: string): string {
  return coChanged ? `${name} (${withWa(other)} 함께 변경)` : name
}

function activePartnerId(deal: Deal): number | null {
  return deal.partnerLinks.find((l) => l.active)?.contactId ?? null
}

function partnerText(deal: Deal, lookup: HistoryLookup): string {
  const id = activePartnerId(deal)
  return id === null ? '없음' : lookup.contactName(id)
}

function numberText(value: number | null): string {
  return value === null ? '-' : String(value)
}

function quoteText(deal: Deal): string {
  const { submitted, submittedDate } = deal.quote
  return `${submitted ?? '-'}${submittedDate ? ` (${submittedDate})` : ''}`
}

function pocText(deal: Deal): string {
  const { state, completedDate } = deal.poc
  return `${state ?? '-'}${completedDate ? ` (${completedDate})` : ''}`
}
