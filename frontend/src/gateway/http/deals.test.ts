import { afterEach, describe, expect, it, vi } from 'vitest'
import { CODE, serverDealDetail, serverDealRow } from '../../test/fixtures/serverDeal'
import type { DealInput, DealSortKey } from '../../shared/model/types'
import { createDealsHttp } from './deals'
import { createHttpGateway } from './index'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const page = (items: unknown[], total = items.length) => ({ items, total, offset: 0, limit: 20 })
const query = (path: string) => new URL(path, 'http://localhost').searchParams

const input = (over: Partial<DealInput> = {}): DealInput => ({
  name: '한빛은행 ITDR',
  ownerId: 'u-kim',
  vendorId: 'vd-006',
  solutionId: 'sl-006',
  users: 100,
  statusKey: 'prospecting',
  forecastKey: 'pipeline',
  revenueAmount: 500_000_000,
  revenueDate: '2027-01-31',
  customer: { contactId: null, company: '한빛은행', name: '정민수', title: '과장', email: 'min@hanbit.test', phone: null },
  partner: null,
  quote: { submitted: null, submittedDate: null },
  poc: { state: null, completedDate: null },
  procurement: '',
  bant: { budget: null, authority: null, need: null, timeline: null },
  ...over,
})

describe('deals.list over HTTP', () => {
  it('sends GET /deals without a query when nothing is set', async () => {
    const { calls } = stubFetch(json(page([])))

    await createDealsHttp().list({})

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/deals' })
  })

  it('maps every filter to its snake_case query key', async () => {
    const { calls } = stubFetch(json(page([])))

    await createDealsHttp().list({
      keyword: '한빛',
      ownerId: 'u-kim',
      vendorId: 'vd-006',
      solutionId: 'sl-006',
      statusKey: 'prospecting',
      forecastKey: 'pipeline',
      year: 2026,
      quarter: 4,
      revenueFrom: '2026-10-01',
      revenueTo: '2026-12-31',
      bantLabelIds: { budget: 'b1', authority: 'a1', need: 'n1', timeline: 't1' },
      mine: true,
      nextActionStatus: 'closed',
      sort: 'revenueAmount',
      order: 'asc',
      offset: 20,
      limit: 50,
    })

    expect(calls[0]?.method).toBe('GET')
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({
      keyword: '한빛',
      owner_user_id: 'u-kim',
      vendor_id: 'vd-006',
      solution_id: 'sl-006',
      status_key: 'prospecting',
      forecast_key: 'pipeline',
      year: '2026',
      quarter: '4',
      revenue_from: '2026-10-01',
      revenue_to: '2026-12-31',
      bant_budget: 'b1',
      bant_authority: 'a1',
      bant_need: 'n1',
      bant_timeline: 't1',
      mine: 'true',
      next_action_status: 'closed',
      sort: 'revenue_amount',
      order: 'asc',
      offset: '20',
      limit: '50',
    })
  })

  it.each([
    ['open', 'open'],
    ['done', 'done'],
    ['notDone', 'not_done'],
    ['closed', 'closed'],
  ] as const)('maps the Next Action status filter %s to %s', async (status, wire) => {
    const { calls } = stubFetch(json(page([])))

    await createDealsHttp().list({ nextActionStatus: status })

    expect(query(calls[0]?.path ?? '').get('next_action_status')).toBe(wire)
  })

  it('does not send a status filter when none is chosen', async () => {
    const { calls } = stubFetch(json(page([])))

    await createDealsHttp().list({})

    expect(query(calls[0]?.path ?? '').has('next_action_status')).toBe(false)
  })

  it.each([
    ['name', 'name'],
    ['revenueAmount', 'revenue_amount'],
    ['revenueDate', 'revenue_date'],
    ['lastUpdatedAt', 'last_updated_at'],
    ['statusKey', 'status'],
  ] as [DealSortKey, string][])('maps the sort key %s to %s', async (sort, server) => {
    const { calls } = stubFetch(json(page([])))

    await createDealsHttp().list({ sort })

    expect(query(calls[0]?.path ?? '').get('sort')).toBe(server)
  })

  it('sends only the bant categories that are chosen', async () => {
    const { calls } = stubFetch(json(page([])))

    await createDealsHttp().list({ bantLabelIds: { need: 'n1' } })

    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ bant_need: 'n1' })
  })

  it('does not send mine when it is false and sends offset 0 when asked', async () => {
    const { calls } = stubFetch(json(page([])))

    await createDealsHttp().list({ mine: false, offset: 0 })

    const sent = query(calls[0]?.path ?? '')
    expect(sent.has('mine')).toBe(false)
    expect(sent.get('offset')).toBe('0')
  })

  it('reads the rows with total, offset and limit of the server page', async () => {
    stubFetch(json({ items: [serverDealRow()], total: 41, offset: 20, limit: 20 }))

    const result = await createDealsHttp().list({ offset: 20 })

    expect(result).toMatchObject({ total: 41, offset: 20, limit: 20 })
    expect(result.items[0]).toMatchObject({ code: CODE, statusKey: 'prospecting', ownerId: 'u-kim' })
  })

  it('AC-18/19 sends a quarter without a year as the quarter alone (the server reads it as this year)', async () => {
    const { calls } = stubFetch(json(page([])))

    await createDealsHttp().list({ quarter: 2 })

    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ quarter: '2' })
  })

  it('does not send the old vendor and solution text parameters', async () => {
    const { calls } = stubFetch(json(page([])))

    await createDealsHttp().list({ vendorId: 'vd-006' })

    const sent = query(calls[0]?.path ?? '')
    expect(sent.has('vendor')).toBe(false)
    expect(sent.has('solution')).toBe(false)
    expect(sent.get('vendor_id')).toBe('vd-006')
  })
})

