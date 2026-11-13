import { describe, expect, it } from 'vitest'
import { CODE, serverContact, serverDealDetail, serverDealRow, serverUserRef } from '../../../test/fixtures/serverDeal'
import type { DealInput } from '../../../shared/model/types'
import { toCreateBody, toDealDetail, toDealRow, toPatchBody } from './deal'
import { USER_ID } from '../../../test/fake/seed/ids'

describe('toDealRow', () => {
  // 서버 Deal 목록 행의 모든 필드를 camelCase 행으로 바꾼다.
  it('maps every server field to the camelCase DealRow', () => {
    // when: 서버 행을 DealRow로 바꾼다
    const row = toDealRow(
      serverDealRow({
        partner_links: [{ contact_id: 11, active: true, linked_at: '2026-10-03T09:00:00+09:00', unlinked_at: null }],
        active_partner: serverContact({ id: 11, kind: 'partner', company: '코어테크', name: '이파트' }),
        quote: { submitted: 'YES', submitted_date: '2026-10-05' },
        poc: { state: 'ING', completed_date: null },
        bant: { budget: 1, authority: null, need: 3, timeline: null },
        next_action: { text: '견적 재송부', due_date: '2026-10-20', status: 'open' },
        procurement: '입찰',
        license_contract_count: 3,
        has_issued_license_contract: true,
      }),
    )
    // then: 모든 필드가 camelCase 이름으로 옮겨진다
    expect(row).toEqual({
      code: CODE,
      name: '한빛은행 ITDR',
      ownerId: USER_ID.kim,
      owner: { id: USER_ID.kim, name: '김영업', role: 'sales', status: 'active' },
      vendor: { id: 6, name: 'Silverfort' },
      solution: 'ITDR',
      users: 100,
      statusKey: 'prospecting',
      forecastKey: 'pipeline',
      revenueAmount: 500_000_000,
      revenueDate: '2027-01-31',
      customerContactId: 10,
      customer: {
        id: 10,
        kind: 'customer',
        company: '한빛은행',
        name: '정민수',
        title: '과장',
        email: 'min@hanbit.test',
        phone: '010-0000-0000',
        createdAt: '2026-10-01T09:00:00+09:00',
        updatedAt: '2026-10-02T09:00:00+09:00',
      },
      activePartner: expect.objectContaining({ id: 11, kind: 'partner', company: '코어테크' }),
      partnerLinks: [{ contactId: 11, active: true, linkedAt: '2026-10-03T09:00:00+09:00', unlinkedAt: null }],
      quote: { submitted: 'YES', submittedDate: '2026-10-05' },
      poc: { state: 'ING', completedDate: null },
      procurement: '입찰',
      licenseContractCount: 3,
      hasIssuedLicenseContract: true,
      bant: { budget: 1, authority: null, need: 3, timeline: null },
      nextAction: { text: '견적 재송부', dueDate: '2026-10-20', status: 'open' },
      lastUpdatedOn: '2026-10-15',
      risk: null,
      statusChangedOn: '2026-10-10',
      statusDays: 5,
      createdAt: '2026-10-01T09:00:00+09:00',
      updatedAt: '2026-10-02T09:00:00+09:00',
    })
  })

  // Vendor가 없는 Deal은 Vendor를 null로 두고 Solution 텍스트를 그대로 옮긴다.
  it('keeps the vendor null when the deal has none and the solution text as sent', () => {
    // when: Vendor 없는 서버 행을 바꾼다
    const row = toDealRow(serverDealRow({ vendor: null, solution: 'MFA' }))
    // then: vendor는 null이고 solution은 보낸 그대로다
    expect(row.vendor).toBeNull()
    expect(row.solution).toBe('MFA')
  })

  // Solution을 일반 문자열로 옮긴다.
  it('maps the solution as a plain string', () => {
    // when: Solution이 있는 서버 행을 바꾼다
    const row = toDealRow(serverDealRow({ solution: 'ITDR' }))
    // then: vendor는 {id, name}이고 solution은 문자열이다
    expect(row.vendor).toEqual({ id: 6, name: 'Silverfort' })
    expect(row.solution).toBe('ITDR')
  })

  // 예전 빈 Solution은 빈 문자열로 둔다.
  it('keeps a legacy empty solution as an empty string', () => {
    // when: 빈 Solution의 서버 행을 바꾼다
    const result = toDealRow(serverDealRow({ solution: '' })).solution
    // then: solution이 빈 문자열이다
    expect(result).toBe('')
  })

  // Action이 없으면 nextAction은 null이다.
  it('keeps nextAction null when the deal has no action', () => {
    // when: Next Action 없는 서버 행을 바꾼다
    const result = toDealRow(serverDealRow({ next_action: null })).nextAction
    // then: nextAction이 null이다
    expect(result).toBeNull()
  })

  // Next Action 기한은 서버가 준 날짜 그대로 둔다.
  it('keeps the next-action due date exactly as the server sent it (never null any more)', () => {
    // when: Next Action이 있는 서버 행을 바꾼다
    const row = toDealRow(serverDealRow({ next_action: { text: '전화', due_date: '2026-10-20', status: 'open' } }))
    // then: text·dueDate·status가 서버 값 그대로다
    expect(row.nextAction).toEqual({ text: '전화', dueDate: '2026-10-20', status: 'open' })
  })

  // 긴 Next Action 문구는 자르지 않는다.
  it('keeps a very long next-action text without cutting it', () => {
    // when: 서버 행을 바꾼다
    const row = toDealRow(serverDealRow({ next_action: { text: '가'.repeat(5000), due_date: '2026-10-20', status: 'open' } }))
    // then: 문구 길이가 5000자 그대로다
    expect(row.nextAction?.text).toHaveLength(5000)
  })

  // 서버가 준 risk를 그대로 옮긴다.
  // 테스트 코드: RK-059
  it.each(['overdue', 'stale', 'overdue_stale', null] as const)('uses the server risk %s as it is', (risk) => {
    // when: 서버 risk가 overdue·stale·overdue_stale·null인 행을 바꾼다
    const result = toDealRow(serverDealRow({ risk })).risk
    // then: 화면 모델의 risk가 서버 값과 같다
    expect(result).toBe(risk)
  })

  // 오래돼 보이는 시각이어도 경고를 다시 계산하지 않는다.
  // 테스트 코드: RK-059
  it('does not recompute risk from the UTC-looking timestamps (an old deal with server risk null stays null)', () => {
    // when: risk가 null이고 갱신 시각이 2020년인 서버 행을 바꾼다
    const row = toDealRow(
      serverDealRow({
        risk: null,
        last_updated_on: '2020-01-01',
        next_action: { text: '전화', due_date: '2020-01-02', status: 'open' },
      }),
    )

    // then: risk는 null 그대로다
    expect(row.risk).toBeNull()
  })

  // 진입 시각과 체류 일수를 서버 값 그대로 옮긴다.
  // 테스트 코드: RK-059
  it('maps the status entry time and the stay days from the server', () => {
    // when: status_changed_on과 status_days가 있는 서버 행을 바꾼다
    const row = toDealRow(serverDealRow({ status_changed_on: '2026-10-01', status_days: 14 }))

    // then: statusChangedOn·statusDays가 서버 값이다
    expect(row).toMatchObject({ statusChangedOn: '2026-10-01', statusDays: 14 })
  })

  // 활성 파트너가 없으면 null, Users 0은 숫자로 옮긴다.
  it('keeps a missing partner as null and maps users of zero as a number', () => {
    // when: 파트너 없고 users 0인 서버 행을 바꾼다
    const row = toDealRow(serverDealRow({ active_partner: null, users: 0 }))
    // then: activePartner는 null이고 users는 0이다
    expect(row.activePartner).toBeNull()
    expect(row.users).toBe(0)
  })

  // 퇴사한 Owner는 서버 역할과 함께 resigned 상태로 옮긴다.
  it('maps a resigned owner with the server role', () => {
    // when: 퇴사 Owner의 서버 행을 바꾼다
    const row = toDealRow(serverDealRow({ owner: serverUserRef({ id: USER_ID.old, resigned: true, role: 'sales' }) }))
    // then: owner에 id·role·status resigned가 담긴다
    expect(row.owner).toMatchObject({ id: USER_ID.old, role: 'sales', status: 'resigned' })
  })
})

