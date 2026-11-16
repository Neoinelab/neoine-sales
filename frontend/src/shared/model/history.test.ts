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
  bantLabelName: (id) => (id === null ? '선택 안 함' : `L:${id}`),
}

function deal(over: Partial<Deal> = {}): Deal {
  return {
    code: '20260801-D001', name: 'A', ownerId: USER_ID.kim, vendorId: 1, product: 'S/4', users: 10,
    statusKey: 'price_negotiation', forecastKey: 'commit', revenueAmount: 1_000, revenueDate: '2026-12-01',
    customerContactId: 1, partnerLinks: [{ contactId: 11, active: true, linkedAt: 'x', unlinkedAt: null }],
    quote: { submitted: null, submittedDate: null }, poc: { state: null, completedDate: null }, procurement: '',
    bant: { budget: null, authority: null, need: null, timeline: null },
    createdAt: '2026-08-01T10:00:00+09:00', updatedAt: '2026-08-01T10:00:00+09:00',
    statusChangedOn: '2026-08-01', ...over,
  }
}

describe('diffDeal', () => {
  // 변경이 없으면 이력 항목이 없다.
  // 테스트 코드: DD-115
  it('변경이 없으면 빈 배열', () => {
    // when: 이력 차이를 계산한다 (전제: 같은 Deal 둘)
    const result = diffDeal(deal(), deal(), lookup)
    // then: 빈 목록이다
    expect(result).toEqual([])
  })

  // 바뀐 필드마다 구분·대상·전·후를 채운 이력 한 건이 나온다.
  // 테스트 코드: DD-115
  it('필드마다 1건, category/target/before/after를 채운다', () => {
    // given: 일곱 필드가 바뀐 Deal
    const after = deal({
      statusKey: 'contract_completed', forecastKey: 'won', revenueAmount: 2_000, revenueDate: '2026-10-20',
      ownerId: USER_ID.park, name: 'B', bant: { budget: 1, authority: null, need: null, timeline: null },
    })
    const drafts = diffDeal(deal(), after, lookup)
    // when: 이력 차이를 계산한다
    const by = (c: string) => drafts.filter((d) => d.category === c)
    // then: Status·Forecast·금액·Expected Close·Owner·기타·BANT 일곱 건이다
    expect(by('status')).toEqual([{ category: 'status', target: 'Status', before: '가격협상', after: '계약완료' }])
    expect(by('forecast')[0]).toMatchObject({ before: 'Commit', after: 'Won' })
    expect(by('amount')[0]).toMatchObject({ target: '금액(단위:원)', before: '1,000', after: '2,000' })
    expect(by('expectedClose')[0]).toMatchObject({ before: '2026-12-01', after: '2026-10-20' })
    expect(by('owner')[0]).toMatchObject({ before: '김영업', after: '박영업' })
    expect(by('other')[0]).toMatchObject({ target: 'Deal Name', before: 'A', after: 'B' })
    expect(by('bant')[0]).toMatchObject({ before: '선택 안 함', after: 'L:1' })
    expect(drafts).toHaveLength(7)
  })

  // 금액 이력은 반올림 없이 원 콤마 숫자다.
  // 테스트 코드: DD-115
  it('금액은 반올림 없이 원 콤마 숫자로 기록한다', () => {
    // when: 이력 차이를 계산한다 (전제: 금액이 바뀐 Deal)
    const drafts = diffDeal(deal({ revenueAmount: 150_000_000 }), deal({ revenueAmount: 1_870_000_000 }), lookup)
    // then: '금액(단위:원)' 전후가 콤마 숫자 그대로다
    expect(drafts).toEqual([{ category: 'amount', target: '금액(단위:원)', before: '150,000,000', after: '1,870,000,000' }])
    expect(diffDeal(deal({ revenueAmount: 1_000 }), deal({ revenueAmount: 1_400 }), lookup)).toEqual([
      { category: 'amount', target: '금액(단위:원)', before: '1,000', after: '1,400' },
    ])
  })

  // 파트너 교체는 한 건, 제거는 변경 후 '없음'이다.
  // 테스트 코드: DD-115
  it('활성 파트너 교체는 partner 1건, 제거는 없음으로 표기한다', () => {
    // given: 파트너가 교체·제거된 Deal
    const swapped = deal({
      partnerLinks: [
        { contactId: 11, active: false, linkedAt: 'x', unlinkedAt: 'y' },
        { contactId: 12, active: true, linkedAt: 'y', unlinkedAt: null },
      ],
    })
    const removed = deal({ partnerLinks: [{ contactId: 11, active: false, linkedAt: 'x', unlinkedAt: 'y' }] })
    // when: 교체·제거된 Deal과 이력 차이를 계산한다
    const swappedDrafts = diffDeal(deal(), swapped, lookup)
    const removedDrafts = diffDeal(deal(), removed, lookup)
    // then: partner 한 건이고 제거는 '없음'이다
    expect(swappedDrafts).toEqual([
      { category: 'partner', target: '파트너', before: '코어테크 민지훈', after: '에이원시스템 표성호' },
    ])
    expect(removedDrafts[0]).toMatchObject({ category: 'partner', after: '없음' })
  })

  // 고객 연락처 변경은 contact 구분이다.
  // 테스트 코드: DD-115
  it('고객 연락처 변경은 contact다', () => {
    // when: 이력 차이를 계산한다 (전제: 고객 연락처가 바뀐 Deal)
    const result = diffDeal(deal(), deal({ customerContactId: 12 }), lookup)[0]
    // then: 구분이 contact다
    expect(result).toMatchObject({ category: 'contact' })
  })

  // 함께 바뀐 값은 둘 다 기록되고 Forecast에 '함께 변경' 표기가 붙는다.
  // 테스트 코드: DD-115
  it('함께 바뀐 값은 둘 다 기록되고 표기가 붙는다', () => {
    // given: Status·Forecast가 함께 바뀐 Deal과 함께 바뀐 값 정보
    const after = deal({ statusKey: 'contract_completed', forecastKey: 'won' })
    // when: 이력 차이를 계산한다
    const drafts = diffDeal(deal(), after, lookup, [{ field: 'forecastKey' }])
    // then: status·forecast 두 건이고 함께 바뀐 쪽에 표기가 있다
    expect(drafts.map((d) => d.category).sort()).toEqual(['forecast', 'status'])
    expect(drafts.find((d) => d.category === 'forecast')?.after).toContain('함께 변경')
    expect(drafts.find((d) => d.category === 'status')?.after).toBe('계약완료')
  })

  // Vendor·Product 변경은 기타 한 건씩이고 Product는 텍스트이며 순서가 정해져 있다.
  // 테스트 코드: DD-115
  it('Vendor와 Product 변경은 기타 1건씩 남고 Product는 텍스트이며 순서는 Deal Name, Vendor, Product, Users count이다', () => {
    // given: 이름·Vendor·Product·Users가 바뀐 Deal
    const after = deal({ name: 'B', vendorId: 2, product: 'SSO', users: 5 })

    // when: 이력 차이를 계산한다
    const others = diffDeal(deal(), after, lookup).filter((d) => d.category === 'other')

    // then: Deal Name, Vendor, Product, Users count 순서의 기타 이력이다
    expect(others).toEqual([
      { category: 'other', target: 'Deal Name', before: 'A', after: 'B' },
      { category: 'other', target: 'Vendor', before: 'SAP', after: 'Okta' },
      { category: 'other', target: 'Product', before: 'S/4', after: 'SSO' },
      { category: 'other', target: 'Users count', before: '10', after: '5' },
    ])
  })

  // 빈 Product(레거시)은 변경 전이 '-'로 기록된다.
  // 테스트 코드: DD-115
  it('records product text with dash for empty (legacy empty values only)', () => {
    // when: ITDR로 바꿔 이력 차이를 계산한다 (전제: Product가 빈 Deal)
    const result = diffDeal(deal({ product: '' }), deal({ product: 'ITDR' }), lookup)
    // then: 변경 전이 '-'다
    expect(result).toEqual([
      { category: 'other', target: 'Product', before: '-', after: 'ITDR' },
    ])
  })

  // 대소문자만 바뀐 Product도 기록하고 같은 값이면 기록하지 않는다.
  // 테스트 코드: DD-115
  it('대소문자만 바뀐 Product도 남기고 같은 값이면 남기지 않는다', () => {
    // when: 이력 차이를 계산한다 (전제: Product만 다른 Deal 쌍)
    const result1 = diffDeal(deal({ product: 'itdr' }), deal({ product: 'ITDR' }), lookup)
    const result2 = diffDeal(deal({ product: 'ITDR' }), deal({ product: 'ITDR' }), lookup)
    // then: 대소문자 차이는 한 건, 같은 값은 없다
    expect(result1).toEqual([
      { category: 'other', target: 'Product', before: 'itdr', after: 'ITDR' },
    ])
    expect(result2).toEqual([])
  })

  // Vendor만 바뀌면 Vendor 한 건뿐이고 Product 이력은 없다.
  // 테스트 코드: DD-115
  it('Vendor만 바뀌면 Vendor 1건만 남고 Product 항목은 없다', () => {
    // when: 이력 차이를 계산한다 (전제: Vendor만 바뀐 Deal)
    const drafts = diffDeal(deal(), deal({ vendorId: 2 }), lookup)

    // then: Vendor 한 건뿐이다
    expect(drafts).toEqual([{ category: 'other', target: 'Vendor', before: 'SAP', after: 'Okta' }])
  })

  // Vendor를 비우면 '선택 안 함'으로 기록하고 Product는 남기지 않는다.
  // 테스트 코드: DD-115
  it('Vendor를 비우면 선택 안 함으로 표기하고 Product는 그대로라 남기지 않는다', () => {
    // when: 이력 차이를 계산한다 (전제: Vendor를 비운 Deal)
    const cleared = diffDeal(deal(), deal({ vendorId: null }), lookup)

    // then: Vendor 변경 후가 '선택 안 함'이고 같은 상태끼리는 이력이 없다
    expect(cleared).toEqual([{ category: 'other', target: 'Vendor', before: 'SAP', after: '선택 안 함' }])
    expect(diffDeal(deal({ vendorId: null }), deal({ vendorId: null }), lookup)).toEqual([])
  })

  // 이력 조회 도우미에는 더 이상 solutionName이 없다.
  it('HistoryLookup has no solutionName any more', () => {
    // when: 키를 확인한다 (전제: 이력 조회 도우미)
    const result = Object.keys(lookup)
    // then: solutionName이 없다
    expect(result).not.toContain('solutionName')
  })
})
