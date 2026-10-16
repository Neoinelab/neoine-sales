/** 어떤 게이트웨이를 쓸지 정하는 스위치. `VITE_GATEWAY=http`일 때만 실제 서버, 그 밖에는 mock(기본). */

export type GatewayMode = 'mock' | 'http'

/** 호출 시점에 읽는다(테스트가 `vi.stubEnv`로 바꿀 수 있게). */
export function gatewayMode(): GatewayMode {
  return import.meta.env.VITE_GATEWAY === 'http' ? 'http' : 'mock'
}