describe('toDealDetail', () => {
  // 파트너 이력에는 연락처를 풀어서 담는다.
  it('adds the partner history with the contact spelled out', () => {
    // when: 파트너 이력이 있는 서버 상세를 바꾼다
    const detail = toDealDetail(
      serverDealDetail({
        partner_history: [
          {
            contact: serverContact({ id: 12, kind: 'partner', company: '코어테크', name: '이파트' }),
            active: false,
            linked_at: '2026-10-03T09:00:00+09:00',
            unlinked_at: '2026-10-10T09:00:00+09:00',
          },
        ],
      }),
    )
    // then: partnerHistory에 연락처 전체와 연결·해제 시각이 담긴다
    expect(detail.partnerHistory).toEqual([
      {
        contact: expect.objectContaining({ id: 12, company: '코어테크', createdAt: '2026-10-01T09:00:00+09:00' }),
        active: false,
        linkedAt: '2026-10-03T09:00:00+09:00',
        unlinkedAt: '2026-10-10T09:00:00+09:00',
      },
    ])
  })

  // has_issued_license_contract를 행과 상세 모두에서 옮긴다.
  it('maps hasIssuedLicenseContract from has_issued_license_contract on rows and details', () => {
    // when: 발급 계약 여부가 true·false인 서버 행과 상세를 바꾼다
    const r1 = toDealRow(serverDealRow({ has_issued_license_contract: true })).hasIssuedLicenseContract
    const r2 = toDealRow(serverDealRow({ has_issued_license_contract: false })).hasIssuedLicenseContract
    const r3 = toDealDetail(serverDealDetail({ has_issued_license_contract: true })).hasIssuedLicenseContract
    // then: hasIssuedLicenseContract가 같은 값이다
    expect(r1).toBe(true)
    expect(r2).toBe(false)
    expect(r3).toBe(true)
  })

  // 상세에도 행 필드가 들어 있다.
  it('carries the row fields too', () => {
    // when: 서버 상세를 바꾼다
    const result = toDealDetail(serverDealDetail())
    // then: 행 필드와 partnerHistory 빈 배열이 담긴다
    expect(result).toMatchObject({ code: CODE, partnerHistory: [], risk: null, statusDays: 5 })
  })
})