describe('deals.get / impact over HTTP', () => {
  it('get reads GET /deals/{code} as a detail with the partner history', async () => {
    const { calls } = stubFetch(json(serverDealDetail()))

    const detail = await createDealsHttp().get(CODE)

    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}` })
    expect(detail).toMatchObject({ code: CODE, partnerHistory: [] })
  })

  it('get shows the 404 message', async () => {
    stubFetch(problem(404, 'not-found', 'Deal을 찾을 수 없습니다.'))

    await expect(createDealsHttp().get(CODE)).rejects.toMatchObject({ status: 404, kind: 'not-found', message: 'Deal을 찾을 수 없습니다.' })
  })

  it('impact reads GET /deals/{code}/deletion-impact in camelCase', async () => {
    const { calls } = stubFetch(json({ history_count: 5, action_count: 3, attachment_count: 2 }))

    const impact = await createDealsHttp().impact(CODE)

    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/deletion-impact` })
    expect(impact).toEqual({ historyCount: 5, actionCount: 3, attachmentCount: 2 })
  })

  it('impact shows the 404 of an unknown deal', async () => {
    stubFetch(problem(404, 'not-found', 'Deal을 찾을 수 없습니다.'))

    await expect(createDealsHttp().impact(CODE)).rejects.toMatchObject({ status: 404 })
  })

  it('AC-17 has no facets call any more', () => {
    expect('facets' in createDealsHttp()).toBe(false)
  })
})

