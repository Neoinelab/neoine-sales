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

describe('app gateway module', () => {
  // 앱 gateway는 HTTP gateway다(서버가 꺼져 있으면 네트워크 오류).
  it('app gateway is the http gateway', async () => {
    // given: 네트워크가 끊긴 fetch
    const fetchSpy = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', fetchSpy)
    const { gateway } = await loadAppGateway()

    // when·then: Forecast 요약도 실제 서버를 부른다 — 서버가 꺼져 있으면 501이 아니라 네트워크 오류(status 0)다
    await expect(gateway.forecast.summary({ year: 2026 })).rejects.toMatchObject({ status: 0 })
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  // 앱 gateway는 내 정보 호출도 HTTP로 노출한다.
  it('app gateway exposes the my-account calls over HTTP (내 정보)', async () => {
    // given: 네트워크가 끊긴 fetch
    const fetchSpy = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', fetchSpy)
    const { gateway } = await loadAppGateway()

    // when·then: 내 정보·인증 방식 선택 호출이 네트워크 오류로 실패한다
    await expect(gateway.me.profile()).rejects.toMatchObject({ status: 0 })
    await expect(gateway.setup.chooseAuthMode('local')).rejects.toMatchObject({ status: 0 })

    expect(fetchSpy).toHaveBeenCalledTimes(2)
  })

  // 첫 동기 전 앱 시계는 브라우저 시각이다.
  // 테스트 코드: TM-028
  it('app clock is the server clock that falls back to the browser clock before the first sync', async () => {
    // given: 동기하지 않은 앱 gateway의 시계
    const { clock } = await loadAppGateway()

    // when: now()를 읽는다
    const now = clock.now()
    // then: syncWith를 가지며 브라우저 시각과 같은 오프셋 ISO 문자열이다
    expect(typeof clock.syncWith).toBe('function')
    expect(now).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)$/)
    expect(Math.abs(Date.parse(now) - Date.now())).toBeLessThan(1000)
  })

  // 앱 gateway로 동기하면 앱 시계가 서버 시각과 오프셋을 따른다.
  // 테스트 코드: TM-029
  it('app clock follows the server time after a sync through the app gateway', async () => {
    // given: 서버가 +02:00 시각을 주는 앱 gateway
    const body = { now: '2031-05-06T07:08:09+02:00', today: '2031-05-06' }
    const fetchSpy = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchSpy)
    const { gateway, clock } = await loadAppGateway()

    // when: 앱 gateway의 time.get으로 동기한다
    await clock.syncWith(() => gateway.time.get())

    // then: /time을 한 번 부르고 앱 시계가 그 시각과 오프셋을 따른다
    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(clock.now().startsWith('2031-05-06T07:08:')).toBe(true)
    expect(clock.now().endsWith('+02:00')).toBe(true)
  })
})
