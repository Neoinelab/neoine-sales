import { describe, expect, it } from 'vitest'
import { MEETING_CONTENTS } from '../../fixtures/partnerMeetings'
import { dealCode, expectApiError, mockAs } from '../testing'
import { USER_ID } from '../seed/ids'

const DEFAULT = { sort: 'meetingDate', order: 'desc' } as const
const item = (company: string, content: string, meetingDate = '2026-10-01') => ({
  partnerCompany: company,
  meetingDate,
  content,
})

describe('partner meetings Fake: seed', () => {
  // 시드 12건이 기본 정렬 순서로 나온다.
  // 테스트 코드: PA-091
  it('has twelve sample meetings in the planned default order', async () => {
    // given: 시드 12건이 든 Fake에 sales로 로그인했다
    const { gateway } = await mockAs('kim')

    // when: 기본 정렬로 첫 쪽(10건)과 둘째 쪽(2건)을 읽는다
    const first = await gateway.partnerMeetings.list(DEFAULT, 0, 10)
    const second = await gateway.partnerMeetings.list(DEFAULT, 10, 10)

    // then: 전체 12건이 기본 정렬 순서로 나뉜다
    expect(first.total).toBe(12)
    expect(first.items.map((m) => m.content)).toEqual(MEETING_CONTENTS.slice(0, 10))
    expect(second.items.map((m) => m.content)).toEqual(MEETING_CONTENTS.slice(10))
  })

  // 목록 항목에 Deal이 없다.
  // 테스트 코드: PA-091
  it('has no deal in a listed meeting', async () => {
    // given: 시드 12건이 든 Fake
    const { gateway } = await mockAs('kim')

    // when: 목록을 읽는다
    const page = await gateway.partnerMeetings.list(DEFAULT, 0, 10)

    // then: 어느 항목에도 deal 키가 없다
    for (const meeting of page.items) expect(Object.keys(meeting)).not.toContain('deal')
  })

  // Deal 선택지 조회가 없다.
  // 테스트 코드: PA-091
  it('has no deal options lookup any more', async () => {
    // when: Fake 게이트웨이를 만든다
    const { gateway } = await mockAs('kim')

    // then: dealOptions가 없다
    expect('dealOptions' in gateway.partnerMeetings).toBe(false)
  })
})

