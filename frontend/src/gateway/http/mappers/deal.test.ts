import { describe, expect, it } from 'vitest'
import { CODE, serverContact, serverDealDetail, serverDealRow, serverUserRef } from '../../../test/fixtures/serverDeal'
import type { DealInput } from '../../../shared/model/types'
import { toCreateBody, toDealDetail, toDealRow, toPatchBody } from './deal'
import { USER_ID } from '../../../test/fake/seed/ids'

describe('toDealRow', () => {
  it('maps every server field to the camelCase DealRow', () => {
    const row = toDealRow(
      serverDealRow({
        partner_links: [{ contact_id: 11, active: true, linked_at: '2026-10-03T09:00:00+09:00', unlinked_at: null }],
        active_partner: serverContact({ id: 11, kind: 'partner', company: '코어테크', name: '이파트' }),
        quote: { submitted: 'YES', submitted_date: '2026-10-05' },
        poc: { state: 'ING', completed_date: null },
        bant: { budget: 1, authority: null, need: 3, timeline: null },
        next_action: { text: '견적 재송부', due_date: '2026-10-20', status: 'open' },
        procurement: '입찰',
      }),
    )

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
      bant: { budget: 1, authority: null, need: 3, timeline: null },
      nextAction: { text: '견적 재송부', dueDate: '2026-10-20', status: 'open' },
      lastUpdatedAt: '2026-10-15T09:00:00+09:00',
      risk: null,
      statusChangedAt: '2026-10-10T09:00:00+09:00',
      statusDays: 5,
      createdAt: '2026-10-01T09:00:00+09:00',
      updatedAt: '2026-10-02T09:00:00+09:00',
    })
  })

  it('AC-6 keeps the vendor null when the deal has none and the solution text as sent', () => {
    const row = toDealRow(serverDealRow({ vendor: null, solution: 'MFA' }))

    expect(row.vendor).toBeNull()
    expect(row.solution).toBe('MFA')
  })

  it('AC-6 maps the solution as a plain string', () => {
    const row = toDealRow(serverDealRow({ solution: 'ITDR' }))

    expect(row.vendor).toEqual({ id: 6, name: 'Silverfort' })
    expect(row.solution).toBe('ITDR')
  })

  it('AC-6 keeps a legacy empty solution as an empty string', () => {
    expect(toDealRow(serverDealRow({ solution: '' })).solution).toBe('')
  })

  it('keeps nextAction null when the deal has no action', () => {
    expect(toDealRow(serverDealRow({ next_action: null })).nextAction).toBeNull()
  })

  it('keeps the next-action due date exactly as the server sent it (never null any more)', () => {
    const row = toDealRow(serverDealRow({ next_action: { text: '전화', due_date: '2026-10-20', status: 'open' } }))

    expect(row.nextAction).toEqual({ text: '전화', dueDate: '2026-10-20', status: 'open' })
  })

  it('keeps a very long next-action text without cutting it', () => {
    const row = toDealRow(serverDealRow({ next_action: { text: '가'.repeat(5000), due_date: '2026-10-20', status: 'open' } }))

    expect(row.nextAction?.text).toHaveLength(5000)
  })

  it.each(['overdue', 'stale', 'overdue_stale', null] as const)('uses the server risk %s as it is', (risk) => {
    expect(toDealRow(serverDealRow({ risk })).risk).toBe(risk)
  })

  it('does not recompute risk from the UTC-looking timestamps (an old deal with server risk null stays null)', () => {
    const row = toDealRow(
      serverDealRow({
        risk: null,
        last_updated_at: '2020-01-01T00:00:00Z',
        next_action: { text: '전화', due_date: '2020-01-02', status: 'open' },
      }),
    )

    expect(row.risk).toBeNull()
  })

  it('maps the status entry time and the stay days from the server', () => {
    const row = toDealRow(serverDealRow({ status_changed_at: '2026-10-01T00:30:00+09:00', status_days: 14 }))

    expect(row).toMatchObject({ statusChangedAt: '2026-10-01T00:30:00+09:00', statusDays: 14 })
  })

  it('keeps a missing partner as null and maps users of zero as a number', () => {
    const row = toDealRow(serverDealRow({ active_partner: null, users: 0 }))

    expect(row.activePartner).toBeNull()
    expect(row.users).toBe(0)
  })

  it('maps a resigned owner with the server role', () => {
    const row = toDealRow(serverDealRow({ owner: serverUserRef({ id: USER_ID.old, resigned: true, role: 'sales' }) }))

    expect(row.owner).toMatchObject({ id: USER_ID.old, role: 'sales', status: 'resigned' })
  })
})

