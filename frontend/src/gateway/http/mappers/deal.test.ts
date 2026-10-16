import { describe, expect, it } from 'vitest'
import { CODE, serverContact, serverDealDetail, serverDealRow, serverUserRef } from '../../../test/fixtures/serverDeal'
import { toDealDetail, toDealRow } from './deal'

describe('toDealRow', () => {
  it('maps every server field to the camelCase DealRow', () => {
    const row = toDealRow(
      serverDealRow({
        partner_links: [{ contact_id: 'c-p', active: true, linked_at: '2026-10-03T09:00:00+09:00', unlinked_at: null }],
        active_partner: serverContact({ id: 'c-p', kind: 'partner', company: '코어테크', name: '이파트' }),
        quote: { submitted: 'YES', submitted_date: '2026-10-05' },
        poc: { state: 'ING', completed_date: null },
        bant: { budget: 'b1', authority: null, need: 'n1', timeline: null },
        next_action: { text: '견적 재송부', due_date: '2026-10-20' },
        procurement: '입찰',
      }),
    )

    expect(row).toEqual({
      code: CODE,
      name: '한빛은행 ITDR',
      ownerId: 'u-kim',
      owner: { id: 'u-kim', name: '김영업', role: 'sales', status: 'active' },
      vendor: 'Silverfort',
      solution: 'ITDR',
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
      nextAction: { text: '견적 재송부', dueDate: '2026-10-20' },
      lastUpdatedAt: '2026-10-15T09:00:00+09:00',
      risk: null,
      createdAt: '2026-10-01T09:00:00+09:00',
      updatedAt: '2026-10-02T09:00:00+09:00',
    })
  })

  it('keeps nextAction null when the deal has no action', () => {
    expect(toDealRow(serverDealRow({ next_action: null })).nextAction).toBeNull()
  })

  it('keeps the next-action due date exactly as the server sent it (never null any more)', () => {
    const row = toDealRow(serverDealRow({ next_action: { text: '전화', due_date: '2026-10-20' } }))

    expect(row.nextAction).toEqual({ text: '전화', dueDate: '2026-10-20' })
  })

  it('keeps a very long next-action text without cutting it', () => {
    const row = toDealRow(serverDealRow({ next_action: { text: '가'.repeat(5000), due_date: '2026-10-20' } }))

    expect(row.nextAction?.text).toHaveLength(5000)
  })

  it('always answers risk null while the server does not compute it', () => {
    expect(toDealRow(serverDealRow({ risk: 'overdue' })).risk).toBeNull()
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
    expect(toDealDetail(serverDealDetail())).toMatchObject({ code: CODE, partnerHistory: [], risk: null })
  })
})