const BASE_INPUT: DealInput = {
  name: '한빛은행 ITDR',
  ownerId: USER_ID.kim,
  vendorId: 6,
  solution: 'ITDR',
  users: 10,
  statusKey: 'prospecting',
  forecastKey: 'pipeline',
  revenueAmount: 1,
  revenueDate: '2027-01-31',
  customer: { contactId: null, company: '한빛은행', name: '정민수', title: '', email: null, phone: null },
  partner: null,
  quote: { submitted: null, submittedDate: null },
  poc: { state: null, completedDate: null },
  procurement: '',
  bant: { budget: null, authority: null, need: null, timeline: null },
}

describe('bant request bodies', () => {
  // 등록 본문은 BANT 구분마다 {id}·{name}·null을 보낸다.
  // 테스트 코드: DE-111
  it('create sends {id}, {name} or null for every category', () => {
    // when: 등록 본문으로 변환한다 (전제: 구분마다 id·이름·없음이 든 입력이다)
    const body = toCreateBody({ ...BASE_INPUT, bant: { budget: { id: 1 }, authority: null, need: { name: '신규 요건' }, timeline: null } })

    // then: bant가 선택 객체 또는 null이다.
    expect(body.bant).toEqual({ budget: { id: 1 }, authority: null, need: { name: '신규 요건' }, timeline: null })
  })

  // 카탈로그 id는 JSON 숫자로 보내고 문자열 id를 보내지 않는다.
  // 테스트 코드: DE-111
  it('create sends catalog ids as JSON numbers and never a bare id string', () => {
    // when: 등록 본문으로 변환한다 (전제: BANT id가 든 입력이다)
    const body = toCreateBody({ ...BASE_INPUT, bant: { budget: { id: 1 }, authority: { name: 'x' }, need: null, timeline: null } })

    // then: id가 number다.
    expect(Object.values(body.bant ?? {}).some((v) => typeof v === 'string')).toBe(false)
    expect(JSON.stringify(body.bant)).toBe('{"budget":{"id":1},"authority":{"name":"x"},"need":null,"timeline":null}')
  })

  // patch는 bant를 보낼 때만 선택 객체를 싣는다.
  // 테스트 코드: DE-112
  it('patch carries the choice objects only when bant is part of the patch', () => {
    // when: 수정 본문으로 변환한다 (전제: bant가 있는 patch와 없는 patch다)
    const result1 = toPatchBody({ name: '이름' })
    const result2 = toPatchBody({ bant: { budget: null, authority: { id: 2 }, need: null, timeline: { name: '내후년 구매' } } }).bant
    // then: bant가 있을 때만 선택 객체가 있다.
    expect(result1).not.toHaveProperty('bant')
    expect(result2).toEqual({
      budget: null,
      authority: { id: 2 },
      need: null,
      timeline: { name: '내후년 구매' },
    })
  })
})

