import { describe, expect, it } from 'vitest'
import { createServerClock } from './clock'
import type { ServerTime } from './types'

/**
 * 서버 동기 시계(시간 기준 서버 통일 AC3·AC4). 브라우저 시계는 경과 시간 측정에만 쓰고,
 * 지금과 오프셋은 서버가 알려 준 값을 따른다. 테스트는 브라우저 ms 공급 함수를 주입해 시간을 직접 움직인다.
 */

const SERVER = (now: string, today = now.slice(0, 10)): ServerTime => ({ now, today })

/** 브라우저 시계를 손으로 움직이는 도구. */
function browser(start: number) {
  const state = { ms: start }
  return { read: () => state.ms, set: (ms: number) => void (state.ms = ms) }
}

describe('createServerClock', () => {
  it('syncs to the server time at the round-trip midpoint', async () => {
    const b = browser(1000)
    const clock = createServerClock(b.read)

    await clock.syncWith(async () => {
      b.set(3000) // 요청 1000ms → 응답 3000ms, 서버 now는 중간(2000ms)의 값
      return SERVER('2026-12-31T23:59:00+09:00')
    })

    expect(clock.now()).toBe('2026-12-31T23:59:01+09:00') // 응답 시점(3000ms)은 중간에서 1초 뒤
  })

  it('returns the server time it received', async () => {
    const clock = createServerClock(browser(0).read)
    const received = SERVER('2026-10-23T09:30:00+09:00')

    await expect(clock.syncWith(async () => received)).resolves.toEqual(received)
  })

  it('keeps the server offset even when the browser zone differs', async () => {
    const clock = createServerClock(browser(5000).read)

    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00-05:00'))

    expect(clock.now()).toBe('2026-10-23T09:00:00-05:00')
    expect(clock.now().endsWith('-05:00')).toBe(true)
  })

  it('treats Z as a zero offset', async () => {
    const clock = createServerClock(browser(0).read)

    await clock.syncWith(async () => SERVER('2026-10-23T00:30:00Z'))

    expect(Date.parse(clock.now())).toBe(Date.parse('2026-10-23T00:30:00Z'))
    expect(clock.now()).toMatch(/^2026-10-23T00:30:00(?:\+00:00|Z)$/)
  })

  it('accepts the microsecond fraction the server sends', async () => {
    const clock = createServerClock(browser(0).read)

    await clock.syncWith(async () => SERVER('2026-10-23T09:30:00.123456+09:00'))

    expect(clock.now().startsWith('2026-10-23T09:30:00')).toBe(true)
    expect(clock.now().endsWith('+09:00')).toBe(true)
  })

  it('rolls over the date as browser time passes without resync', async () => {
    const b = browser(1000)
    const clock = createServerClock(b.read)
    await clock.syncWith(async () => {
      b.set(3000)
      return SERVER('2026-12-31T23:59:00+09:00')
    })

    b.set(3000 + 60_000)

    expect(clock.now()).toBe('2027-01-01T00:00:01+09:00')
  })

  it('follows the browser elapsed time, not the browser date', async () => {
    const b = browser(Date.UTC(2000, 0, 1)) // 브라우저 날짜가 서버와 완전히 달라도
    const clock = createServerClock(b.read)
    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00+09:00'))

    b.set(b.read() + 90_000)

    expect(clock.now()).toBe('2026-10-23T09:01:30+09:00')
  })

  it('replaces the skew on resync', async () => {
    const b = browser(0)
    const clock = createServerClock(b.read)
    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00+09:00'))
    b.set(600_000)

    await clock.syncWith(async () => SERVER('2026-10-23T09:12:00+09:00')) // 서버는 브라우저보다 2분 앞서 있었다

    expect(clock.now()).toBe('2026-10-23T09:12:00+09:00')
  })

  it('takes the offset of the latest sync', async () => {
    const clock = createServerClock(browser(0).read)
    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00+09:00'))

    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00-04:00'))

    expect(clock.now().endsWith('-04:00')).toBe(true)
  })

  it('keeps the previous sync when fetch fails', async () => {
    const b = browser(0)
    const clock = createServerClock(b.read)
    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00+09:00'))
    b.set(10_000)

    await expect(clock.syncWith(() => Promise.reject(new Error('network down')))).rejects.toThrow('network down')

    expect(clock.now()).toBe('2026-10-23T09:00:10+09:00')
  })

  it.each(['2026-10-23T09:00:00', 'not-a-date', '', '2026-10-23'])('rejects the server time %j without a usable offset', async (now) => {
    const clock = createServerClock(browser(0).read)

    await expect(clock.syncWith(async () => SERVER(now, '2026-10-23'))).rejects.toBeInstanceOf(RangeError)
  })

  it('keeps the previous sync when the server time has no offset', async () => {
    const b = browser(0)
    const clock = createServerClock(b.read)
    await clock.syncWith(async () => SERVER('2026-10-23T09:00:00+09:00'))
    b.set(5000)

    await expect(clock.syncWith(async () => SERVER('2026-10-23T12:00:00'))).rejects.toBeInstanceOf(RangeError)

    expect(clock.now()).toBe('2026-10-23T09:00:05+09:00')
  })

  it('uses the browser clock only before the first sync', () => {
    const start = Date.UTC(2026, 9, 23, 3, 0, 0)
    const clock = createServerClock(() => start)

    const now = clock.now()

    expect(Date.parse(now)).toBe(start)
    expect(now).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)$/)
  })

  it('does not share state between clocks', async () => {
    const first = createServerClock(browser(0).read)
    const second = createServerClock(browser(0).read)

    await first.syncWith(async () => SERVER('2026-10-23T09:00:00+05:45'))

    expect(second.now().endsWith('+05:45')).toBe(false)
  })
})
