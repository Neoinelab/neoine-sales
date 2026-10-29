import { afterEach, describe, expect, it, vi } from 'vitest'
import { createPartnerMeetingsHttp } from './partnerMeetings'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const URL_BASE = '/api/v1/partner-meetings'

const meeting = (over: Record<string, unknown> = {}) => ({
  id: 7,
  partner_company: '코어테크',
  deal: { code: '20270301-D002', name: '대한제조 MFA 확대' },
  meeting_date: '2027-03-05',
  content: '견적 전달\n다음 주 재방문',
  author: { id: 2, name: '김영업', resigned: false, label: '김영업', role: 'sales' },
  created_at: '2027-03-05T11:00:00+09:00',
  updated_at: '2027-03-06T11:00:00+09:00',
  ...over,
})

const mapped = {
  id: 7,
  partnerCompany: '코어테크',
  deal: { code: '20270301-D002', name: '대한제조 MFA 확대' },
  meetingDate: '2027-03-05',
  content: '견적 전달\n다음 주 재방문',
  author: { id: 2, name: '김영업', role: 'sales', status: 'active' },
  createdAt: '2027-03-05T11:00:00+09:00',
  updatedAt: '2027-03-06T11:00:00+09:00',
}

function paramsOf(path: string): URLSearchParams {
  return new URLSearchParams(path.split('?')[1] ?? '')
}

describe('partner meetings over HTTP: list', () => {
  it('reads GET /partner-meetings with the page and sort in snake_case and maps the page', async () => {
    const { calls } = stubFetch(json({ items: [meeting()], total: 12, offset: 0, limit: 10 }))

    const page = await createPartnerMeetingsHttp().list({ sort: 'meetingDate', order: 'desc' }, 0, 10)

    expect(calls[0]).toMatchObject({ method: 'GET' })
    expect(calls[0]?.path.startsWith(URL_BASE + '?')).toBe(true)
    expect(Object.fromEntries(paramsOf(calls[0]?.path ?? ''))).toEqual({ sort: 'meeting_date', order: 'desc', offset: '0', limit: '10' })
    expect(page).toEqual({ items: [mapped], total: 12, offset: 0, limit: 10 })
  })

  it('sends only the conditions that are set, with the planned parameter names', async () => {
    const { calls } = stubFetch(json({ items: [], total: 0, offset: 10, limit: 10 }))

    await createPartnerMeetingsHttp().list(
      { partner: '코어', deal: 'ERP', content: '견적', dateFrom: '2027-03-01', dateTo: '2027-03-31', authorId: 3, sort: 'partner', order: 'asc' },
      10,
      10,
    )

    expect(Object.fromEntries(paramsOf(calls[0]?.path ?? ''))).toEqual({
      partner: '코어',
      deal: 'ERP',
      content: '견적',
      date_from: '2027-03-01',
      date_to: '2027-03-31',
      author_user_id: '3',
      sort: 'partner',
      order: 'asc',
      offset: '10',
      limit: '10',
    })
  })

  it.each([
    ['meetingDate', 'meeting_date'],
    ['partner', 'partner'],
    ['deal', 'deal'],
    ['content', 'content'],
    ['author', 'author'],
  ] as const)('maps the %s sort column to %s', async (sort, wire) => {
    const { calls } = stubFetch(json({ items: [], total: 0, offset: 0, limit: 10 }))

    await createPartnerMeetingsHttp().list({ sort, order: 'asc' }, 0, 10)

    expect(paramsOf(calls[0]?.path ?? '').get('sort')).toBe(wire)
  })

  it('maps a resigned author to status resigned', async () => {
    stubFetch(json({ items: [meeting({ author: { id: 7, name: '강퇴사', resigned: true, label: '강퇴사(퇴사)', role: 'sales' } })], total: 1, offset: 0, limit: 10 }))

    const page = await createPartnerMeetingsHttp().list({ sort: 'meetingDate', order: 'desc' }, 0, 10)

    expect(page.items[0]?.author).toEqual({ id: 7, name: '강퇴사', role: 'sales', status: 'resigned' })
  })

  it('shows the 422 message of a reversed date range', async () => {
    stubFetch(problem(422, 'invalid-value', '미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다.'))

    await expect(createPartnerMeetingsHttp().list({ dateFrom: '2027-03-10', dateTo: '2027-03-01', sort: 'meetingDate', order: 'desc' }, 0, 10)).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다.',
    })
  })
})