describe('deals.create over HTTP', () => {
  it('posts the snake_case body and reads the 201 detail', async () => {
    const { calls } = stubFetch(json(serverDealDetail(), 201, { Location: `/api/v1/deals/${CODE}` }))

    const detail = await createDealsHttp().create(
      input({
        partner: { contactId: 'c-p', company: '코어테크', name: '이파트', title: '', email: null, phone: '02-000-0000' },
        quote: { submitted: 'YES', submittedDate: '2026-10-05' },
        poc: { state: 'ING', completedDate: null },
        bant: { budget: { id: 'b1' }, authority: null, need: null, timeline: { name: '내후년 구매' } },
        procurement: '입찰',
      }),
    )

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/deals' })
    expect(calls[0]?.body).toEqual({
      name: '한빛은행 ITDR',
      owner_user_id: 'u-kim',
      vendor_id: 'vd-006',
      solution_id: 'sl-006',
      users: 100,
      status_key: 'prospecting',
      forecast_key: 'pipeline',
      revenue_amount: 500_000_000,
      revenue_date: '2027-01-31',
      customer: { contact_id: null, company: '한빛은행', name: '정민수', title: '과장', email: 'min@hanbit.test', phone: null },
      partner: { contact_id: 'c-p', company: '코어테크', name: '이파트', title: null, email: null, phone: '02-000-0000' },
      quote: { submitted: 'YES', submitted_date: '2026-10-05' },
      poc: { state: 'ING', completed_date: null },
      procurement: '입찰',
      bant: { budget: { id: 'b1' }, authority: null, need: null, timeline: { name: '내후년 구매' } },
    })
    expect(detail.code).toBe(CODE)
  })

  it('sends an empty title as null and no partner as null', async () => {
    const { calls } = stubFetch(json(serverDealDetail(), 201))

    await createDealsHttp().create(input({ customer: { contactId: null, company: '한빛은행', name: '정민수', title: '', email: null, phone: null } }))

    const body = calls[0]?.body as { customer: { title: unknown }; partner: unknown }
    expect(body.customer.title).toBeNull()
    expect(body.partner).toBeNull()
  })

  it('sends an empty Expected Close as null so the server answers its own message', async () => {
    const { calls } = stubFetch(json(serverDealDetail(), 201))

    await createDealsHttp().create(input({ revenueDate: '' }))

    expect((calls[0]?.body as { revenue_date: unknown }).revenue_date).toBeNull()
  })

  it.each([
    [403, 'forbidden', '이 작업을 수행할 권한이 없습니다.', 'forbidden'],
    [404, 'not-found', '연락처를 찾을 수 없습니다.', 'not-found'],
    [409, 'already-exists', '이미 등록된 연락처입니다.', 'conflict'],
    [422, 'invalid-value', 'Deal Name을 입력하세요.', 'validation'],
  ])('shows the %s error with the server message', async (status, serverKind, detail, kind) => {
    stubFetch(problem(status, serverKind, detail))

    await expect(createDealsHttp().create(input())).rejects.toMatchObject({ status, kind, message: detail })
  })
})