describe('toDealRow Next Action status', () => {
  // 기준 행의 Next Action 상태를 화면 모델 이름으로 옮긴다.
  it.each([
    ['open', 'open'],
    ['done', 'done'],
    ['not_done', 'notDone'],
  ] as const)('maps the basis row status %s to %s', (wire, status) => {
    // when: 해당 상태의 Next Action이 든 서버 행을 바꾼다
    const row = toDealRow(serverDealRow({ next_action: { text: '전화', due_date: '2026-10-20', status: wire } }))

    // then: 화면 모델의 상태 이름으로 바뀐다
    expect(row.nextAction?.status).toBe(status)
  })
})

describe('solution request bodies', () => {
  // 등록 본문은 Solution 텍스트를 그대로 보내고 solution_id는 보내지 않는다.
  // 테스트 코드: DE-111
  it('create sends solution as given text and never solution_id', () => {
    // when: 등록 본문으로 변환한다 (전제: Solution이 든 입력이다)
    const body = toCreateBody({ ...BASE_INPUT, solution: 'ITDR' })

    // then: solution이 있고 solution_id는 없다.
    expect(body.solution).toBe('ITDR')
    expect(body).not.toHaveProperty('solution_id')
  })

  // 등록 본문은 Vendor id를 숫자로, 빈 Solution을 빈 문자열로 보낸다.
  // 테스트 코드: DE-111
  it('create sends the vendor id as a number and an empty solution as an empty string', () => {
    // when: 빈 Solution의 등록 입력을 본문으로 변환한다
    const body = toCreateBody({ ...BASE_INPUT, vendorId: 6, solution: '' })

    // then: vendor_id는 6, solution은 ''다
    expect(body.vendor_id).toBe(6)
    expect(body.solution).toBe('')
  })

  // patch는 Solution을 보낼 때만 싣고 solution_id는 보내지 않는다.
  // 테스트 코드: DE-112
  it('patch carries solution only when it is part of the patch and never solution_id', () => {
    // when: 수정 본문으로 변환한다 (전제: Solution이 있는 patch와 없는 patch다)
    const result1 = toPatchBody({ name: 'x' })
    const result2 = toPatchBody({ solution: 'MFA' })
    const result3 = toPatchBody({ vendorId: 3 })
    // then: 있을 때만 solution이 있다.
    expect(result1).not.toHaveProperty('solution')
    expect(result2).toEqual({ solution: 'MFA' })
    expect(result3).not.toHaveProperty('solution_id')
  })
})