describe('partner meetings over HTTP: create', () => {
  it('posts {items} in snake_case and maps the created meetings in order', async () => {
    const { calls } = stubFetch(json({ items: [meeting(), meeting({ id: 8, content: '두 번째' })] }, 201))

    const created = await createPartnerMeetingsHttp().create([
      { partnerCompany: '코어테크', dealCode: '20270301-D002', meetingDate: '2027-03-05', content: '견적 전달' },
      { partnerCompany: '코어테크', dealCode: '20270301-D008', meetingDate: '2027-03-06', content: '두 번째' },
    ])

    expect(calls[0]).toMatchObject({
      method: 'POST',
      path: URL_BASE,
      body: {
        items: [
          { partner_company: '코어테크', deal_code: '20270301-D002', meeting_date: '2027-03-05', content: '견적 전달' },
          { partner_company: '코어테크', deal_code: '20270301-D008', meeting_date: '2027-03-06', content: '두 번째' },
        ],
      },
    })
    expect(created.map((m) => m.id)).toEqual([7, 8])
    expect(created[0]).toEqual(mapped)
  })

  it('moves the located violations of a 422 into problem.itemErrors without a field suffix in the message', async () => {
    const errors = [
      { location: ['items', 1, 'deal_code'], message: '선택한 파트너와 연결된 Deal이 아닙니다.' },
      { location: ['items', 2, 'content'], message: '미팅 내용을 입력하세요.' },
    ]
    stubFetch(problem(422, 'invalid-value', '선택한 파트너와 연결된 Deal이 아닙니다.', { errors }))

    const failure = createPartnerMeetingsHttp().create([{ partnerCompany: '코어테크', dealCode: 'x', meetingDate: '2027-03-05', content: 'a' }])

    await expect(failure).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '선택한 파트너와 연결된 Deal이 아닙니다.',
      problem: { itemErrors: errors },
    })
  })

  it('keeps the field description of a request-validation 422 (only invalid-value is moved to itemErrors)', async () => {
    const errors = [{ loc: ['query', 'content'], msg: 'String should have at most 100 characters', type: 'string_too_long' }]
    stubFetch(problem(422, 'request-validation', '요청 형식이 올바르지 않습니다', { errors }))

    const failure = createPartnerMeetingsHttp().list({ content: 'x'.repeat(101), sort: 'meetingDate', order: 'desc' }, 0, 10)

    await expect(failure).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '요청 형식이 올바르지 않습니다 — content: String should have at most 100 characters',
      problem: { errors },
    })
    await failure.catch((error: { problem?: { itemErrors?: unknown } }) => expect(error.problem?.itemErrors).toBeUndefined())
  })

  it('keeps the field description of a request-validation 422 on create too', async () => {
    const errors = [{ loc: ['body', 'items', 1, 'content'], msg: 'Field required', type: 'missing' }]
    stubFetch(problem(422, 'request-validation', '요청 형식이 올바르지 않습니다', { errors }))

    await expect(createPartnerMeetingsHttp().create([{ partnerCompany: 'a', dealCode: 'b', meetingDate: '2027-03-05', content: 'c' }])).rejects.toMatchObject({
      message: '요청 형식이 올바르지 않습니다 — items.1.content: Field required',
    })
  })

  it('shows the 403 message for a read-only user', async () => {
    stubFetch(problem(403, 'forbidden', '이 작업을 할 권한이 없습니다(읽기 전용 계정)'))

    await expect(createPartnerMeetingsHttp().create([{ partnerCompany: 'a', dealCode: 'b', meetingDate: '2027-03-05', content: 'c' }])).rejects.toMatchObject({
      status: 403,
      message: '이 작업을 할 권한이 없습니다(읽기 전용 계정)',
    })
  })
})

describe('partner meetings over HTTP: update, remove, deal options', () => {
  it('update puts one item to /partner-meetings/{id}', async () => {
    const { calls } = stubFetch(json(meeting({ content: '수정' })))

    const updated = await createPartnerMeetingsHttp().update(7, { partnerCompany: '코어테크', dealCode: '20270301-D002', meetingDate: '2027-03-05', content: '수정' })

    expect(calls[0]).toMatchObject({
      method: 'PUT',
      path: `${URL_BASE}/7`,
      body: { partner_company: '코어테크', deal_code: '20270301-D002', meeting_date: '2027-03-05', content: '수정' },
    })
    expect(updated).toEqual({ ...mapped, content: '수정' })
  })

  it('update puts the located violations of a 422 on problem.itemErrors', async () => {
    const errors = [{ location: ['content'], message: '미팅 내용을 입력하세요.' }]
    stubFetch(problem(422, 'invalid-value', '미팅 내용을 입력하세요.', { errors }))

    await expect(createPartnerMeetingsHttp().update(7, { partnerCompany: 'a', dealCode: 'b', meetingDate: '2027-03-05', content: ' ' })).rejects.toMatchObject({
      problem: { itemErrors: errors },
    })
  })

  it.each([
    [403, 'forbidden', '본인 미팅 기록 또는 admin만 수정할 수 있습니다.'],
    [404, 'not-found', '미팅 기록을 찾을 수 없습니다.'],
  ])('update shows the %s message', async (status, kind, detail) => {
    stubFetch(problem(status, kind, detail))

    await expect(createPartnerMeetingsHttp().update(7, { partnerCompany: 'a', dealCode: 'b', meetingDate: '2027-03-05', content: 'c' })).rejects.toMatchObject({ status, message: detail })
  })

  it('remove deletes /partner-meetings/{id} and accepts 204', async () => {
    const { calls } = stubFetch(noContent())

    await expect(createPartnerMeetingsHttp().remove(7)).resolves.toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'DELETE', path: `${URL_BASE}/7` })
  })

  it('remove shows the 403 message of another author', async () => {
    stubFetch(problem(403, 'forbidden', '본인 미팅 기록 또는 admin만 삭제할 수 있습니다.'))

    await expect(createPartnerMeetingsHttp().remove(7)).rejects.toMatchObject({ status: 403, message: '본인 미팅 기록 또는 admin만 삭제할 수 있습니다.' })
  })

  it('dealOptions reads GET /partner-meetings/deal-options?company= and maps customer_company', async () => {
    const { calls } = stubFetch(json({ items: [{ code: '20270301-D002', name: '대한제조 MFA 확대', customer_company: '대한제조' }] }))

    const options = await createPartnerMeetingsHttp().dealOptions('코어테크')

    expect(calls[0]).toMatchObject({ method: 'GET' })
    expect(calls[0]?.path.startsWith(`${URL_BASE}/deal-options?`)).toBe(true)
    expect(paramsOf(calls[0]?.path ?? '').get('company')).toBe('코어테크')
    expect(options).toEqual([{ code: '20270301-D002', name: '대한제조 MFA 확대', customerCompany: '대한제조' }])
  })
})