describe('deals.update over HTTP', () => {
  it('patches only the fields that are given', async () => {
    const { calls } = stubFetch(json(serverDealDetail()))

    await createDealsHttp().update(CODE, { name: '새 이름', ownerId: 'u-park', statusKey: 'qualified', revenueAmount: 700_000_000, revenueDate: '2027-02-28' })

    expect(calls[0]).toMatchObject({ method: 'PATCH', path: `/api/v1/deals/${CODE}` })
    expect(calls[0]?.body).toEqual({
      name: '새 이름',
      owner_user_id: 'u-park',
      status_key: 'qualified',
      revenue_amount: 700_000_000,
      revenue_date: '2027-02-28',
    })
  })

  it('sends an empty Expected Close as null so the server refuses it with its own message', async () => {
    const { calls } = stubFetch(json(serverDealDetail()))

    await createDealsHttp().update(CODE, { revenueDate: '' })

    expect(calls[0]?.body).toEqual({ revenue_date: null })
  })

  it('AC-11 sends vendor_id and a null solution_id together when the vendor changes', async () => {
    const { calls } = stubFetch(json(serverDealDetail()))

    await createDealsHttp().update(CODE, { vendorId: 'vd-003', solutionId: null })

    expect(calls[0]?.body).toEqual({ vendor_id: 'vd-003', solution_id: null })
  })

  it('AC-13 sends a null vendor_id to clear the vendor and omits vendor fields that are not given', async () => {
    const { calls } = stubFetch(json(serverDealDetail()), json(serverDealDetail()))

    await createDealsHttp().update(CODE, { vendorId: null, solutionId: null })
    await createDealsHttp().update(CODE, { name: 'x' })

    expect(calls[0]?.body).toEqual({ vendor_id: null, solution_id: null })
    expect(calls[1]?.body).toEqual({ name: 'x' })
  })

  it('keeps partner null in the body so that the server removes the partner', async () => {
    const { calls } = stubFetch(json(serverDealDetail()))

    await createDealsHttp().update(CODE, { partner: null })

    expect(calls[0]?.body).toEqual({ partner: null })
  })

  it('maps the nested fields of a patch', async () => {
    const { calls } = stubFetch(json(serverDealDetail()))

    await createDealsHttp().update(CODE, {
      customer: { contactId: 'c1', company: '한빛은행', name: '정민수', title: '', email: null, phone: null },
      quote: { submitted: 'NO', submittedDate: null },
      poc: { state: 'YES', completedDate: '2026-10-10' },
      bant: { budget: null, authority: { id: 'a1' }, need: { name: '신규 요건' }, timeline: null },
      users: 5,
      procurement: '',
    })

    expect(calls[0]?.body).toEqual({
      customer: { contact_id: 'c1', company: '한빛은행', name: '정민수', title: null, email: null, phone: null },
      quote: { submitted: 'NO', submitted_date: null },
      poc: { state: 'YES', completed_date: '2026-10-10' },
      bant: { budget: null, authority: { id: 'a1' }, need: { name: '신규 요건' }, timeline: null },
      users: 5,
      procurement: '',
    })
  })

  it.each([
    [403, 'forbidden', 'forbidden'],
    [404, 'not-found', 'not-found'],
    [409, 'already-exists', 'conflict'],
    [422, 'invalid-value', 'validation'],
  ])('shows the %s error', async (status, serverKind, kind) => {
    stubFetch(problem(status, serverKind, '서버 문구'))

    await expect(createDealsHttp().update(CODE, { name: 'x' })).rejects.toMatchObject({ status, kind, message: '서버 문구' })
  })
})

