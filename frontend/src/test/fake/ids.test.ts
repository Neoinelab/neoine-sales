import { describe, expect, it } from 'vitest'
import { newMock, expectApiError, mockAs } from './testing'
import { USER_ID } from './seed/ids'
import { takeId } from './store'

/** Fake가 서버(BIGINT id)처럼 양의 안전 정수를 쓰고, 종류마다 1씩 커지는지 고정한다. */
describe('Fake 게이트웨이의 정수 id', () => {
  it('takeId는 종류마다 1부터 하나씩 늘려 준다', () => {
    // given: 빈 카운터
    const counters: Record<string, number> = {}

    // when: vd를 두 번, sl을 한 번 받으면 1, 2, 1이다
    const actual = [takeId(counters, 'vd'), takeId(counters, 'vd'), takeId(counters, 'sl')]
    // then: vd는 1, 2, sl은 1로 종류마다 따로 센다
    expect(actual).toEqual([1, 2, 1])
  })

  it('시드 사용자는 USER_ID의 고정 id를 그대로 쓴다', async () => {
    // given: root로 로그인한 게이트웨이
    const { gateway } = await mockAs('root')

    // when: 전체 사용자 목록을 읽는다
    const users = await gateway.users.list('all')

    // then: 로그인 아이디마다 USER_ID의 고정 id가 들어 있다
    expect(users.map((u) => [u.loginId, u.id])).toEqual(
      expect.arrayContaining(Object.entries(USER_ID).map(([loginId, id]) => [loginId, id])),
    )
  })

  it('새 Vendor는 시드 Vendor보다 큰 정수 id를 받는다', async () => {
    // given: 시드 Vendor 목록
    const { gateway } = await mockAs('root')
    const before = await gateway.vendors.list()

    // when: Vendor를 새로 만든다
    const created = await gateway.vendors.create('Brand New Vendor')

    // then: 안전한 정수이고 기존 id보다 크다
    expect(Number.isSafeInteger(created.id)).toBe(true)
    expect(created.id).toBeGreaterThan(Math.max(...before.map((v) => v.id)))
  })

  it('새 사용자는 시드 사용자 다음 정수 id를 받는다', async () => {
    // given: root로 로그인한 게이트웨이
    const { gateway } = await mockAs('root')

    // when: 사용자를 새로 만든다
    const created = await gateway.users.create({ loginId: 'newbie', name: '신입', role: 'sales' })

    // then: 시드 사용자 수 + 1이다
    expect(created.id).toBe(Object.keys(USER_ID).length + 1)
  })

  it('새 연락처와 새 Action 유형은 양의 정수 id를 받는다', async () => {
    // given: root로 로그인한 게이트웨이
    const { gateway } = await mockAs('root')

    // when: Action 유형과 연락처를 새로 만든다
    const type = await gateway.actionTypes.create('웨비나')
    const contact = await gateway.contacts.create('customer', { company: '신규상사', name: '김신규', title: '', email: null, phone: null })

    // then: 둘 다 양의 안전 정수 id이다
    expect(Number.isSafeInteger(type.id) && type.id > 0).toBe(true)
    expect(Number.isSafeInteger(contact.id) && contact.id > 0).toBe(true)
  })

  it('sessionStorage에 문자열로 남은 세션은 숫자 사용자 id로 복원된다', async () => {
    // given: 김영업 id를 문자열로 저장한 sessionStorage
    window.sessionStorage.setItem('neoine-mock-user-id', String(USER_ID.kim))

    // when: 세션 유지 옵션으로 Fake를 만든다
    const mock = newMock({ persistSession: true })

    // then: 현재 사용자 id가 숫자 김영업 id이다
    expect((await mock.gateway.auth.me()).id).toBe(USER_ID.kim)
  })

  it('어느 행에도 없는 id는 타입 오류가 아니라 404이다', async () => {
    // given: root로 로그인한 게이트웨이
    const { gateway } = await mockAs('root')

    // when·then: 없는 id의 Vendor를 삭제하면 404이다
    await expectApiError(gateway.vendors.remove(Number.MAX_SAFE_INTEGER), 404)
  })
})