describe('partner meetings Fake: rules', () => {
  // 다른 sales와 읽기 전용 사용자는 남의 기록을 수정·삭제할 수 없다.
  // 테스트 코드: PA-091
  it('refuses edit and delete of another author record with 403', async () => {
    // given: kim이 만든 기록
    const kim = await mockAs('kim')
    const [created] = await kim.gateway.partnerMeetings.create([item('코어테크', '김영업 기록')])
    const id = created?.id ?? 0

    // when·then: 다른 sales는 수정·삭제가 403이고, 읽기 전용 사용자도 403이다
    await kim.signInAs(USER_ID.park)
    await expectApiError(kim.gateway.partnerMeetings.update(id, item('코어테크', '가로채기')), 403, '본인 미팅 기록 또는 admin만 수정할 수 있습니다.')
    await expectApiError(kim.gateway.partnerMeetings.remove(id), 403, '본인 미팅 기록 또는 admin만 삭제할 수 있습니다.')
    await kim.signInAs(USER_ID.han)
    await expectApiError(kim.gateway.partnerMeetings.update(id, item('코어테크', '읽기 전용')), 403)
  })

  // admin은 남의 기록도 수정·삭제한다.
  // 테스트 코드: PA-091
  it('lets admin edit and delete another author record', async () => {
    // given: kim이 만든 기록과 admin 로그인
    const kim = await mockAs('kim')
    const [created] = await kim.gateway.partnerMeetings.create([item('코어테크', '김영업 기록')])
    const id = created?.id ?? 0
    await kim.signInAs(USER_ID.root)

    // when: 수정하고 삭제한다
    const edited = await kim.gateway.partnerMeetings.update(id, item('코어테크', '관리자 수정'))
    const removed = await kim.gateway.partnerMeetings.remove(id)

    // then: 둘 다 성공한다
    expect(edited).toMatchObject({ content: '관리자 수정' })
    expect(removed).toBeUndefined()
  })

  // 없는 기록은 404다.
  // 테스트 코드: PA-091
  it('answers 404 for a missing record before the content check', async () => {
    // given: 다른 sales(park)로 로그인한 Fake
    const kim = await mockAs('kim')
    await kim.signInAs(USER_ID.park)

    // when·then: 없는 기록을 빈 내용으로 고치면 404다
    await expectApiError(kim.gateway.partnerMeetings.update(Number.MAX_SAFE_INTEGER, item('코어테크', ' ')), 404, '미팅 기록을 찾을 수 없습니다.')
  })

  // 남의 기록은 내용 검사(422)보다 403이 먼저다.
  // 테스트 코드: PA-091
  it('answers 403 for another author record before the content check', async () => {
    // given: kim의 기록과 다른 sales(park)의 로그인
    const kim = await mockAs('kim')
    const [created] = await kim.gateway.partnerMeetings.create([item('코어테크', '기록')])
    await kim.signInAs(USER_ID.park)

    // when·then: 남의 기록을 빈 내용으로 고치면 403이다
    await expectApiError(kim.gateway.partnerMeetings.update(created?.id ?? 0, item('코어테크', ' ')), 403)
  })

  // 일괄 등록은 모든 행을 검사해 위치를 모두 알리고 아무것도 저장하지 않는다.
  // 테스트 코드: PA-091
  it('checks every row of a batch, reports all locations and saves nothing', async () => {
    // given: 시드 12건이 든 Fake
    const kim = await mockAs('kim')

    // when: 정상 행, 없는 회사 행, 빈 내용 행을 함께 등록한다
    const error = await expectApiError(
      kim.gateway.partnerMeetings.create([item('코어테크', '정상'), item('없는회사', '회사 없음'), item('시큐어원', ' ')]),
      422,
    )

    // then: 두 위반이 위치와 함께 나오고 저장된 기록은 12건 그대로다
    expect(error.problem?.itemErrors).toEqual([
      { location: ['items', 1, 'partner_company'], message: '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.' },
      { location: ['items', 2, 'content'], message: '미팅 내용을 입력하세요.' },
    ])
    expect((await kim.gateway.partnerMeetings.list(DEFAULT, 0, 10)).total).toBe(12)
  })

  // Deal 없는 파트너 회사도 등록된다.
  // 테스트 코드: PA-091
  it('registers a meeting for a partner company without any deal', async () => {
    // given: Deal 없이 연락처만 있는 파트너 회사
    const kim = await mockAs('root')
    await kim.gateway.contacts.create('partner', { company: 'Deal없는파트너', name: '가나다', title: '', email: null, phone: null })
    await kim.signInAs(USER_ID.kim)

    // when: 대소문자가 다른 이름으로 등록한다
    const [created] = await kim.gateway.partnerMeetings.create([item('deal없는파트너', '첫 만남')])

    // then: 대표 표기로 저장된다
    expect(created).toMatchObject({ partnerCompany: 'Deal없는파트너', content: '첫 만남' })
  })

  // 회사를 그대로 두면 날짜만 고치고, 없는 회사로 바꾸면 거절한다.
  // 테스트 코드: PA-091
  it('edits the date with the company unchanged and rejects an unknown company', async () => {
    // given: kim의 기록
    const kim = await mockAs('kim')
    const [created] = await kim.gateway.partnerMeetings.create([item('코어테크', '이전')])

    // when: 회사를 그대로 두고 날짜만 고친다
    const edited = await kim.gateway.partnerMeetings.update(created?.id ?? 0, item('코어테크', '이전', '2026-11-30'))

    // then: 날짜가 바뀌고 회사는 그대로이며, 없는 회사로 바꾸면 422다
    expect(edited).toMatchObject({ partnerCompany: '코어테크', meetingDate: '2026-11-30' })
    await expectApiError(kim.gateway.partnerMeetings.update(created?.id ?? 0, item('없는회사', '이전')), 422, '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.')
  })

  // Deal을 지워도 미팅이 남고 삭제 영향에 미팅 건수가 없다.
  // 테스트 코드: PA-091
  it('keeps the meetings when their deal is deleted and counts no partner meetings in the impact', async () => {
    // given: admin으로 로그인한 Fake
    const root = await mockAs('root')
    const code = dealCode(1)
    // when: 삭제 영향을 읽고 Deal을 삭제한다
    const impact = await root.gateway.deals.impact(code)
    await root.gateway.deals.remove(code, code)

    // then: 미팅은 12건 그대로이고 삭제 영향 키는 네 개뿐이다
    expect(Object.keys(impact).sort()).toEqual(['actionCount', 'attachmentCount', 'commentCount', 'historyCount', 'licenseContractCount'])
    const page = await root.gateway.partnerMeetings.list(DEFAULT, 0, 50)
    expect(page.total).toBe(12)
  })
})

