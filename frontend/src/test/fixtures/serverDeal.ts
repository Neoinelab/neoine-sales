/** HTTP 어댑터·매퍼 테스트용 서버 응답 조각(생성 타입 기준, 더미 값). */

import type { Schemas } from '../../shared/api/client'

export const CODE = '20261016-AB12'

export function serverContact(over: Partial<Schemas['ContactResponse']> = {}): Schemas['ContactResponse'] {
  return {
    id: 'c-cust',
    kind: 'customer',
    company: '한빛은행',
    name: '정민수',
    title: '과장',
    email: 'min@hanbit.test',
    phone: '010-0000-0000',
    created_at: '2026-10-01T09:00:00+09:00',
    updated_at: '2026-10-02T09:00:00+09:00',
    ...over,
  }
}

export function serverUserRef(over: Partial<Schemas['UserRef']> = {}): Schemas['UserRef'] {
  return { id: 'u-kim', name: '김영업', label: '김영업', resigned: false, role: 'sales', ...over }
}

export function serverDealRow(over: Partial<Schemas['DealRowResponse']> = {}): Schemas['DealRowResponse'] {
  return {
    code: CODE,
    name: '한빛은행 ITDR',
    owner_user_id: 'u-kim',
    owner: serverUserRef(),
    vendor: { id: 'vd-006', name: 'Silverfort' },
    solution: { id: 'sl-006', name: 'ITDR' },
    users: 100,
    status_key: 'prospecting',
    forecast_key: 'pipeline',
    revenue_amount: 500_000_000,
    revenue_date: '2027-01-31',
    customer: serverContact(),
    active_partner: null,
    partner_links: [],
    quote: { submitted: null, submitted_date: null },
    poc: { state: null, completed_date: null },
    procurement: '',
    bant: { budget: null, authority: null, need: null, timeline: null },
    next_action: null,
    last_updated_at: '2026-10-15T09:00:00+09:00',
    risk: null,
    status_changed_at: '2026-10-10T09:00:00+09:00',
    status_days: 5,
    created_at: '2026-10-01T09:00:00+09:00',
    updated_at: '2026-10-02T09:00:00+09:00',
    ...over,
  }
}

export function serverDealDetail(over: Partial<Schemas['DealDetailResponse']> = {}): Schemas['DealDetailResponse'] {
  return { ...serverDealRow(), partner_history: [], ...over }
}

export function serverHistory(over: Partial<Schemas['HistoryEntryResponse']> = {}): Schemas['HistoryEntryResponse'] {
  return {
    id: 'h1',
    deal_code: CODE,
    at: '2026-10-15T09:00:00+09:00',
    by: serverUserRef(),
    category: 'status',
    target: 'Status',
    before: 'Prospecting',
    after: 'Qualified',
    ...over,
  }
}

export function serverAlertSettings(over: Partial<Schemas['AlertSettingsResponse']> = {}): Schemas['AlertSettingsResponse'] {
  return { stale_days: 14, updated_at: null, updated_by: null, ...over }
}
