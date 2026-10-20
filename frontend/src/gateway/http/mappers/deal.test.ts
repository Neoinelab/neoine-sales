import { describe, expect, it } from 'vitest'
import { CODE, serverContact, serverDealDetail, serverDealRow, serverUserRef } from '../../../test/fixtures/serverDeal'
import type { DealInput } from '../../../shared/model/types'
import { toCreateBody, toDealDetail, toDealRow, toPatchBody } from './deal'

describe('toDealRow', () => {
  it('maps every server field to the camelCase DealRow', () => {
    const row = toDealRow(
      serverDealRow({
        partner_links: [{ contact_id: 'c-p', active: true, linked_at: '2026-10-03T09:00:00+09:00', unlinked_at: null }],
        active_partner: serverContact({ id: 'c-p', kind: 'partner', company: '코어테크', name: '이파트' }),
        quote: { submitted: 'YES', submitted_date: '2026-10-05' },
        poc: { state: 'ING', completed_date: null },
        bant: { budget: 'b1', authority: null, need: 'n1', timeline: null },
        next_action: { text: '견적 재송부', due_date: '2026-10-20', status: 'open' },
        procurement: '입찰',
      }),
    )

    expect(row).toEqual({
      code: CODE,
      name: '한빛은행 ITDR',
      ownerId: 'u-kim',
      owner: { id: 'u-kim', name: '김영업', role: 'sales', status: 'active' },
      vendor: { id: 'vd-006', name: 'Silverfort' },
      solution: { id: 'sl-006', name: 'ITDR' },
      users: 100,
      statusKey: 'prospecting',
      forecastKey: 'pipeline',
      revenueAmount: 500_000_000,
      revenueDate: '2027-01-31',
      customerContactId: 'c-cust',
      customer: {
        id: 'c-cust',
        kind: 'customer',
        company: '한빛은행',
        name: '정민수',
        title: '과장',
        email: 'min@hanbit.test',
        phone: '010-0000-0000',
        createdAt: '2026-10-01T09:00:00+09:00',
        updatedAt: '2026-10-02T09:00:00+09:00',
      },
      activePartner: expect.objectContaining({ id: 'c-p', kind: 'partner', company: '코어테크' }),
      partnerLinks: [{ contactId: 'c-p', active: true, linkedAt: '2026-10-03T09:00:00+09:00', unlinkedAt: null }],
      quote: { submitted: 'YES', submittedDate: '2026-10-05' },
      poc: { state: 'ING', completedDate: null },
      procurement: '입찰',
      bant: { budget: 'b1', authority: null, need: 'n1', timeline: null },
      nextAction: { text: '견적 재송부', dueDate: '2026-10-20', status: 'open' },
      lastUpdatedAt: '2026-10-15T09:00:00+09:00',
      risk: null,
      statusChangedAt: '2026-10-10T09:00:00+09:00',
      statusDays: 5,
      createdAt: '2026-10-01T09:00:00+09:00',
      updatedAt: '2026-10-02T09:00:00+09:00',
    })
  })

  it('AC-13 keeps vendor and solution null when the deal has none', () => {
    const row = toDealRow(serverDealRow({ vendor: null, solution: null }))

    expect(row.vendor).toBeNull()
    expect(row.solution).toBeNull()
  })

  it('AC-13 keeps a vendor without a solution', () => {
    const row = toDealRow(serverDealRow({ solution: null }))

    expect(row.vendor).toEqual({ id: 'vd-006', name: 'Silverfort' })
    expect(row.solution).toBeNull()
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

  it('keeps a missing partner and an empty users as null', () => {
    const row = toDealRow(serverDealRow({ active_partner: null, users: null }))

    expect(row.activePartner).toBeNull()
    expect(row.users).toBeNull()
  })

  it('maps a resigned owner with the server role', () => {
    const row = toDealRow(serverDealRow({ owner: serverUserRef({ id: 'u-old', resigned: true, role: 'sales' }) }))

    expect(row.owner).toMatchObject({ id: 'u-old', role: 'sales', status: 'resigned' })
  })
})

describe('toDealDetail', () => {
  it('adds the partner history with the contact spelled out', () => {
    const detail = toDealDetail(
      serverDealDetail({
        partner_history: [
          {
            contact: serverContact({ id: 'c-p1', kind: 'partner', company: '코어테크', name: '이파트' }),
            active: false,
            linked_at: '2026-10-03T09:00:00+09:00',
            unlinked_at: '2026-10-10T09:00:00+09:00',
          },
        ],
      }),
    )

    expect(detail.partnerHistory).toEqual([
      {
        contact: expect.objectContaining({ id: 'c-p1', company: '코어테크', createdAt: '2026-10-01T09:00:00+09:00' }),
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
  ownerId: 'u-kim',
  vendorId: null,
  solutionId: null,
  users: null,
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
    const body = toCreateBody({ ...BASE_INPUT, bant: { budget: { id: 'b1' }, authority: null, need: { name: '신규 요건' }, timeline: null } })

    expect(body.bant).toEqual({ budget: { id: 'b1' }, authority: null, need: { name: '신규 요건' }, timeline: null })
  })

  it('create never sends a bare uuid string for a category', () => {
    const body = toCreateBody({ ...BASE_INPUT, bant: { budget: { id: 'b1' }, authority: { name: 'x' }, need: null, timeline: null } })

    expect(Object.values(body.bant ?? {}).some((v) => typeof v === 'string')).toBe(false)
  })

  it('patch carries the choice objects only when bant is part of the patch', () => {
    expect(toPatchBody({ name: '이름' })).not.toHaveProperty('bant')
    expect(toPatchBody({ bant: { budget: null, authority: { id: 'a1' }, need: null, timeline: { name: '내후년 구매' } } }).bant).toEqual({
      budget: null,
      authority: { id: 'a1' },
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
