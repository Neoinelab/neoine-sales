import { afterEach, describe, expect, it, vi } from 'vitest'
import { createPartnerMeetingsHttp } from './partnerMeetings'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const URL_BASE = '/api/v1/partner-meetings'

const meeting = (over: Record<string, unknown> = {}) => ({
  id: 7,
  partner_company: '코어테크',
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
  // 목록은 쪽과 정렬을 snake_case로 보내고 응답을 화면 모양으로 바꾼다.
  // 테스트 코드: PA-089
  it('목록은 GET /partner-meetings에 쪽과 정렬을 snake_case로 보내고 응답을 화면 모양으로 바꾼다', async () => {
    // given: 서버가 기록 한 건과 건수를 돌려준다
    const { calls } = stubFetch(json({ items: [meeting()], total: 12, offset: 0, limit: 10 }))

    // when: 기본 정렬로 첫 쪽을 읽는다
    const page = await createPartnerMeetingsHttp().list({ sort: 'meetingDate', order: 'desc' }, 0, 10)

    // then: GET이며 쿼리는 정렬·쪽뿐이고 응답이 화면 모양으로 바뀐다
    expect(calls[0]).toMatchObject({ method: 'GET' })
    expect(calls[0]?.path.startsWith(URL_BASE + '?')).toBe(true)
    expect(Object.fromEntries(paramsOf(calls[0]?.path ?? ''))).toEqual({ sort: 'meeting_date', order: 'desc', offset: '0', limit: '10' })
    expect(page).toEqual({ items: [mapped], total: 12, offset: 0, limit: 10 })
  })

  // 값이 있는 조건만 정해진 파라미터 이름으로 보낸다.
  // 테스트 코드: PA-089
  it('값이 있는 조건만 정해진 파라미터 이름으로 보낸다', async () => {
    // given: 서버가 빈 쪽을 돌려준다
    const { calls } = stubFetch(json({ items: [], total: 0, offset: 10, limit: 10 }))

    // when: 모든 조건을 걸어 둘째 쪽을 읽는다
    await createPartnerMeetingsHttp().list(
      { partner: '코어', content: '견적', dateFrom: '2027-03-01', dateTo: '2027-03-31', authorId: 3, sort: 'partner', order: 'asc' },
      10,
      10,
    )

    // then: 쿼리 이름이 snake_case이다
    expect(Object.fromEntries(paramsOf(calls[0]?.path ?? ''))).toEqual({
      partner: '코어',
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
    ['content', 'content'],
    ['author', 'author'],
  // 정렬 열 이름을 서버 값으로 바꾼다.
  // 테스트 코드: PA-089
  ] as const)('정렬 열 %s는 서버 값 %s로 바꾼다', async (sort, wire) => {
    // given: 서버가 빈 쪽을 돌려준다
    const { calls } = stubFetch(json({ items: [], total: 0, offset: 0, limit: 10 }))

    // when: 그 열로 정렬해 읽는다
    await createPartnerMeetingsHttp().list({ sort, order: 'asc' }, 0, 10)

    // then: sort 값이 서버 값이다
    expect(paramsOf(calls[0]?.path ?? '').get('sort')).toBe(wire)
  })

  // 퇴사한 작성자는 status resigned로 바꾼다.
  // 테스트 코드: PA-089
  it('퇴사한 작성자는 status resigned로 바꾼다', async () => {
    // given: 작성자가 퇴사한 기록을 서버가 돌려준다
    stubFetch(json({ items: [meeting({ author: { id: 7, name: '강퇴사', resigned: true, label: '강퇴사(퇴사)', role: 'sales' } })], total: 1, offset: 0, limit: 10 }))

    // when: 목록을 읽는다
    const page = await createPartnerMeetingsHttp().list({ sort: 'meetingDate', order: 'desc' }, 0, 10)

    // then: 작성자의 status가 resigned다
    expect(page.items[0]?.author).toEqual({ id: 7, name: '강퇴사', role: 'sales', status: 'resigned' })
  })

  // 역전된 날짜 범위의 422 문구를 그대로 보인다.
  // 테스트 코드: PA-089
  it('역전된 날짜 범위는 422 서버 문구를 그대로 보인다', async () => {
    // given: 서버가 역전 범위 422를 돌려준다
    stubFetch(problem(422, 'invalid-value', '미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다.'))

    // when·then: 역전된 범위로 읽으면 422 validation 오류와 서버 문구로 거절된다
    await expect(createPartnerMeetingsHttp().list({ dateFrom: '2027-03-10', dateTo: '2027-03-01', sort: 'meetingDate', order: 'desc' }, 0, 10)).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다.',
    })
  })
})

