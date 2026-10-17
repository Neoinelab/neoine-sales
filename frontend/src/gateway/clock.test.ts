import { afterEach, describe, expect, it, vi } from 'vitest'
/** 앱 시계 계약(`Clock`)과 같은 모양. 타입이 생기기 전에도 컴파일되도록 로컬로 둔다. */
interface Clock {
  now(): string
}

afterEach(() => vi.useRealTimers())

async function loadSystemClock(): Promise<Clock> {
  const mod = await vi.importActual<{ systemClock: Clock }>('./clock')
  return mod.systemClock
}

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

describe('systemClock (P8 T3)', () => {
  it('system clock reports the local calendar date with its offset', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 9, 17, 23, 30, 0)) // 로컬 시각 2026-10-17 23:30
    const clock = await loadSystemClock()

    const now = clock.now()
    const local = new Date()
    expect(now.slice(0, 10)).toBe(`${local.getFullYear()}-${pad(local.getMonth() + 1)}-${pad(local.getDate())}`)
    expect(now.slice(0, 10)).toBe('2026-10-17')
    expect(now.slice(11, 19)).toBe('23:30:00')

    const offsetMinutes = -local.getTimezoneOffset()
    const sign = offsetMinutes >= 0 ? '+' : '-'
    const abs = Math.abs(offsetMinutes)
    expect(now.endsWith(`${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`)).toBe(true)
  })
})
