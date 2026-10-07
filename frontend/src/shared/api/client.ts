import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export type Schemas = components['schemas']

// fetch는 호출 시점에 찾는다(테스트에서 globalThis.fetch를 바꿔 끼울 수 있게).
export const api = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: 'include',
  // 쿠키 인증의 CSRF 방어: 다른 출처는 CORS 허용 없이 이 헤더를 보낼 수 없다.
  headers: { 'X-Requested-With': 'neoine-web' },
  fetch: (request) => globalThis.fetch(request),
})