describe('partner meetings over HTTP: create', () => {
  // 등록은 {items}를 snake_case로 보내고 만든 기록을 순서대로 바꾼다.
  // 테스트 코드: PA-090
  it('등록은 {items}를 snake_case로 보내고 만든 기록을 순서대로 바꾼다', async () => {
    // given: 서버가 만든 기록 둘을 돌려준다
    const { calls } = stubFetch(json({ items: [meeting(), meeting({ id: 8, content: '두 번째' })] }, 201))

    // when: 두 건을 등록한다
    const created = await createPartnerMeetingsHttp().create([
      { partnerCompany: '코어테크', meetingDate: '2027-03-05', content: '견적 전달' },
      { partnerCompany: '코어테크', meetingDate: '2027-03-06', content: '두 번째' },
    ])

    // then: POST 본문이 세 키 항목들이고 응답이 순서대로 바뀐다
    expect(calls[0]).toMatchObject({
      method: 'POST',
      path: URL_BASE,
      body: {
        items: [
          { partner_company: '코어테크', meeting_date: '2027-03-05', content: '견적 전달' },
          { partner_company: '코어테크', meeting_date: '2027-03-06', content: '두 번째' },
        ],
      },
    })
    expect(created.map((m) => m.id)).toEqual([7, 8])
    expect(created[0]).toEqual(mapped)
  })

  // 위치가 있는 422 위반을 problem.itemErrors로 옮기고 문구에 필드 접미사를 붙이지 않는다.
  // 테스트 코드: PA-090
  it('위치가 있는 422 위반은 문구에 필드 접미사 없이 problem.itemErrors로 옮긴다', async () => {
    // given: 서버가 위치가 있는 위반 둘을 돌려준다
    const errors = [
      { location: ['items', 1, 'partner_company'], message: '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.' },
      { location: ['items', 2, 'content'], message: '미팅 내용을 입력하세요.' },
    ]
    stubFetch(problem(422, 'invalid-value', '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.', { errors }))

    // when: 등록한다
    const failure = createPartnerMeetingsHttp().create([{ partnerCompany: '코어테크', meetingDate: '2027-03-05', content: 'a' }])

    // then: 오류 문구는 첫 위반이고 itemErrors가 위반 목록이다
    await expect(failure).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.',
      problem: { itemErrors: errors },
    })
  })

  // request-validation 422는 필드 설명을 문구에 붙이고 itemErrors로 옮기지 않는다.
  // 테스트 코드: PA-089
  it('목록의 request-validation 422는 필드 설명을 문구에 붙이고 itemErrors로 옮기지 않는다', async () => {
    // given: 서버가 request-validation 422를 돌려준다
    const errors = [{ loc: ['query', 'content'], msg: 'String should have at most 100 characters', type: 'string_too_long' }]
    stubFetch(problem(422, 'request-validation', '요청 형식이 올바르지 않습니다', { errors }))

    // when: 101자 내용 조건으로 읽는다
    const failure = createPartnerMeetingsHttp().list({ content: 'x'.repeat(101), sort: 'meetingDate', order: 'desc' }, 0, 10)

    // then: 문구에 필드 설명이 붙고 itemErrors는 없다
    await expect(failure).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '요청 형식이 올바르지 않습니다 — content: String should have at most 100 characters',
      problem: { errors },
    })
    await failure.catch((error: { problem?: { itemErrors?: unknown } }) => expect(error.problem?.itemErrors).toBeUndefined())
  })

  // 등록에서도 request-validation 422의 필드 설명을 문구에 붙인다.
  // 테스트 코드: PA-090
  it('등록의 request-validation 422도 필드 설명을 문구에 붙인다', async () => {
    // given: 서버가 request-validation 422를 돌려준다
    const errors = [{ loc: ['body', 'items', 1, 'content'], msg: 'Field required', type: 'missing' }]
    stubFetch(problem(422, 'request-validation', '요청 형식이 올바르지 않습니다', { errors }))

    // when·then: 등록하면 문구에 필드 설명이 붙은 오류로 거절된다
    await expect(createPartnerMeetingsHttp().create([{ partnerCompany: 'a', meetingDate: '2027-03-05', content: 'c' }])).rejects.toMatchObject({
      message: '요청 형식이 올바르지 않습니다 — items.1.content: Field required',
    })
  })

  // 읽기 전용 사용자의 403 문구를 보인다.
  // 테스트 코드: PA-090
  it('읽기 전용 사용자의 403 문구를 보인다', async () => {
    // given: 서버가 읽기 전용 403을 돌려준다
    stubFetch(problem(403, 'forbidden', '이 작업을 할 권한이 없습니다(읽기 전용 계정)'))

    // when·then: 등록하면 403 오류와 서버 문구로 거절된다
    await expect(createPartnerMeetingsHttp().create([{ partnerCompany: 'a', meetingDate: '2027-03-05', content: 'c' }])).rejects.toMatchObject({
      status: 403,
      message: '이 작업을 할 권한이 없습니다(읽기 전용 계정)',
    })
  })
})

