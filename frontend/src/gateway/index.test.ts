import { afterEach, describe, expect, it, vi } from 'vitest'

/** 앱이 실제로 쓰는 gateway/index 모듈(테스트 setup이 주입한 Fake가 아니라 원본). */
interface Clock {
  now(): string
  syncWith(fetch: () => Promise<{ now: string; today: string }>): Promise<{ now: string; today: string }>
}

interface AppGatewayModule {
  gateway: import('./types').Gateway
  clock: Clock
}

async function loadAppGateway(): Promise<AppGatewayModule> {
  return vi.importActual<AppGatewayModule>('./index')
}

afterEach(() => vi.unstubAllGlobals())

describe('app gateway module (P8 T2)', () => {
  it('app gateway is the http gateway', async () => {
    const fetchSpy = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', fetchSpy)
    const { gateway } = await loadAppGateway()

    // Forecast 요약도 실제 서버를 부른다(P6): 서버가 꺼져 있으면 501이 아니라 네트워크 오류(status 0)다.
    await expect(gateway.forecast.summary({ year: 2026 })).rejects.toMatchObject({ status: 0 })
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('app clock is the server clock that falls back to the browser clock before the first sync', async () => {
    const { clock } = await loadAppGateway()

    const now = clock.now()
    expect(typeof clock.syncWith).toBe('function')
    expect(now).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)$/)
    expect(Math.abs(Date.parse(now) - Date.now())).toBeLessThan(1000)
  })

  it('app clock follows the server time after a sync through the app gateway', async () => {
    const body = { now: '2031-05-06T07:08:09+02:00', today: '2031-05-06' }
    const fetchSpy = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchSpy)
    const { gateway, clock } = await loadAppGateway()

    await clock.syncWith(() => gateway.time.get())

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(clock.now().startsWith('2031-05-06T07:08:')).toBe(true)
    expect(clock.now().endsWith('+02:00')).toBe(true)
  })
})
