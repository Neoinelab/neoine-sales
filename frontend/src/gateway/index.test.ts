import { afterEach, describe, expect, it, vi } from 'vitest'

/** 앱이 실제로 쓰는 gateway/index 모듈(테스트 setup이 주입한 Fake가 아니라 원본). */
interface Clock {
  now(): string
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
    const fetchSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)
    const { gateway } = await loadAppGateway()

    // http 게이트웨이에서 Forecast 집계만 아직 서버가 없어 501이다. mock이면 집계가 돌아온다.
    await expect(gateway.forecast.summary({ year: 2026 })).rejects.toMatchObject({ status: 501, kind: 'not-implemented' })
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('app clock is the system clock', async () => {
    const { clock } = await loadAppGateway()

    const now = clock.now()
    expect(now).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)$/)
    expect(Math.abs(Date.parse(now) - Date.now())).toBeLessThan(1000)
  })
})
