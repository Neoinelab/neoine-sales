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
    const fetchSpy = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', fetchSpy)
    const { gateway } = await loadAppGateway()

    // Forecast 요약도 실제 서버를 부른다(P6): 서버가 꺼져 있으면 501이 아니라 네트워크 오류(status 0)다.
    await expect(gateway.forecast.summary({ year: 2026 })).rejects.toMatchObject({ status: 0 })
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('app clock is the system clock', async () => {
    const { clock } = await loadAppGateway()

    const now = clock.now()
    expect(now).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)$/)
    expect(Math.abs(Date.parse(now) - Date.now())).toBeLessThan(1000)
  })
})
