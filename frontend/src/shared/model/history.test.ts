import { describe, expect, it } from 'vitest'
import { diffDeal, type HistoryLookup } from './history'
import type { Deal } from './types'

const lookup: HistoryLookup = {
  statusName: (k) => ({ price_negotiation: '가격협상', contract_completed: '계약완료' })[k] ?? k,
  forecastName: (k) => ({ commit: 'Commit', won: 'Won' })[k] ?? k,
  userName: (id) => ({ 'u-kim': '김영업', 'u-park': '박영업' })[id] ?? id,
  contactName: (id) => ({ 'ct-1': '한빛은행 정민수', 'pt-1': '코어테크 민지훈', 'pt-2': '에이원시스템 표성호' })[id] ?? id,
  bantLabelName: (id) => (id === null ? '선택 안 함' : `L:${id}`),
}

function deal(over: Partial<Deal> = {}): Deal {
  return {
    code: '20260801-D001', name: 'A', ownerId: 'u-kim', vendor: 'V', solution: 'S', users: null,
    statusKey: 'price_negotiation', forecastKey: 'commit', revenueAmount: 1_000, revenueDate: '2026-12-01',
    customerContactId: 'ct-1', partnerLinks: [{ contactId: 'pt-1', active: true, linkedAt: 'x', unlinkedAt: null }],
    quote: { submitted: null, submittedDate: null }, poc: { state: null, completedDate: null }, procurement: '',
    bant: { budget: null, authority: null, need: null, timeline: null },
    createdAt: '2026-08-01T10:00:00+09:00', updatedAt: '2026-08-01T10:00:00+09:00', ...over,
  }
}

describe('diffDeal', () => {
  it('변경이 없으면 빈 배열', () => {
    expect(diffDeal(deal(), deal(), lookup)).toEqual([])
  })

  it('필드마다 1건, category/target/before/after를 채운다', () => {
    const after = deal({
      statusKey: 'contract_completed', forecastKey: 'won', revenueAmount: 2_000, revenueDate: '2026-10-20',
      ownerId: 'u-park', name: 'B', bant: { budget: 'l1', authority: null, need: null, timeline: null },
    })
    const drafts = diffDeal(deal(), after, lookup)
    const by = (c: string) => drafts.filter((d) => d.category === c)
    expect(by('status')).toEqual([{ category: 'status', target: 'Status', before: '가격협상', after: '계약완료' }])
    expect(by('forecast')[0]).toMatchObject({ before: 'Commit', after: 'Won' })
    expect(by('amount')[0]).toMatchObject({ target: '금액', before: '1,000원', after: '2,000원' })
    expect(by('expectedClose')[0]).toMatchObject({ before: '2026-12-01', after: '2026-10-20' })
    expect(by('owner')[0]).toMatchObject({ before: '김영업', after: '박영업' })
    expect(by('other')[0]).toMatchObject({ target: 'Deal Name', before: 'A', after: 'B' })
    expect(by('bant')[0]).toMatchObject({ before: '선택 안 함', after: 'L:l1' })
    expect(drafts).toHaveLength(7)
  })

  it('활성 파트너 교체는 partner 1건, 제거는 없음으로 표기한다', () => {
    const swapped = deal({
      partnerLinks: [
        { contactId: 'pt-1', active: false, linkedAt: 'x', unlinkedAt: 'y' },
        { contactId: 'pt-2', active: true, linkedAt: 'y', unlinkedAt: null },
      ],
    })
    expect(diffDeal(deal(), swapped, lookup)).toEqual([
      { category: 'partner', target: '파트너', before: '코어테크 민지훈', after: '에이원시스템 표성호' },
    ])
    const removed = deal({ partnerLinks: [{ contactId: 'pt-1', active: false, linkedAt: 'x', unlinkedAt: 'y' }] })
    expect(diffDeal(deal(), removed, lookup)[0]).toMatchObject({ category: 'partner', after: '없음' })
  })

  it('고객 연락처 변경은 contact다', () => {
    expect(diffDeal(deal(), deal({ customerContactId: 'pt-2' }), lookup)[0]).toMatchObject({ category: 'contact' })
  })

  it('함께 바뀐 값은 둘 다 기록되고 표기가 붙는다', () => {
    const after = deal({ statusKey: 'contract_completed', forecastKey: 'won' })
    const drafts = diffDeal(deal(), after, lookup, [{ field: 'forecastKey' }])
    expect(drafts.map((d) => d.category).sort()).toEqual(['forecast', 'status'])
    expect(drafts.find((d) => d.category === 'forecast')?.after).toContain('함께 변경')
    expect(drafts.find((d) => d.category === 'status')?.after).toBe('계약완료')
  })
})