describe('deals.applyChange over HTTP', () => {
  const answer = (over: Record<string, unknown> = {}) => ({ deal: serverDealDetail(), co_changed: [], notice: null, ...over })

  it.each([
    [{ field: 'statusKey', value: 'qualified' }, { field: 'status_key', value: 'qualified' }],
    [{ field: 'forecastKey', value: 'commit' }, { field: 'forecast_key', value: 'commit' }],
    [{ field: 'revenueAmount', value: 900_000_000 }, { field: 'revenue_amount', value: 900_000_000 }],
    [{ field: 'revenueDate', value: '2027-03-31' }, { field: 'revenue_date', value: '2027-03-31' }],
  ] as const)('posts %j as %j', async (change, server) => {
    const { calls } = stubFetch(json(answer()))

    await createDealsHttp().applyChange(CODE, { change })

    expect(calls[0]).toMatchObject({ method: 'POST', path: `/api/v1/deals/${CODE}/changes` })
    expect(calls[0]?.body).toEqual({ change: server })
  })

  it('maps the resolution answers to snake_case', async () => {
    const { calls } = stubFetch(json(answer()))

    await createDealsHttp().applyChange(CODE, {
      change: { field: 'statusKey', value: 'contract_completed' },
      resolution: { revenueAmount: 1_800_000_000, revenueDate: '2026-10-14', statusKey: 'qualified', forecastKey: 'commit' },
    })

    expect(calls[0]?.body).toEqual({
      change: { field: 'status_key', value: 'contract_completed' },
      resolution: { revenue_amount: 1_800_000_000, revenue_date: '2026-10-14', status_key: 'qualified', forecast_key: 'commit' },
    })
  })

  it('maps co_changed and the notice of the response', async () => {
    stubFetch(
      json(
        answer({
          deal: serverDealDetail({ status_key: 'contract_completed', forecast_key: 'won' }),
          co_changed: [{ field: 'forecast_key', from: 'commit', to: 'won' }],
          notice: "Forecast가 'Won'으로 함께 변경되었습니다.",
        }),
      ),
    )

    const result = await createDealsHttp().applyChange(CODE, { change: { field: 'statusKey', value: 'contract_completed' } })

    expect(result.coChanged).toEqual([{ field: 'forecastKey', from: 'commit', to: 'won' }])
    expect(result.notice).toBe("Forecast가 'Won'으로 함께 변경되었습니다.")
    expect(result.deal).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won' })
  })

  it('answers an empty coChanged and a null notice for an independent change', async () => {
    stubFetch(json(answer()))

    const result = await createDealsHttp().applyChange(CODE, { change: { field: 'forecastKey', value: 'commit' } })

    expect(result).toMatchObject({ coChanged: [], notice: null })
  })

  it('shows the 422 message that asks for the revenue', async () => {
    stubFetch(problem(422, 'invalid-value', 'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.'))

    await expect(createDealsHttp().applyChange(CODE, { change: { field: 'statusKey', value: 'contract_completed' } })).rejects.toMatchObject({
      status: 422,
      message: 'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.',
    })
  })

  it.each([
    [403, 'forbidden'],
    [404, 'not-found'],
  ])('shows the %s error', async (status, serverKind) => {
    stubFetch(problem(status, serverKind, '서버 문구'))

    await expect(createDealsHttp().applyChange(CODE, { change: { field: 'forecastKey', value: 'commit' } })).rejects.toMatchObject({ status })
  })
})

describe('deals.remove over HTTP', () => {
  it('deletes with the confirm code in the query and accepts the 204', async () => {
    const { calls } = stubFetch(noContent())

    await expect(createDealsHttp().remove(CODE, CODE)).resolves.toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'DELETE', path: `/api/v1/deals/${CODE}?confirm_code=${CODE}` })
  })

  it('sends the typed confirm code as it is, even when it differs', async () => {
    const { calls } = stubFetch(problem(422, 'invalid-value', 'Deal code가 일치하지 않습니다.'))

    await expect(createDealsHttp().remove(CODE, 'wrong')).rejects.toMatchObject({ status: 422, message: 'Deal code가 일치하지 않습니다.' })

    expect(query(calls[0]?.path ?? '').get('confirm_code')).toBe('wrong')
  })

  it.each([
    [403, 'forbidden', 'forbidden'],
    [404, 'not-found', 'not-found'],
    [409, 'invalid-state', 'conflict'],
  ])('shows the %s error', async (status, serverKind, kind) => {
    stubFetch(problem(status, serverKind, '서버 문구'))

    await expect(createDealsHttp().remove(CODE, CODE)).rejects.toMatchObject({ status, kind, message: '서버 문구' })
  })
})

describe('http gateway wiring', () => {
  it('uses the real deals adapter instead of the 501 placeholder', async () => {
    const { calls } = stubFetch(json(page([])))

    await createHttpGateway().deals.list({})

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/deals' })
  })

  it('uses the real history adapter instead of the 501 placeholder', async () => {
    const { calls } = stubFetch(json([]))

    await createHttpGateway().history.list(CODE, {})

    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/history` })
  })

  it('uses the real attachments adapter instead of the 501 placeholder', async () => {
    const { calls } = stubFetch(json({ items: [] }))

    await expect(createHttpGateway().attachments.list(CODE)).resolves.toEqual([])

    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/attachments` })
  })

  it('keeps only forecast on 501', async () => {
    const gateway = createHttpGateway()

    await expect(gateway.forecast.summary({ year: 2026 })).rejects.toMatchObject({ status: 501 })
  })
})
