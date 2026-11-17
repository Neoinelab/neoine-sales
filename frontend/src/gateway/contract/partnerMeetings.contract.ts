/**
 * 파트너 Activity(미팅 기록) 계약. mock과 실제 서버가 같은 규칙을 지킨다.
 * 호출마다 고유한 내용 접두사를 써서 다른 기록과 섞이지 않게 하고, 만든 것은 스스로 치운다.
 * 미팅은 Deal과 무관하다. 파트너 회사는 이미 등록된 파트너 연락처의 회사를 쓴다(첫 회사).
 */

import { describe, expect, it } from 'vitest'
import type { Gateway } from '../types'
import { expectRejects, NO_SUCH_ID, unique, type MakeGateway } from './support'

const DEFAULT_QUERY = { sort: 'meetingDate', order: 'desc' } as const
const CONTENT_REQUIRED = '미팅 내용을 입력하세요.'
const COMPANY_NOT_FOUND = '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.'
const NOT_FOUND = '미팅 기록을 찾을 수 없습니다.'
const NUL_CONTENT = '미팅 내용에는 NUL 문자를 쓸 수 없습니다'
const DATE_OUT_OF_BOUNDS = '미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다'

async function target(gateway: Gateway): Promise<{ company: string }> {
  const [company] = await gateway.contacts.companies('partner')
  if (!company) throw new Error('등록된 파트너 회사가 없다')
  return { company }
}

const input = (t: { company: string }, content: string, meetingDate = '2026-10-01') => ({
  partnerCompany: t.company,
  meetingDate,
  content,
})