describe('partner meetings over HTTP: update, remove', () => {
  // 수정은 /partner-meetings/{id}에 항목 하나를 PUT한다.
  // 테스트 코드: PA-090
  it('수정은 /partner-meetings/{id}에 항목 하나를 PUT한다', async () => {
    // given: 서버가 수정된 기록을 돌려준다
    const { calls } = stubFetch(json(meeting({ content: '수정' })))

    // when: 기록을 수정한다
    const updated = await createPartnerMeetingsHttp().update(7, { partnerCompany: '코어테크', meetingDate: '2027-03-05', content: '수정' })

    // then: PUT 본문이 세 키이고 응답이 화면 모양으로 바뀐다
    expect(calls[0]).toMatchObject({
      method: 'PUT',
      path: `${URL_BASE}/7`,
      body: { partner_company: '코어테크', meeting_date: '2027-03-05', content: '수정' },
    })
    expect(updated).toEqual({ ...mapped, content: '수정' })
  })

  // 수정의 위치 있는 422 위반도 problem.itemErrors로 옮긴다.
  // 테스트 코드: PA-090
  it('수정의 위치 있는 422 위반도 problem.itemErrors로 옮긴다', async () => {
    // given: 서버가 필드만의 위치 위반을 돌려준다
    const errors = [{ location: ['content'], message: '미팅 내용을 입력하세요.' }]
    stubFetch(problem(422, 'invalid-value', '미팅 내용을 입력하세요.', { errors }))

    // when·then: 수정하면 itemErrors가 든 오류로 거절된다
    await expect(createPartnerMeetingsHttp().update(7, { partnerCompany: 'a', meetingDate: '2027-03-05', content: ' ' })).rejects.toMatchObject({
      problem: { itemErrors: errors },
    })
  })

  it.each([
    [403, 'forbidden', '본인 미팅 기록 또는 admin만 수정할 수 있습니다.'],
    [404, 'not-found', '미팅 기록을 찾을 수 없습니다.'],
  // 수정의 403·404 문구를 그대로 보인다.
  // 테스트 코드: PA-090
  ])('수정의 %s 오류는 서버 문구를 그대로 보인다', async (status, kind, detail) => {
    // given: 서버가 해당 오류를 돌려준다
    stubFetch(problem(status, kind, detail))

    // when·then: 수정하면 그 상태와 서버 문구로 거절된다
    await expect(createPartnerMeetingsHttp().update(7, { partnerCompany: 'a', meetingDate: '2027-03-05', content: 'c' })).rejects.toMatchObject({ status, message: detail })
  })

  // 삭제는 /partner-meetings/{id}를 DELETE하고 204를 성공으로 받는다.
  // 테스트 코드: PA-090
  it('삭제는 /partner-meetings/{id}를 DELETE하고 204를 성공으로 받는다', async () => {
    // given: 서버가 204를 돌려준다
    const { calls } = stubFetch(noContent())

    // when: 삭제한다
    const result = await createPartnerMeetingsHttp().remove(7)

    // then: 값 없이 성공하고 DELETE 요청 경로가 맞다
    expect(result).toBeUndefined()
    expect(calls[0]).toMatchObject({ method: 'DELETE', path: `${URL_BASE}/7` })
  })

  // 다른 작성자의 삭제 403 문구를 그대로 보인다.
  // 테스트 코드: PA-090
  it('다른 작성자 기록의 삭제 403 문구를 그대로 보인다', async () => {
    // given: 서버가 403을 돌려준다
    stubFetch(problem(403, 'forbidden', '본인 미팅 기록 또는 admin만 삭제할 수 있습니다.'))

    // when·then: 삭제하면 403 오류와 서버 문구로 거절된다
    await expect(createPartnerMeetingsHttp().remove(7)).rejects.toMatchObject({ status: 403, message: '본인 미팅 기록 또는 admin만 삭제할 수 있습니다.' })
  })

  // 등록·수정 본문은 정확히 세 키이고 Deal이 없다.
  // 테스트 코드: PA-090
  it('등록·수정 본문은 정확히 세 키이고 Deal이 없다', async () => {
    // given: 등록과 수정에 각각 응답할 서버
    const { calls } = stubFetch(json({ items: [meeting()] }, 201), json(meeting()))

    // when: 등록하고 수정한다
    await createPartnerMeetingsHttp().create([{ partnerCompany: '코어테크', meetingDate: '2027-03-05', content: 'a' }])
    await createPartnerMeetingsHttp().update(7, { partnerCompany: '코어테크', meetingDate: '2027-03-05', content: 'a' })

    // then: 두 본문 모두 세 키뿐이다
    const items = (calls[0]?.body as { items: Record<string, unknown>[] }).items
    expect(Object.keys(items[0] ?? {}).sort()).toEqual(['content', 'meeting_date', 'partner_company'])
    expect(Object.keys((calls[1]?.body ?? {}) as object).sort()).toEqual(['content', 'meeting_date', 'partner_company'])
  })

  // dealOptions 호출이 없고 Deal 없는 응답을 바꾼다.
  // 테스트 코드: PA-089
  it('dealOptions 호출은 더 이상 없고 Deal 없는 응답을 바꾼다', async () => {
    // given: Deal 없는 응답을 돌려주는 서버
    stubFetch(json({ items: [meeting()], total: 1, offset: 0, limit: 10 }))
    const http = createPartnerMeetingsHttp()

    // when: 목록을 읽는다
    const page = await http.list({ sort: 'meetingDate', order: 'desc' }, 0, 10)

    // then: dealOptions가 없고 항목에 deal 키가 없다
    expect('dealOptions' in http).toBe(false)
    expect(Object.keys(page.items[0] ?? {})).not.toContain('deal')
  })

  // 목록 쿼리에 Deal 조건을 보내지 않는다.
  // 테스트 코드: PA-089
  it('목록 쿼리에 Deal 조건을 보내지 않는다', async () => {
    // given: 서버가 빈 쪽을 돌려준다
    const { calls } = stubFetch(json({ items: [], total: 0, offset: 0, limit: 10 }))

    // when: 파트너 조건으로 읽는다
    await createPartnerMeetingsHttp().list({ partner: '코어', sort: 'partner', order: 'asc' }, 0, 10)

    // then: 쿼리에 deal이 없다
    expect(paramsOf(calls[0]?.path ?? '').has('deal')).toBe(false)
  })
})