describe('partner meetings Fake: 서버와 같은 요청 형식 오류', () => {
  const REQUEST_FORMAT = '요청 형식이 올바르지 않습니다'
  const NUL_CONTENT = '미팅 내용에는 NUL 문자를 쓸 수 없습니다'
  const total = async (gateway: Awaited<ReturnType<typeof mockAs>>['gateway']) => (await gateway.partnerMeetings.list(DEFAULT, 0, 50)).total

  // 빈 목록과 51건은 서버처럼 요청 형식 오류이고 아무것도 저장하지 않는다.
  // 테스트 코드: PA-091
  it('rejects an empty list and 51 items with the request-format error, without row locations or saving', async () => {
    // given: 시드 12건이 든 Fake
    const { gateway } = await mockAs('kim')
    // when: 빈 목록과 51건을 등록한다
    const empty = await expectApiError(gateway.partnerMeetings.create([]), 422, REQUEST_FORMAT)
    const many = await expectApiError(
      gateway.partnerMeetings.create(Array.from({ length: 51 }, (_, i) => item('코어테크', `기록 ${i}`))),
      422,
      REQUEST_FORMAT,
    )
    // then: 행 위치 위반이 없고 저장된 기록은 12건 그대로다
    expect(empty.problem?.itemErrors).toBeUndefined()
    expect(many.problem?.itemErrors).toBeUndefined()
    expect(await total(gateway)).toBe(12)
  })

  // 50건은 받는다.
  // 테스트 코드: PA-091
  it('accepts exactly 50 items', async () => {
    // given: 시드 12건이 든 Fake
    const { gateway } = await mockAs('kim')
    // when: 50건을 등록한다
    const created = await gateway.partnerMeetings.create(Array.from({ length: 50 }, (_, i) => item('코어테크', `기록 ${i}`)))
    // then: 50건이 저장된다
    expect(created).toHaveLength(50)
    expect(await total(gateway)).toBe(62)
  })

  // 형식이 틀린 날짜와 201자 회사명은 행 위반이 아니라 요청 형식 오류다.
  // 테스트 코드: PA-091
  it.each([['2027-02-30'], ['20270310'], ['abc']])('rejects the malformed date %s with the request-format error and saves nothing', async (bad) => {
    // given: 시드 12건이 든 Fake
    const { gateway } = await mockAs('kim')
    // when: 형식이 틀린 날짜가 든 행을 정상 행과 함께 등록한다
    const error = await expectApiError(gateway.partnerMeetings.create([item('코어테크', '정상'), item('코어테크', '날짜 틀림', bad)]), 422, REQUEST_FORMAT)
    // then: 행 위치 위반이 없고 정상 행도 저장되지 않았다
    expect(error.problem?.itemErrors).toBeUndefined()
    expect(await total(gateway)).toBe(12)
  })

  // 201자 회사명은 요청 형식 오류이고 200자는 회사 목록에 없다는 행 위반이다.
  // 테스트 코드: PA-091
  it('rejects a 201-character company name as the request-format error but a 200-character one only as a row violation', async () => {
    // given: 시드 12건이 든 Fake
    const { gateway } = await mockAs('kim')
    // when: 201자와 200자 회사명으로 각각 등록한다
    const long = await expectApiError(gateway.partnerMeetings.create([item('가'.repeat(201), '긴 이름')]), 422, REQUEST_FORMAT)
    const edge = await expectApiError(gateway.partnerMeetings.create([item('가'.repeat(200), '긴 이름')]), 422)
    // then: 201자는 위치 없는 요청 형식 오류, 200자는 partner_company 위치 위반이다
    expect(long.problem?.itemErrors).toBeUndefined()
    expect(edge.problem?.itemErrors).toEqual([{ location: ['items', 0, 'partner_company'], message: '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.' }])
  })

  // 형식이 맞는 범위 밖 날짜는 형식 오류가 아니라 날짜 위치 위반이다.
  // 테스트 코드: PA-091
  it('reports a well-formed date outside the bounds as a located row violation, not a format error', async () => {
    // given: 시드 12건이 든 Fake
    const { gateway } = await mockAs('kim')
    // when: 3000-01-01로 등록한다
    const error = await expectApiError(gateway.partnerMeetings.create([item('코어테크', '범위 밖', '3000-01-01')]), 422)
    // then: meeting_date 위치의 범위 문구다
    expect(error.problem?.itemErrors).toEqual([
      { location: ['items', 0, 'meeting_date'], message: '미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다' },
    ])
  })

  // NUL이 든 내용은 content 위치 위반이다.
  // 테스트 코드: PA-091
  it('reports a NUL in the content at the content location together with other violations', async () => {
    // given: 시드 12건이 든 Fake
    const { gateway } = await mockAs('kim')
    // when: NUL이 든 내용과 없는 회사를 한 행씩 등록한다
    const error = await expectApiError(gateway.partnerMeetings.create([item('코어테크', 'a\u0000b'), item('없는회사', '정상')]), 422)
    // then: 내용 NUL 위반과 회사 위반이 위치와 함께 모두 나오고 저장되지 않는다
    expect(error.problem?.itemErrors).toEqual([
      { location: ['items', 0, 'content'], message: NUL_CONTENT },
      { location: ['items', 1, 'partner_company'], message: '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.' },
    ])
    expect(await total(gateway)).toBe(12)
  })

  // 수정에서도 NUL 내용은 content 위치 위반이다.
  // 테스트 코드: PA-091
  it('reports a NUL in the content of an update at the content location', async () => {
    // given: kim의 기록
    const { gateway } = await mockAs('kim')
    const [created] = await gateway.partnerMeetings.create([item('코어테크', '이전')])
    // when: NUL이 든 내용으로 고친다
    const error = await expectApiError(gateway.partnerMeetings.update(created?.id ?? 0, item('코어테크', 'a\u0000b')), 422)
    // then: content 위치 위반이다
    expect(error.problem?.itemErrors).toEqual([{ location: ['content'], message: NUL_CONTENT }])
  })

  // 수정의 형식 오류는 없는 기록(404)보다 먼저 판정된다.
  // 테스트 코드: PA-091
  it('answers the request-format error of an update before 404', async () => {
    // given: 시드 12건이 든 Fake
    const { gateway } = await mockAs('kim')
    // when: 없는 기록을 형식이 틀린 날짜와 201자 회사명으로 고친다
    const badDate = await expectApiError(gateway.partnerMeetings.update(Number.MAX_SAFE_INTEGER, item('코어테크', '내용', '2027-02-30')), 422, REQUEST_FORMAT)
    const longCompany = await expectApiError(gateway.partnerMeetings.update(Number.MAX_SAFE_INTEGER, item('가'.repeat(201), '내용')), 422, REQUEST_FORMAT)
    // then: 둘 다 404가 아니라 위치 없는 요청 형식 오류다
    expect(badDate.problem?.itemErrors).toBeUndefined()
    expect(longCompany.problem?.itemErrors).toBeUndefined()
  })

  // 읽기 전용 사용자의 쓰기는 요청 형식 검사보다 먼저 403이다.
  // 테스트 코드: PA-091
  it('answers 403 for a read-only user before the request-format check', async () => {
    // given: 읽기 전용 사용자로 로그인한 Fake
    const { gateway } = await mockAs('han')
    // when: 빈 목록으로 등록한다
    const error = await expectApiError(gateway.partnerMeetings.create([]), 403)
    // then: 403이다(문구는 단언하지 않는다)
    expect(error.status).toBe(403)
  })
})

