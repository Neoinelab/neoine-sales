import { describe, expect, it } from 'vitest'
import { diffDeal, type HistoryLookup } from './history'
import type { Deal } from './types'
import { USER_ID } from '../../test/fake/seed/ids'

const lookup: HistoryLookup = {
  statusName: (k) => ({ price_negotiation: '가격협상', contract_completed: '계약완료' })[k] ?? k,
  forecastName: (k) => ({ commit: 'Commit', won: 'Won' })[k] ?? k,
  userName: (id) => ({ [USER_ID.kim]: '김영업', [USER_ID.park]: '박영업' })[id] ?? String(id),
  contactName: (id) => ({ 1: '한빛은행 정민수', 11: '코어테크 민지훈', 12: '에이원시스템 표성호' })[id] ?? String(id),
  vendorName: (id) => (id === null ? '선택 안 함' : ({ 1: 'SAP', 2: 'Okta' })[id] ?? String(id)),
  solutionName: (id) => (id === null ? '선택 안 함' : ({ 1: 'S/4', 2: 'SSO' })[id] ?? String(id)),
  bantLabelName: (id) => (id === null ? '선택 안 함' : `L:${id}`),
}

function deal(over: Partial<Deal> = {}): Deal {
  return {
    code: '20260801-D001', name: 'A', ownerId: USER_ID.kim, vendorId: 1, solutionId: 1, users: 10,
    statusKey: 'price_negotiation', forecastKey: 'commit', revenueAmount: 1_000, revenueDate: '2026-12-01',
    customerContactId: 1, partnerLinks: [{ contactId: 11, active: true, linkedAt: 'x', unlinkedAt: null }],
    quote: { submitted: null, submittedDate: null }, poc: { state: null, completedDate: null }, procurement: '',
    bant: { budget: null, authority: null, need: null, timeline: null },
    createdAt: '2026-08-01T10:00:00+09:00', updatedAt: '2026-08-01T10:00:00+09:00',
    statusChangedAt: '2026-08-01T10:00:00+09:00', ...over,
  }
}

describe('diffDeal', () => {
  it('변경이 없으면 빈 배열', () => {
    expect(diffDeal(deal(), deal(), lookup)).toEqual([])
  })

  it('필드마다 1건, category/target/before/after를 채운다', () => {
    const after = deal({
      statusKey: 'contract_completed', forecastKey: 'won', revenueAmount: 2_000, revenueDate: '2026-10-20',
      ownerId: USER_ID.park, name: 'B', bant: { budget: 1, authority: null, need: null, timeline: null },
    })
    const drafts = diffDeal(deal(), after, lookup)
    const by = (c: string) => drafts.filter((d) => d.category === c)
    expect(by('status')).toEqual([{ category: 'status', target: 'Status', before: '가격협상', after: '계약완료' }])
    expect(by('forecast')[0]).toMatchObject({ before: 'Commit', after: 'Won' })
    expect(by('amount')[0]).toMatchObject({ target: '금액(단위:천원)', before: '1', after: '2' })
    expect(by('expectedClose')[0]).toMatchObject({ before: '2026-12-01', after: '2026-10-20' })
    expect(by('owner')[0]).toMatchObject({ before: '김영업', after: '박영업' })
    expect(by('other')[0]).toMatchObject({ target: 'Deal Name', before: 'A', after: 'B' })
    expect(by('bant')[0]).toMatchObject({ before: '선택 안 함', after: 'L:1' })
    expect(drafts).toHaveLength(7)
  })

  it('활성 파트너 교체는 partner 1건, 제거는 없음으로 표기한다', () => {
    const swapped = deal({
      partnerLinks: [
        { contactId: 11, active: false, linkedAt: 'x', unlinkedAt: 'y' },
        { contactId: 12, active: true, linkedAt: 'y', unlinkedAt: null },
      ],
    })
    expect(diffDeal(deal(), swapped, lookup)).toEqual([
      { category: 'partner', target: '파트너', before: '코어테크 민지훈', after: '에이원시스템 표성호' },
    ])
    const removed = deal({ partnerLinks: [{ contactId: 11, active: false, linkedAt: 'x', unlinkedAt: 'y' }] })
    expect(diffDeal(deal(), removed, lookup)[0]).toMatchObject({ category: 'partner', after: '없음' })
  })

  it('고객 연락처 변경은 contact다', () => {
    expect(diffDeal(deal(), deal({ customerContactId: 12 }), lookup)[0]).toMatchObject({ category: 'contact' })
  })

  it('함께 바뀐 값은 둘 다 기록되고 표기가 붙는다', () => {
    const after = deal({ statusKey: 'contract_completed', forecastKey: 'won' })
    const drafts = diffDeal(deal(), after, lookup, [{ field: 'forecastKey' }])
    expect(drafts.map((d) => d.category).sort()).toEqual(['forecast', 'status'])
    expect(drafts.find((d) => d.category === 'forecast')?.after).toContain('함께 변경')
    expect(drafts.find((d) => d.category === 'status')?.after).toBe('계약완료')
  })

  it('AC-14 Vendor와 Solution 변경은 이름으로 기타 1건씩 남고 순서는 Deal Name, Vendor, Solution, Users이다', () => {
    const after = deal({ name: 'B', vendorId: 2, solutionId: 2, users: 5 })

    const others = diffDeal(deal(), after, lookup).filter((d) => d.category === 'other')

    expect(others).toEqual([
      { category: 'other', target: 'Deal Name', before: 'A', after: 'B' },
      { category: 'other', target: 'Vendor', before: 'SAP', after: 'Okta' },
      { category: 'other', target: 'Solution', before: 'S/4', after: 'SSO' },
      { category: 'other', target: 'Users', before: '10', after: '5' },
    ])
  })

  it('AC-14 선택 없음은 선택 안 함으로 표기하고 바뀌지 않으면 남기지 않는다', () => {
    const cleared = diffDeal(deal(), deal({ vendorId: null, solutionId: null }), lookup)

    expect(cleared).toEqual([
      { category: 'other', target: 'Vendor', before: 'SAP', after: '선택 안 함' },
      { category: 'other', target: 'Solution', before: 'S/4', after: '선택 안 함' },
    ])
    expect(diffDeal(deal({ vendorId: null, solutionId: null }), deal({ vendorId: null, solutionId: null }), lookup)).toEqual([])
  })
})