describe('toDealDetail', () => {
  it('adds the partner history with the contact spelled out', () => {
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

    expect(detail.partnerHistory).toEqual([
      {
        contact: expect.objectContaining({ id: 12, company: '코어테크', createdAt: '2026-10-01T09:00:00+09:00' }),
        active: false,
        linkedAt: '2026-10-03T09:00:00+09:00',
        unlinkedAt: '2026-10-10T09:00:00+09:00',
      },
    ])
  })

  it('carries the row fields too', () => {
    expect(toDealDetail(serverDealDetail())).toMatchObject({ code: CODE, partnerHistory: [], risk: null, statusDays: 5 })
  })
})

const BASE_INPUT: DealInput = {
  name: '한빛은행 ITDR',
  ownerId: USER_ID.kim,
  vendorId: null,
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

describe('bant request bodies (AC-17)', () => {
  it('create sends {id}, {name} or null for every category', () => {
    const body = toCreateBody({ ...BASE_INPUT, bant: { budget: { id: 1 }, authority: null, need: { name: '신규 요건' }, timeline: null } })

    expect(body.bant).toEqual({ budget: { id: 1 }, authority: null, need: { name: '신규 요건' }, timeline: null })
  })

  it('create sends catalog ids as JSON numbers and never a bare id string', () => {
    const body = toCreateBody({ ...BASE_INPUT, bant: { budget: { id: 1 }, authority: { name: 'x' }, need: null, timeline: null } })

    expect(Object.values(body.bant ?? {}).some((v) => typeof v === 'string')).toBe(false)
    expect(JSON.stringify(body.bant)).toBe('{"budget":{"id":1},"authority":{"name":"x"},"need":null,"timeline":null}')
  })

  it('patch carries the choice objects only when bant is part of the patch', () => {
    expect(toPatchBody({ name: '이름' })).not.toHaveProperty('bant')
    expect(toPatchBody({ bant: { budget: null, authority: { id: 2 }, need: null, timeline: { name: '내후년 구매' } } }).bant).toEqual({
      budget: null,
      authority: { id: 2 },
      need: null,
      timeline: { name: '내후년 구매' },
    })
  })
})

describe('toDealRow Next Action status (AC-15)', () => {
  it.each([
    ['open', 'open'],
    ['done', 'done'],
    ['not_done', 'notDone'],
  ] as const)('maps the basis row status %s to %s', (wire, status) => {
    const row = toDealRow(serverDealRow({ next_action: { text: '전화', due_date: '2026-10-20', status: wire } }))

    expect(row.nextAction?.status).toBe(status)
  })
})

describe('solution request bodies (AC-6, AC-9)', () => {
  it('create sends solution as given text and never solution_id', () => {
    const body = toCreateBody({ ...BASE_INPUT, solution: 'ITDR' })

    expect(body.solution).toBe('ITDR')
    expect(body).not.toHaveProperty('solution_id')
  })

  it('patch carries solution only when it is part of the patch and never solution_id', () => {
    expect(toPatchBody({ name: 'x' })).not.toHaveProperty('solution')
    expect(toPatchBody({ solution: 'MFA' })).toEqual({ solution: 'MFA' })
    expect(toPatchBody({ vendorId: 3 })).not.toHaveProperty('solution_id')
  })
})
