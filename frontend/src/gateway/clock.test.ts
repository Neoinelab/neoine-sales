import { describe, expect, it } from 'vitest'
import { createServerClock } from './clock'
import type { ServerTime } from './types'

/**
 * 서버 동기 시계. 브라우저 시계는 경과 시간 측정에만 쓰고,
 * 지금과 오프셋은 서버가 알려 준 값을 따른다. 테스트는 브라우저 ms 공급 함수를 주입해 시간을 직접 움직인다.
 */

const SERVER = (now: string, today = now.slice(0, 10)): ServerTime => ({ now, today })

/** 브라우저 시계를 손으로 움직이는 도구. */
function browser(start: number) {
  const state = { ms: start }
  return { read: () => state.ms, set: (ms: number) => void (state.ms = ms) }
}

describe('createServerClock', () => {
  // 앱 시계는 왕복 지연의 절반을 보정해 서버 시각에 맞춘다.
  // 테스트 코드: TM-022
  it('syncs to the server time at the round-trip midpoint', async () => {
    // given: 브라우저 시각 1000ms
    const b = browser(1000)
    const clock = createServerClock(b.read)

    // when: 요청 1000ms → 응답 3000ms, 서버 now는 중간(2000ms)의 값으로 동기한다
    await clock.syncWith(async () => {
      b.set(3000)
      return SERVER('2026-12-31T23:59:00+09:00')
    })

    // then: 응답 시점(3000ms)은 중간에서 1초 뒤다
    expect(clock.now()).toBe('2026-12-31T23:59:01+09:00')
  })

  // 동기는 받은 서버 시각을 그대로 돌려준다.
  // 테스트 코드: TM-022
  it('returns the server time it received', async () => {
    // given: 서버가 줄 시각
    const clock = createServerClock(browser(0).read)
    const received = SERVER('2026-10-23T09:30:00+09:00')

    // when·then: 동기하면 받은 값을 그대로 돌려준다
    await expect(clock.syncWith(async () => received)).resolves.toEqual(received)
  })

  // 브라우저 시간대가 달라도 서버 오프셋을 유지한다.
  // 테스트 코드: TM-023
  it('keeps the server offset even when the browser zone differs', async () => {
    // given: 브라우저 시각 5000ms
    const clock = createServerClock(browser(5000).read)

    // when: 서버 now가 -05:00으로 동기한다
    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00-05:00'))

    // then: now()는 -05:00으로 끝난다
    expect(clock.now()).toBe('2026-10-23T09:00:00-05:00')
    expect(clock.now().endsWith('-05:00')).toBe(true)
  })

  // 서버 now의 Z는 오프셋 0으로 읽는다.
  // 테스트 코드: TM-024
  it('treats Z as a zero offset', async () => {
    // given: 앱 시계
    const clock = createServerClock(browser(0).read)

    // when: 서버 now가 Z 표기로 동기한다
    await clock.syncWith(async () => SERVER('2026-10-23T00:30:00Z'))

    // then: 순간이 같고 오프셋은 0이다
    expect(Date.parse(clock.now())).toBe(Date.parse('2026-10-23T00:30:00Z'))
    expect(clock.now()).toMatch(/^2026-10-23T00:30:00(?:\+00:00|Z)$/)
  })

  // 서버가 보내는 마이크로초 소수 초를 읽는다.
  // 테스트 코드: TM-024
  it('accepts the microsecond fraction the server sends', async () => {
    // given: 앱 시계
    const clock = createServerClock(browser(0).read)

    // when: 마이크로초가 있는 서버 now로 동기한다
    await clock.syncWith(async () => SERVER('2026-10-23T09:30:00.123456+09:00'))

    // then: now()는 09:30:00으로 시작하고 +09:00으로 끝난다
    expect(clock.now().startsWith('2026-10-23T09:30:00')).toBe(true)
    expect(clock.now().endsWith('+09:00')).toBe(true)
  })

  // 동기 사이 자정을 지나면 앱 시계 날짜가 바뀐다.
  // 테스트 코드: TM-025
  it('rolls over the date as browser time passes without resync', async () => {
    // given: 서버 now 2026-12-31T23:59:00+09:00으로 동기(응답 시점 23:59:01)
    const b = browser(1000)
    const clock = createServerClock(b.read)
    await clock.syncWith(async () => {
      b.set(3000)
      return SERVER('2026-12-31T23:59:00+09:00')
    })

    // when: 다시 동기하지 않고 브라우저 시각이 60초 흐른다
    b.set(3000 + 60_000)

    // then: 새해 00:00:01이다
    expect(clock.now()).toBe('2027-01-01T00:00:01+09:00')
  })

  // 앱 시계는 브라우저 날짜가 아니라 경과 시간만 따른다.
  // 테스트 코드: TM-023
  it('follows the browser elapsed time, not the browser date', async () => {
    // given: 브라우저 날짜가 서버와 완전히 다른(2000-01-01) 상태에서 동기
    const b = browser(Date.UTC(2000, 0, 1))
    const clock = createServerClock(b.read)
    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00+09:00'))

    // when: 브라우저 시각이 90초 흐른다
    b.set(b.read() + 90_000)

    // then: 서버 기준 09:01:30이다
    expect(clock.now()).toBe('2026-10-23T09:01:30+09:00')
  })

  // 다시 동기하면 보정값이 새 값으로 바뀐다.
  // 테스트 코드: TM-026
  it('replaces the skew on resync', async () => {
    // given: 동기된 뒤 브라우저 시각이 600초 흘렀다
    const b = browser(0)
    const clock = createServerClock(b.read)
    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00+09:00'))
    b.set(600_000)

    // when: 서버 now 09:12로 다시 동기한다(서버는 브라우저보다 2분 앞서 있었다)
    await clock.syncWith(async () => SERVER('2026-10-23T09:12:00+09:00'))

    // then: now()는 09:12:00이다
    expect(clock.now()).toBe('2026-10-23T09:12:00+09:00')
  })

  // 다시 동기하면 오프셋도 새 값으로 바뀐다.
  // 테스트 코드: TM-026
  it('takes the offset of the latest sync', async () => {
    // given: +09:00으로 동기된 시계
    const clock = createServerClock(browser(0).read)
    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00+09:00'))

    // when: -04:00으로 다시 동기한다
    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00-04:00'))

    // then: now()는 -04:00으로 끝난다
    expect(clock.now().endsWith('-04:00')).toBe(true)
  })

  // 동기 요청이 실패하면 직전 동기가 유지된다.
  // 테스트 코드: TM-027
  it('keeps the previous sync when fetch fails', async () => {
    // given: 동기된 뒤 브라우저 시각이 흘렀다
    const b = browser(0)
    const clock = createServerClock(b.read)
    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00+09:00'))
    b.set(10_000)

    // when: 동기 요청이 네트워크 오류로 실패한다
    await expect(clock.syncWith(() => Promise.reject(new Error('network down')))).rejects.toThrow('network down')

    // then: 직전 동기 기준 시각이다
    expect(clock.now()).toBe('2026-10-23T09:00:10+09:00')
  })

  // 오프셋이 없거나 읽을 수 없는 서버 now는 RangeError로 거절한다.
  // 테스트 코드: TM-027
  it.each(['2026-10-23T09:00:00', 'not-a-date', '', '2026-10-23'])('rejects the server time %j without a usable offset', async (now) => {
    // given: 앱 시계
    const clock = createServerClock(browser(0).read)

    // when·then: 사용할 수 없는 서버 now로 동기하면 RangeError
    await expect(clock.syncWith(async () => SERVER(now, '2026-10-23'))).rejects.toBeInstanceOf(RangeError)
  })

  // 서버 now에 오프셋이 없어도 직전 동기가 유지된다.
  // 테스트 코드: TM-027
  it('keeps the previous sync when the server time has no offset', async () => {
    // given: 동기된 뒤 브라우저 시각이 5초 흘렀다
    const b = browser(0)
    const clock = createServerClock(b.read)
    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00+09:00'))
    b.set(5000)

    // when: 오프셋 없는 서버 now로 동기한다
    await expect(clock.syncWith(async () => SERVER('2026-10-23T12:00:00'))).rejects.toBeInstanceOf(RangeError)

    // then: 직전 동기 기준 시각이다
    expect(clock.now()).toBe('2026-10-23T09:00:05+09:00')
  })

  // 첫 동기 전에는 브라우저 시각을 쓴다.
  // 테스트 코드: TM-028
  it('uses the browser clock only before the first sync', () => {
    // given: 동기하지 않은 앱 시계
    const start = Date.UTC(2026, 9, 23, 3, 0, 0)
    const clock = createServerClock(() => start)

    // when: now()를 읽는다
    const now = clock.now()

    // then: 브라우저 시각과 같은 순간의 오프셋 ISO 문자열이다
    expect(Date.parse(now)).toBe(start)
    expect(now).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)$/)
  })

  // 시계 인스턴스끼리 상태를 나누지 않는다.
  // 테스트 코드: TM-023
  it('does not share state between clocks', async () => {
    // given: 시계 두 개
    const first = createServerClock(browser(0).read)
    const second = createServerClock(browser(0).read)

    // when: 첫 시계만 +05:45로 동기한다
    await first.syncWith(async () => SERVER('2026-10-23T09:00:00+05:45'))

    // then: 둘째 시계의 오프셋은 바뀌지 않는다
    expect(second.now().endsWith('+05:45')).toBe(false)
  })
})
