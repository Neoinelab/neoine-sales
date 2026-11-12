import { describe, expect, it } from 'vitest'
import { expectApiError, mockAs } from '../testing'

describe('time.get (Fake 서버 시각)', () => {
  // Fake는 세 역할에 시계의 now와 그 날짜를 같은 모양으로 준다.
  // 테스트 코드: TM-029
  it.each(['root', 'kim', 'han'] as const)('answers the clock now and its calendar date to %s', async (key) => {
    // given: 시계가 2026-12-31T23:30+09:00이다
    const mock = await mockAs(key)
    mock.clock.setNow('2026-12-31T23:30:00+09:00')

    // when·then: now와 today(now[:10])를 준다
    expect(await mock.gateway.time.get()).toEqual({ now: '2026-12-31T23:30:00+09:00', today: '2026-12-31' })
  })

  // 시계가 흐르면 서버 시각도 따라간다.
  it('follows the clock when it advances', async () => {
    // given: 시계가 23:59:30이고 60초 흐른다
    const mock = await mockAs('kim')
    mock.clock.setNow('2026-12-31T23:59:30+09:00')
    mock.clock.advance(60_000)

    // when·then: 새해 00:00:30을 준다
    expect(await mock.gateway.time.get()).toEqual({ now: '2027-01-01T00:00:30+09:00', today: '2027-01-01' })
  })

  // 세션이 없으면 401이다.
  it('answers 401 without a session', async () => {
    // given: 로그인하지 않았다
    const { gateway } = await mockAs(null)

    // when·then: 서버 시각 요청은 401
    await expectApiError(gateway.time.get(), 401)
  })
})

describe('fake clock syncWith', () => {
  // Fake 시계의 동기는 받은 서버 시각을 그대로 돌려주고 시계는 건드리지 않는다.
  it('returns the fetched server time unchanged and leaves the clock alone', async () => {
    // given: Fake 시계가 2026-10-23T09:00이다
    const mock = await mockAs('kim')
    mock.clock.setNow('2026-10-23T09:00:00+09:00')

    // when: 다른 서버 시각으로 동기한다
    const synced = await mock.clock.syncWith(async () => ({ now: '2030-01-01T00:00:00+09:00', today: '2030-01-01' }))

    // then: 받은 값을 그대로 돌려주고 시계는 그대로다
    expect(synced).toEqual({ now: '2030-01-01T00:00:00+09:00', today: '2030-01-01' })
    expect(mock.clock.now()).toBe('2026-10-23T09:00:00+09:00')
  })

  // 동기 요청이 실패하면 그 오류로 reject된다.
  it('rejects with the fetch error', async () => {
    // given: Fake 시계
    const mock = await mockAs('kim')

    // when·then: 실패한 fetch의 오류로 reject
    await expect(mock.clock.syncWith(() => Promise.reject(new Error('down')))).rejects.toThrow('down')
  })
})
