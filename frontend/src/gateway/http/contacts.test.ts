import { afterEach, describe, expect, it, vi } from 'vitest'
import { createContactsHttp } from './contacts'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const contact = (over: Record<string, unknown> = {}) => ({
  id: 9,
  kind: 'customer',
  company: '네오인',
  name: '홍길동',
  title: null,
  email: null,
  phone: null,
  created_at: '2026-10-01T09:00:00+09:00',
  updated_at: '2026-10-02T09:00:00+09:00',
  ...over,
})

describe('contacts over HTTP', () => {
  // 회사 목록 조회는 종류를 쿼리로 보낸다
  // 테스트 코드: CT-106
  it('companies reads GET /contacts/companies for the kind', async () => {
    // given: 회사 목록 응답을 흉내 내는 fetch
    const { calls } = stubFetch(json(['네오인', '에이콘']))

    // when: 고객 종류로 회사 목록을 읽는다
    const result = await createContactsHttp().companies('customer')

    // then: GET /contacts/companies?kind=customer를 보내고 회사명 배열을 돌려준다
    expect(result).toEqual(['네오인', '에이콘'])

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/contacts/companies?kind=customer' })
  })

  // 회사별 담당자 조회는 종류와 회사명을 보내고 연결 Deal 수를 매핑한다
  // 테스트 코드: CT-106
  it('byCompany reads the people of one company with their Deal counts', async () => {
    // given: 담당자 한 명과 deal_count 2를 돌려주는 fetch
    const { calls } = stubFetch(json([{ ...contact({ title: '팀장', email: 'hong@neoine.test' }), deal_count: 2 }]))

    // when: 파트너 종류와 회사명으로 읽는다
    const rows = await createContactsHttp().byCompany('partner', '네오인')

    // then: 종류·회사명 쿼리를 보내고 dealCount 등 camelCase로 변환한다
    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/contacts/by-company?kind=partner&company=${encodeURIComponent('네오인')}` })
    expect(rows[0]).toEqual({
      id: 9,
      kind: 'customer',
      company: '네오인',
      name: '홍길동',
      title: '팀장',
      email: 'hong@neoine.test',
      phone: null,
      createdAt: '2026-10-01T09:00:00+09:00',
      updatedAt: '2026-10-02T09:00:00+09:00',
      dealCount: 2,
    })
  })

  // 응답의 null 직급은 빈 값으로 바꾼다
  // 테스트 코드: CT-106
  it('maps a missing title to an empty string', async () => {
    // given: 직급이 null인 응답
    stubFetch(json([{ ...contact(), deal_count: 0 }]))

    // when: 회사별 담당자를 읽는다
    const [row] = await createContactsHttp().byCompany('customer', '네오인')

    // then: 직급이 빈 문자열이다
    expect(row?.title).toBe('')
  })

  // 관리 목록 조회는 정한 조건만 보내고 응답의 total을 읽는다
  // 테스트 코드: CT-106
  it('list sends the filters and reads total from the page', async () => {
    // given: 41건 중 한 페이지를 돌려주는 fetch
    const { calls } = stubFetch(json({ items: [{ ...contact(), deal_count: 1 }], total: 41, offset: 20, limit: 20 }))

    // when: 종류·키워드·offset·limit을 주고 읽는다
    const page = await createContactsHttp().list({ kind: 'customer', keyword: '홍', offset: 20, limit: 20 })

    // then: 그 조건만 쿼리로 보내고 total·offset·limit을 돌려준다
    expect(calls[0]).toMatchObject({
      method: 'GET',
      path: `/api/v1/contacts?kind=customer&keyword=${encodeURIComponent('홍')}&offset=20&limit=20`,
    })
    expect(page).toMatchObject({ total: 41, offset: 20, limit: 20 })
    expect(page.items[0]).toMatchObject({ id: 9, dealCount: 1 })
  })

  // 주지 않은 조건은 쿼리에 싣지 않는다
  // 테스트 코드: CT-106
  it('list omits the filters that are not set', async () => {
    // given: 빈 목록을 돌려주는 fetch
    const { calls } = stubFetch(json({ items: [], total: 0, offset: 0, limit: 50 }))

    // when: 조건 없이 읽는다
    await createContactsHttp().list({})

    // then: 쿼리 없는 경로로 요청한다
    expect(calls[0]?.path).toBe('/api/v1/contacts')
  })

  // admin이 아니면 관리 목록은 403 오류가 된다
  it('list shows the 403 of a non-admin', async () => {
    // given: 403 응답을 돌려주는 fetch
    stubFetch(problem(403, 'forbidden', '이 작업을 수행할 권한이 없습니다.'))

    // when·then: 관리 목록을 읽는다 → 403 forbidden ApiError로 거절된다
    await expect(createContactsHttp().list({})).rejects.toMatchObject({ status: 403, kind: 'forbidden' })
  })

  // 등록은 종류와 다섯 값을 본문으로 POST한다
  // 테스트 코드: CT-107
  it('create posts the kind with company, name, title, email and phone', async () => {
    // given: 201 응답을 돌려주는 fetch
    const { calls } = stubFetch(json(contact({ title: '팀장', email: 'hong@neoine.test', phone: '010-1234-5678' }), 201))

    // when: 고객 연락처를 등록한다
    const created = await createContactsHttp().create('customer', {
      company: '네오인',
      name: '홍길동',
      title: '팀장',
      email: 'hong@neoine.test',
      phone: '010-1234-5678',
    })

    // then: kind를 포함한 본문으로 POST하고 응답을 변환해 돌려준다
    expect(calls[0]).toMatchObject({
      method: 'POST',
      path: '/api/v1/contacts',
      body: { kind: 'customer', company: '네오인', name: '홍길동', title: '팀장', email: 'hong@neoine.test', phone: '010-1234-5678' },
    })
    expect(created).toMatchObject({ id: 9, title: '팀장', phone: '010-1234-5678' })
  })

  // 등록은 빈 직급을 null로 보낸다
  // 테스트 코드: CT-107
  it('create sends an empty title as null', async () => {
    // given: 201 응답을 돌려주는 fetch
    const { calls } = stubFetch(json(contact(), 201))

    // when: 직급이 빈 연락처를 등록한다
    await createContactsHttp().create('partner', { company: 'A', name: 'B', title: '', email: null, phone: null })

    // then: 본문의 직급이 null이다
    expect(calls[0]?.body).toEqual({ kind: 'partner', company: 'A', name: 'B', title: null, email: null, phone: null })
  })

  // 등록 실패(같은 사람·공백·형식)는 서버 문구를 그대로 오류 메시지로 쓴다
  // 테스트 코드: CT-107
  it.each([
    [409, 'already-exists', '이미 등록된 연락처입니다.', 'conflict'],
    [422, 'invalid-value', '공백은 입력할 수 없습니다.', 'validation'],
    [422, 'invalid-value', '이메일 형식이 올바르지 않습니다.', 'validation'],
    [422, 'invalid-value', '전화번호 형식이 올바르지 않습니다.', 'validation'],
  ])('create failure %i "%s" keeps the server message', async (status, serverKind, detail, kind) => {
    // given: 서버가 오류 응답을 돌려준다
    stubFetch(problem(status, serverKind, detail))

    // when·then: 연락처를 등록한다 → 상태·종류·서버 문구를 가진 오류로 거절된다
    await expect(createContactsHttp().create('customer', { company: 'A', name: 'B', title: '', email: null, phone: null })).rejects.toMatchObject({
      status,
      kind,
      message: detail,
    })
  })

  // 수정은 종류 없이 다섯 값을 PUT하고 빈 직급은 null로 보낸다
  // 테스트 코드: CT-107
  it('update puts the fields without the kind', async () => {
    // given: 200 응답을 돌려주는 fetch
    const { calls } = stubFetch(json(contact({ name: '김철수' })))

    // when: 연락처를 수정한다
    const updated = await createContactsHttp().update(9, { company: '네오인', name: '김철수', title: '', email: null, phone: null })

    // then: kind 없는 본문으로 PUT한다
    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/contacts/9', body: { company: '네오인', name: '김철수', title: null, email: null, phone: null } })
    expect(calls[0]?.body).not.toHaveProperty('kind')
    expect(updated.name).toBe('김철수')
  })

  // 삭제는 204를 성공으로 받는다
  // 테스트 코드: CT-107
  it('remove deletes and accepts 204', async () => {
    // given: 204를 돌려주는 fetch
    const { calls } = stubFetch(noContent())

    // when: 연락처를 삭제한다
    const result = await createContactsHttp().remove(9)

    // then: DELETE 요청을 보내고 값 없이 끝난다
    expect(result).toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/api/v1/contacts/9' })
  })

  // 참조 중 삭제 409는 서버 문구를 그대로 오류 메시지로 쓴다
  // 테스트 코드: CT-107
  it('remove shows the server message when Deals still use the contact', async () => {
    // given: 409 invalid-state 응답을 돌려주는 fetch
    stubFetch(problem(409, 'invalid-state', '연결된 Deal이 2건 있어 삭제할 수 없습니다.'))

    // when·then: 연락처를 삭제한다 → conflict 오류이고 메시지가 서버 문구다
    await expect(createContactsHttp().remove(9)).rejects.toMatchObject({
      kind: 'conflict',
      message: '연결된 Deal이 2건 있어 삭제할 수 없습니다.',
    })
  })
})
