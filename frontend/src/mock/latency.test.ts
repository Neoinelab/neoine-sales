import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createClock } from './clock'
import { createLatency } from './latency'

describe('latency', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('사용 불가(테스트)면 표시만 토글되고 실제 지연은 항상 0ms다', async () => {
    const latency = createLatency(false)
    expect(latency.isOn()).toBe(true)
    latency.setOn(false)
    expect(latency.isOn()).toBe(false)
    latency.setOn(true)
    await expect(latency.run('write', () => 1)).resolves.toBe(1)
  })

  it('켜져 있으면 읽기 150~300ms, 쓰기 300~600ms 뒤에 결과가 나오고 끄면 즉시다', async () => {
    const latency = createLatency(true, () => 0)
    let done = false
    void latency.run('read', () => 'x').then(() => (done = true))
    await vi.advanceTimersByTimeAsync(149)
    expect(done).toBe(false)
    await vi.advanceTimersByTimeAsync(1)
    expect(done).toBe(true)

    done = false
    void latency.run('write', () => 'y').then(() => (done = true))
    await vi.advanceTimersByTimeAsync(299)
    expect(done).toBe(false)
    await vi.advanceTimersByTimeAsync(1)
    expect(done).toBe(true)

    latency.setOn(false)
    await expect(latency.run('write', () => 'z')).resolves.toBe('z')
  })

  it('실패도 같은 지연 뒤에 reject하고, 실행(상태 변경)은 즉시 일어난다', async () => {
    const latency = createLatency(true, () => 0)
    let ran = false
    const failing = latency.run('read', () => {
      ran = true
      throw new Error('boom')
    })
    const caught = failing.catch((e: Error) => e.message)
    expect(ran).toBe(true)
    await vi.advanceTimersByTimeAsync(150)
    await expect(caught).resolves.toBe('boom')
  })
})

describe('clock', () => {
  it('고정 시각은 흐르지 않고 advance로만 움직이며 null이면 실제 시각이다', () => {
    const clock = createClock('2026-10-15T23:30:00+09:00')
    expect(clock.today()).toBe('2026-10-15')
    clock.advance(30 * 60_000)
    expect(clock.now()).toBe('2026-10-16T00:00:00+09:00')
    expect(clock.today()).toBe('2026-10-16')
    clock.setNow(null)
    expect(clock.isFixed()).toBe(false)
    expect(clock.now()).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$/)
  })
})
