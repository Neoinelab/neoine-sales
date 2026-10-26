import { describe, expect, it } from 'vitest'
import { expectApiError, mockAs } from '../testing'

describe('time.get (Fake 서버 시각)', () => {
  it.each(['root', 'kim', 'han'] as const)('answers the clock now and its calendar date to %s', async (key) => {
    const mock = await mockAs(key)
    mock.clock.setNow('2026-12-31T23:30:00+09:00')

    expect(await mock.gateway.time.get()).toEqual({ now: '2026-12-31T23:30:00+09:00', today: '2026-12-31' })
  })

  it('follows the clock when it advances', async () => {
    const mock = await mockAs('kim')
    mock.clock.setNow('2026-12-31T23:59:30+09:00')
    mock.clock.advance(60_000)

    expect(await mock.gateway.time.get()).toEqual({ now: '2027-01-01T00:00:30+09:00', today: '2027-01-01' })
  })

  it('answers 401 without a session', async () => {
    const { gateway } = await mockAs(null)

    await expectApiError(gateway.time.get(), 401)
  })
})

describe('fake clock syncWith', () => {
  it('returns the fetched server time unchanged and leaves the clock alone', async () => {
    const mock = await mockAs('kim')
    mock.clock.setNow('2026-10-23T09:00:00+09:00')

    const synced = await mock.clock.syncWith(async () => ({ now: '2030-01-01T00:00:00+09:00', today: '2030-01-01' }))

    expect(synced).toEqual({ now: '2030-01-01T00:00:00+09:00', today: '2030-01-01' })
    expect(mock.clock.now()).toBe('2026-10-23T09:00:00+09:00')
  })

  it('rejects with the fetch error', async () => {
    const mock = await mockAs('kim')

    await expect(mock.clock.syncWith(() => Promise.reject(new Error('down')))).rejects.toThrow('down')
  })
})