export function partnerMeetingsContract(make: MakeGateway): void {
  describe('partnerMeetings 계약', () => {
    // 여러 건을 등록하면 입력 순서대로 돌려주고 목록은 미팅 날짜 최신순이다.
    // 테스트 코드: PA-091
    it('creates several meetings in input order and lists them newest meeting date first', async () => {
      // given: sales로 로그인한 게이트웨이
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')

      // when: 날짜가 다른 세 건을 한 번에 등록한다
      const created = await gateway.partnerMeetings.create([
        input(t, `${tag} 첫째`, '2026-10-01'),
        input(t, `${tag} 둘째`, '2026-10-03'),
        input(t, `${tag} 셋째`, '2026-10-02'),
      ])

      // then: 응답은 입력 순서이고 목록은 최신 날짜 순이며 건수는 3이다
      expect(created.map((m) => m.content)).toEqual([`${tag} 첫째`, `${tag} 둘째`, `${tag} 셋째`])
      const page = await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 0, 10)
      expect(page.items.map((m) => m.content)).toEqual([`${tag} 둘째`, `${tag} 셋째`, `${tag} 첫째`])
      expect(page.total).toBe(3)
      for (const m of created) await gateway.partnerMeetings.remove(m.id)
    })

    // 등록한 기록은 문서의 필드와 대표 표기 회사, 작성자를 갖고 Deal이 없다.
    // 테스트 코드: PA-091
    it('returns the documented fields with the representative company and author, and no deal', async () => {
      // given: sales로 로그인한 게이트웨이와 내 정보
      const gateway = await make('sales')
      const me = await gateway.auth.me()
      const t = await target(gateway)
      // when: 줄바꿈이 든 내용으로 한 건을 등록한다
      const [created] = await gateway.partnerMeetings.create([input(t, `${unique('pm')} 내용\n둘째 줄`)])

      // then: 회사·날짜·작성자·줄바꿈과 키 목록이 문서와 같다
      expect(created).toMatchObject({ partnerCompany: t.company, meetingDate: '2026-10-01' })
      expect(created?.author).toMatchObject({ id: me.id, status: 'active' })
      expect(created?.content).toContain('\n')
      expect(Object.keys(created ?? {}).sort()).toEqual(['author', 'content', 'createdAt', 'id', 'meetingDate', 'partnerCompany', 'updatedAt'])
      if (created) await gateway.partnerMeetings.remove(created.id)
    })

    // 회사 표기는 등록된 대표 표기로 정리된다.
    // 테스트 코드: PA-091
    it('normalizes the company spelling to the registered one', async () => {
      // given: sales로 로그인한 게이트웨이
      const gateway = await make('sales')
      const t = await target(gateway)
      // when: 대문자로 바꾼 회사명으로 등록한다
      const [created] = await gateway.partnerMeetings.create([{ ...input(t, unique('pm')), partnerCompany: t.company.toUpperCase() }])

      // then: 등록된 표기로 저장된다
      expect(created?.partnerCompany).toBe(t.company)
      if (created) await gateway.partnerMeetings.remove(created.id)
    })

    // 내용의 앞뒤 공백은 지워지고 미래 날짜를 받는다.
    // 테스트 코드: PA-091
    it('trims the content and accepts a future date', async () => {
      // given: sales로 로그인한 게이트웨이
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')
      // when: 앞뒤 공백이 붙은 내용과 2999-12-31로 등록한다
      const [created] = await gateway.partnerMeetings.create([input(t, `  ${tag}  \n`, '2999-12-31')])

      // then: 내용은 정리되고 날짜는 그대로다
      expect(created?.content).toBe(tag)
      expect(created?.meetingDate).toBe('2999-12-31')
      if (created) await gateway.partnerMeetings.remove(created.id)
    })

    // 행이 틀리면 아무것도 저장하지 않고 모든 위반을 위치와 함께 알린다.
    // 테스트 코드: PA-091
    it('saves nothing and reports every violation with its location when a row is invalid', async () => {
      // given: sales로 로그인한 게이트웨이
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')

      // when: 정상 행, 없는 회사 행, 빈 내용 행을 함께 등록한다
      const error = await expectRejects(
        gateway.partnerMeetings.create([input(t, `${tag} ok`), { ...input(t, `${tag} bad`), partnerCompany: '없는회사이름' }, input(t, '   ')]),
        422,
      )

      // then: 두 위반이 위치와 함께 나오고 저장된 기록이 없다
      expect(error.problem?.itemErrors).toEqual([
        { location: ['items', 1, 'partner_company'], message: COMPANY_NOT_FOUND },
        { location: ['items', 2, 'content'], message: CONTENT_REQUIRED },
      ])
      expect((await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 0, 10)).total).toBe(0)
    })

    // Deal 없는 파트너 회사도 등록된다.
    // 테스트 코드: PA-091
    it('registers a meeting for a partner company that has no deal', async () => {
      // given: admin이 Deal 없는 파트너 연락처를 만들었다
      const admin = await make('admin')
      const company = unique('NoDealPartner')
      await admin.contacts.create('partner', { company, name: '가나다', title: '', email: null, phone: null })
      const sales = await make('sales')

      // when: sales가 그 회사로 등록한다
      const [created] = await sales.partnerMeetings.create([{ partnerCompany: company, meetingDate: '2026-10-01', content: unique('pm') }])

      // then: 그 회사명으로 저장된다
      expect(created?.partnerCompany).toBe(company)
      if (created) await sales.partnerMeetings.remove(created.id)
    })

    // 빈 목록과 51건은 요청 형식 오류이고 저장하지 않는다.
    // 테스트 코드: PA-091
    it('rejects an empty list and more than 50 items with the request-format error and saves nothing', async () => {
      // given: sales로 로그인한 게이트웨이
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')

      // when: 빈 목록과 51건을 각각 등록한다
      const empty = await expectRejects(gateway.partnerMeetings.create([]), 422)
      const many = await expectRejects(gateway.partnerMeetings.create(Array.from({ length: 51 }, () => input(t, `${tag} x`))), 422)

      // then: 행 위치 위반이 없고 저장된 기록이 없다
      expect(empty.problem?.itemErrors).toBeUndefined()
      expect(many.problem?.itemErrors).toBeUndefined()
      expect((await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 0, 10)).total).toBe(0)
    })

    // 형식이 틀린 날짜와 201자 회사명은 행 검사보다 먼저 요청 형식 오류다.
    // 테스트 코드: PA-091
    it('rejects a malformed meeting date and a 201-character company with the request-format error, before the row checks', async () => {
      // given: sales로 로그인한 게이트웨이
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')

      // when: 형식이 틀린 날짜와 201자 회사명이 든 요청을 각각 등록한다
      const badDates = []
      for (const bad of ['2027-02-30', '20270310', 'abc']) {
        badDates.push(await expectRejects(gateway.partnerMeetings.create([input(t, `${tag} ok`), input(t, `${tag} bad`, bad)]), 422))
      }
      const long = await expectRejects(gateway.partnerMeetings.create([{ ...input(t, `${tag} long`), partnerCompany: '가'.repeat(201) }]), 422)

      // then: 모두 행 위치 위반 없이 거절되고 저장된 기록이 없다
      expect(badDates.map((e) => e.problem?.itemErrors)).toEqual([undefined, undefined, undefined])
      expect(long.problem?.itemErrors).toBeUndefined()
      expect((await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 0, 10)).total).toBe(0)
    })

    // 수정의 형식 오류는 404보다 먼저다.
    // 테스트 코드: PA-091
    it('answers the request-format error of an update before 404', async () => {
      // given: sales로 로그인한 게이트웨이
      const gateway = await make('sales')
      const t = await target(gateway)

      // when: 없는 기록을 틀린 날짜로 고친다
      const error = await expectRejects(gateway.partnerMeetings.update(NO_SUCH_ID, input(t, unique('pm'), '2027-02-30')), 422)

      // then: 404가 아니라 위치 없는 422다
      expect(error.problem?.itemErrors).toBeUndefined()
    })

    // 내용의 NUL은 content 위치 위반이다.
    // 테스트 코드: PA-091
    it('reports a NUL in the content at the content location', async () => {
      // given: sales로 로그인한 게이트웨이
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')

      // when: NUL이 든 내용으로 등록한다
      const error = await expectRejects(gateway.partnerMeetings.create([input(t, `${tag}\u0000x`)]), 422)

      // then: content 위치 위반이고 저장되지 않는다
      expect(error.problem?.itemErrors).toEqual([{ location: ['items', 0, 'content'], message: NUL_CONTENT }])
      expect((await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 0, 10)).total).toBe(0)
    })

    // 범위 밖 검색 날짜는 범위 문구, 긴 텍스트 조건은 요청 형식 오류다.
    // 테스트 코드: PA-093
    it('rejects an out-of-bounds search date with the range message and a too long text condition with the request-format error', async () => {
      // given: user로 로그인한 게이트웨이
      const { partnerMeetings } = await make('user')

      // when·then: 범위 밖 날짜(역전 포함)는 422 범위 문구, 201자 파트너·101자 내용은 422로 거절된다
      await expectRejects(partnerMeetings.list({ ...DEFAULT_QUERY, dateFrom: '1899-12-31' }, 0, 10), 422, DATE_OUT_OF_BOUNDS)
      await expectRejects(partnerMeetings.list({ ...DEFAULT_QUERY, dateTo: '3000-01-01' }, 0, 10), 422, DATE_OUT_OF_BOUNDS)
      await expectRejects(partnerMeetings.list({ ...DEFAULT_QUERY, dateFrom: '3000-01-01', dateTo: '1899-12-31' }, 0, 10), 422, DATE_OUT_OF_BOUNDS)
      await expectRejects(partnerMeetings.list({ ...DEFAULT_QUERY, partner: 'a'.repeat(201) }, 0, 10), 422)
      await expectRejects(partnerMeetings.list({ ...DEFAULT_QUERY, content: 'a'.repeat(101) }, 0, 10), 422)
    })

    // 경계 길이의 텍스트 조건은 받고 NUL은 거절한다.
    // 테스트 코드: PA-093
    it('accepts a 200-character partner and a 100-character content condition and rejects a NUL in a text condition', async () => {
      // given: user로 로그인한 게이트웨이
      const { partnerMeetings } = await make('user')

      // when: 200자 파트너, 100자 내용, NUL이 든 내용으로 각각 읽는다
      const partner = await partnerMeetings.list({ ...DEFAULT_QUERY, partner: 'a'.repeat(200) }, 0, 10)
      const content = await partnerMeetings.list({ ...DEFAULT_QUERY, content: 'a'.repeat(100) }, 0, 10)
      const nul = await expectRejects(partnerMeetings.list({ ...DEFAULT_QUERY, content: 'a\u0000b' }, 0, 10), 422)

      // then: 앞의 둘은 빈 쪽이고 NUL은 422 NUL 안내다
      expect([partner.total, content.total]).toEqual([0, 0])
      expect(nul.message).toBe('미팅 내용에는 NUL 문자를 쓸 수 없습니다')
    })

    // 내용·파트너·날짜 범위(양끝 포함)·작성자 조건은 AND이고 건수를 알린다.
    // 테스트 코드: PA-091
    it('filters by content, partner, date range (inclusive) and author with AND, and reports the total', async () => {
      // given: 날짜가 다른 세 건을 등록했다
      const gateway = await make('sales')
      const me = await gateway.auth.me()
      const t = await target(gateway)
      const tag = unique('pm')
      const created = await gateway.partnerMeetings.create([
        input(t, `${tag} a`, '2026-09-01'),
        input(t, `${tag} b`, '2026-09-02'),
        input(t, `${tag} c`, '2026-09-03'),
      ])

      // when: 날짜 범위, 쪽 나누기, AND 조건, 없는 작성자로 각각 읽는다
      const range = await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag, dateFrom: '2026-09-02', dateTo: '2026-09-03' }, 0, 10)
      const paged = await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 1, 1)
      const anded = await gateway.partnerMeetings.list(
        { ...DEFAULT_QUERY, content: tag, partner: t.company.slice(0, 2), authorId: me.id },
        0,
        10,
      )
      const none = await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag, authorId: NO_SUCH_ID }, 0, 10)

      // then: 조건대로 걸러지고 건수가 조건을 따른다
      expect(range.items.map((m) => m.content)).toEqual([`${tag} c`, `${tag} b`])
      expect(paged.items.map((m) => m.content)).toEqual([`${tag} b`])
      expect(paged).toMatchObject({ total: 3, offset: 1, limit: 1 })
      expect(anded.total).toBe(3)
      expect(none.total).toBe(0)
      for (const m of created) await gateway.partnerMeetings.remove(m.id)
    })

    // 필터의 %와 _는 글자 그대로 찾는다.
    // 테스트 코드: PA-091
    it('treats % and _ in a filter literally', async () => {
      // given: "10%"가 든 기록과 "100"이 든 기록
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')
      const created = await gateway.partnerMeetings.create([input(t, `${tag} 10%`, '2026-09-01'), input(t, `${tag} 100`, '2026-09-02')])

      // when: 내용 조건 "10%"로 읽는다
      const page = await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: `${tag} 10%` }, 0, 10)

      // then: "10%" 기록만 나온다
      expect(page.items.map((m) => m.content)).toEqual([`${tag} 10%`])
      for (const m of created) await gateway.partnerMeetings.remove(m.id)
    })

    // 각 열을 양방향으로 정렬하고 동률은 최신 날짜 순이다.
    // 테스트 코드: PA-091
    it('sorts by each column in both directions with ties by newest date', async () => {
      // given: 내용·날짜가 다른 세 건을 등록했다
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')
      const created = await gateway.partnerMeetings.create([
        input(t, `${tag} banana`, '2026-09-03'),
        input(t, `${tag} Apple`, '2026-09-01'),
        input(t, `${tag} cherry`, '2026-09-02'),
      ])

      // when: 내용·파트너·미팅 날짜 열을 양방향으로 읽는다
      const byContent = (order: 'asc' | 'desc') => gateway.partnerMeetings.list({ sort: 'content', order, content: tag }, 0, 10)
      const byPartner = (order: 'asc' | 'desc') => gateway.partnerMeetings.list({ sort: 'partner', order, content: tag }, 0, 10)

      // then: 방향대로 정렬되고 파트너 열의 동률은 최신 날짜 순이다
      expect((await byContent('asc')).items.map((m) => m.content.slice(tag.length + 1))).toEqual(['Apple', 'banana', 'cherry'])
      expect((await byContent('desc')).items.map((m) => m.content.slice(tag.length + 1))).toEqual(['cherry', 'banana', 'Apple'])
      for (const order of ['asc', 'desc'] as const) {
        expect((await byPartner(order)).items.map((m) => m.content.slice(tag.length + 1))).toEqual(['banana', 'cherry', 'Apple'])
      }
      const oldest = await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'asc', content: tag }, 0, 10)
      expect(oldest.items.map((m) => m.content.slice(tag.length + 1))).toEqual(['Apple', 'cherry', 'banana'])
      for (const m of created) await gateway.partnerMeetings.remove(m.id)
    })

    // 역전된 검색 범위는 거절된다.
    // 테스트 코드: PA-091
    it('rejects a reversed date range in the search', async () => {
      // given: sales로 로그인한 게이트웨이
      const { partnerMeetings } = await make('sales')

      // when·then: 시작이 끝보다 늦은 범위로 읽으면 422와 서버 문구로 거절된다
      await expectRejects(partnerMeetings.list({ ...DEFAULT_QUERY, dateFrom: '2026-10-02', dateTo: '2026-10-01' }, 0, 10), 422, '미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다.')
    })

    // 모든 역할이 읽는다.
    // 테스트 코드: PA-091
    it('lets every role read', async () => {
      // when: 역할마다 목록을 읽는다
      const limits: number[] = []
      for (const role of ['admin', 'sales', 'user'] as const) {
        const { partnerMeetings } = await make(role)
        limits.push((await partnerMeetings.list(DEFAULT_QUERY, 0, 10)).limit)
      }

      // then: 모든 역할이 읽는다
      expect(limits).toEqual([10, 10, 10])
    })

    // 로그아웃한 호출은 거절된다.
    // 테스트 코드: PA-091
    it('refuses an anonymous caller with 401', async () => {
      // given: user로 로그인했다가 로그아웃한 게이트웨이
      const gateway = await make('user')
      await gateway.auth.logout()

      // when·then: 목록을 읽으면 401로 거절된다
      await expectRejects(gateway.partnerMeetings.list(DEFAULT_QUERY, 0, 10), 401)
    })

    // 읽기 전용 사용자의 쓰기는 403으로 거절된다.
    // 테스트 코드: PA-091
    it('refuses writes from a read-only user with 403', async () => {
      // given: sales가 만든 기록과 user 로그인
      const writer = await make('sales')
      const t = await target(writer)
      const [created] = await writer.partnerMeetings.create([input(t, unique('pm'))])
      const { partnerMeetings } = await make('user')

      // when·then: 등록·수정·삭제를 하면 모두 403으로 거절된다
      await expectRejects(partnerMeetings.create([input(t, unique('pm'))]), 403)
      await expectRejects(partnerMeetings.update(created?.id ?? 0, input(t, unique('pm'))), 403)
      await expectRejects(partnerMeetings.remove(created?.id ?? 0), 403)
      const cleanup = await make('sales')
      if (created) await cleanup.partnerMeetings.remove(created.id)
    })

    // 날짜·내용을 고쳐도 작성자는 그대로이고 값이 바뀐 때만 변경 시각이 바뀐다.
    // 테스트 코드: PA-091
    it('updates the date and content, keeps the author and bumps updatedAt only when something changed', async () => {
      // given: sales의 기록
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')
      const [created] = await gateway.partnerMeetings.create([input(t, `${tag} 이전`)])
      if (!created) throw new Error('생성 실패')

      // when: 같은 값으로 고치고 이어서 다른 값으로 고친다
      const same = await gateway.partnerMeetings.update(created.id, input(t, `${tag} 이전`))
      const changed = await gateway.partnerMeetings.update(created.id, input(t, `${tag} 이후`, '2026-11-02'))

      // then: 같은 값은 변경 시각이 그대로이고 다른 값은 날짜·내용만 바뀐다
      expect(same.updatedAt).toBe(created.updatedAt)
      expect(changed).toMatchObject({ id: created.id, content: `${tag} 이후`, meetingDate: '2026-11-02', author: created.author, createdAt: created.createdAt })
      await gateway.partnerMeetings.remove(created.id)
    })

    // admin은 남의 기록을 수정·삭제한다.
    // 테스트 코드: PA-091
    it('lets admin edit and delete someone elses record', async () => {
      // given: sales의 기록
      const sales = await make('sales')
      const t = await target(sales)
      const tag = unique('pm')
      const [created] = await sales.partnerMeetings.create([input(t, `${tag} 원본`)])
      if (!created) throw new Error('생성 실패')

      // when: admin이 고치고 삭제한다
      const admin = await make('admin')
      const edited = await admin.partnerMeetings.update(created.id, input(t, `${tag} 관리자`))
      await admin.partnerMeetings.remove(created.id)

      // then: 내용이 바뀌었고 작성자는 그대로이며 삭제 뒤 기록이 없다
      expect(edited.content).toBe(`${tag} 관리자`)
      expect(edited.author).toEqual(created.author)
      expect((await admin.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 0, 10)).total).toBe(0)
    })

    // 없는 기록은 다른 검사보다 먼저 404 문구다.
    // 테스트 코드: PA-091
    it('answers 404 with the message for a missing record before anything else', async () => {
      // given: sales로 로그인한 게이트웨이
      const gateway = await make('sales')
      const t = await target(gateway)

      // when·then: 없는 기록을 빈 내용으로 고치거나 삭제하면 404 문구로 거절된다
      await expectRejects(gateway.partnerMeetings.update(NO_SUCH_ID, input(t, '  ')), 404, NOT_FOUND)
      await expectRejects(gateway.partnerMeetings.remove(NO_SUCH_ID), 404, NOT_FOUND)
    })

    // 회사는 바뀔 때만 다시 확인한다.
    // 테스트 코드: PA-091
    it('rechecks the company only when it changes', async () => {
      // given: sales의 기록
      const gateway = await make('sales')
      const t = await target(gateway)
      const [created] = await gateway.partnerMeetings.create([input(t, unique('pm'))])
      if (!created) throw new Error('생성 실패')

      // when: 대소문자만 다른 같은 회사로 고치고, 없는 회사로 고친다
      const same = await gateway.partnerMeetings.update(created.id, { ...input(t, unique('pm')), partnerCompany: t.company.toUpperCase() })
      const error = await expectRejects(gateway.partnerMeetings.update(created.id, { ...input(t, unique('pm')), partnerCompany: '없는회사이름' }), 422)

      // then: 같은 회사는 저장 표기 그대로이고 없는 회사는 partner_company 위치로 거절된다
      expect(same.partnerCompany).toBe(t.company)
      expect(error.problem?.itemErrors?.[0]?.location).toEqual(['partner_company'])
      await gateway.partnerMeetings.remove(created.id)
    })

    // 수정의 위반은 필드만의 위치로 알린다.
    // 테스트 코드: PA-091
    it('reports an update violation with a field-only location', async () => {
      // given: sales의 기록
      const gateway = await make('sales')
      const t = await target(gateway)
      const [created] = await gateway.partnerMeetings.create([input(t, unique('pm'))])
      if (!created) throw new Error('생성 실패')

      // when: 빈 내용으로 고친다
      const error = await expectRejects(gateway.partnerMeetings.update(created.id, input(t, '   ')), 422, CONTENT_REQUIRED)

      // then: 위치는 ["content"]다
      expect(error.problem?.itemErrors).toEqual([{ location: ['content'], message: CONTENT_REQUIRED }])
      await gateway.partnerMeetings.remove(created.id)
    })

    // Deal 삭제 영향에 미팅 건수가 없다.
    // 테스트 코드: PA-091
    it('does not count partner meetings in a deal deletion impact', async () => {
      // given: admin의 미팅 기록과 Deal 하나
      const admin = await make('admin')
      const t = await target(admin)
      const tag = unique('pm')
      const [created] = await admin.partnerMeetings.create([input(t, `${tag} a`)])
      const [deal] = (await admin.deals.list({ limit: 1 })).items
      if (!created || !deal) throw new Error('준비 실패')

      // when: Deal의 삭제 영향을 읽는다
      const impact = await admin.deals.impact(deal.code)

      // then: 키는 네 건수뿐이고 미팅은 그대로 있다
      expect(Object.keys(impact).sort()).toEqual(['actionCount', 'attachmentCount', 'commentCount', 'historyCount', 'licenseContractCount'])
      expect((await admin.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 0, 10)).total).toBe(1)
      await admin.partnerMeetings.remove(created.id)
    })
  })
}