describe('partner meetings Fake: 서버와 같은 목록 조건 검사', () => {
  const REQUEST_FORMAT = '요청 형식이 올바르지 않습니다'
  const OUT_OF_BOUNDS = '미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다'
  const list = (gateway: Awaited<ReturnType<typeof mockAs>>['gateway'], query: Record<string, string>) =>
    gateway.partnerMeetings.list({ ...DEFAULT, ...query }, 0, 10)

  // 범위 밖 검색 날짜는 역전 문구가 아니라 범위 문구다.
  // 테스트 코드: PA-093
  it.each([
    ['dateFrom 1899-12-31', { dateFrom: '1899-12-31' }],
    ['dateTo 3000-01-01', { dateTo: '3000-01-01' }],
    ['both out of bounds and reversed', { dateFrom: '3000-01-01', dateTo: '1899-12-31' }],
  ])('rejects the out-of-bounds search date (%s) with the range message, not the reversed-range message', async (_name, query) => {
    // given: 읽기 전용 사용자로 로그인한 Fake
    const { gateway } = await mockAs('han')
    // when: 범위 밖 날짜로 읽는다
    const error = await expectApiError(list(gateway, query), 422)
    // then: 범위 문구다
    expect(error.message).toBe(OUT_OF_BOUNDS)
  })

  // 201자 파트너와 101자 내용은 요청 형식 오류다.
  // 테스트 코드: PA-093
  it.each([
    ['partner 201', { partner: 'a'.repeat(201) }],
    ['content 101', { content: 'a'.repeat(101) }],
  ])('rejects the too long text condition (%s) with the request-format error', async (_name, query) => {
    // given: 읽기 전용 사용자로 로그인한 Fake
    const { gateway } = await mockAs('han')
    // when: 길이를 넘긴 조건으로 읽는다
    const error = await expectApiError(list(gateway, query), 422)
    // then: 요청 형식 오류 문구다
    expect(error.message).toBe(REQUEST_FORMAT)
  })

  // NUL이 든 텍스트 조건은 입력 위반이다.
  // 테스트 코드: PA-093
  it('rejects a NUL in the content condition as an input violation', async () => {
    // given: 읽기 전용 사용자로 로그인한 Fake
    const { gateway } = await mockAs('han')
    // when: NUL이 든 내용 조건으로 읽는다
    const error = await expectApiError(list(gateway, { content: 'a\u0000b' }), 422)
    // then: 요청 형식 오류가 아니라 NUL 안내 문구다
    expect(error.message).toBe('미팅 내용에는 NUL 문자를 쓸 수 없습니다')
  })

  // NUL과 범위 밖 날짜가 함께 걸리면 서버처럼 NUL이 먼저다.
  // 테스트 코드: PA-093
  it('reports the NUL violation before the out-of-bounds date when both apply', async () => {
    // given: 읽기 전용 사용자로 로그인한 Fake
    const { gateway } = await mockAs('han')
    // when: NUL이 든 내용과 범위 밖 시작일을 함께 보낸다
    const error = await expectApiError(list(gateway, { content: 'a\u0000b', dateFrom: '1899-12-31' }), 422)
    // then: NUL 안내 문구다
    expect(error.message).toBe('미팅 내용에는 NUL 문자를 쓸 수 없습니다')
  })

  // 200자 파트너와 100자 내용은 오류 없이 빈 쪽이다.
  // 테스트 코드: PA-093
  it('accepts a 200-character partner and a 100-character content condition and returns an empty page', async () => {
    // given: 읽기 전용 사용자로 로그인한 Fake
    const { gateway } = await mockAs('han')
    // when: 경계 길이의 조건으로 읽는다
    const partner = await list(gateway, { partner: 'a'.repeat(200) })
    const content = await list(gateway, { content: 'a'.repeat(100) })
    // then: 오류 없이 빈 쪽이다
    expect(partner.total).toBe(0)
    expect(content.total).toBe(0)
  })
})
