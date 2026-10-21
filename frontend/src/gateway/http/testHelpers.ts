/** HTTP 어댑터 테스트 도우미: `fetch`를 고정 응답으로 바꿔 끼우고 보낸 요청을 기록한다(MSW 없음). */

import { vi } from 'vitest'

export interface Captured {
  method: string
  /** 경로 + 쿼리 문자열. */
  path: string
  headers: Headers
  credentials: RequestCredentials
  /** JSON 본문(없으면 undefined). */
  body: unknown
}

const PROBLEM_BASE = 'https://neoine-sales.example/problems/'

/** 200(또는 지정 상태)의 JSON 응답. */
export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } })
}

/** 본문 없는 204. */
export function noContent(): Response {
  return new Response(null, { status: 204 })
}

/** 서버 형식의 problem+json 응답. kind는 서버 표기(`already-exists` 등). */
export function problem(status: number, kind: string, detail: string, extra: Record<string, unknown> = {}): Response {
  const body = { type: `${PROBLEM_BASE}${kind}`, title: kind, status, detail, instance: '/x', ...extra }
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/problem+json' } })
}

/** 서버가 준 응답을 순서대로 돌려주는 가짜 fetch. 호출은 `calls`에 쌓인다. */
export function stubFetch(...replies: Response[]): { calls: Captured[] } {
  const calls: Captured[] = []
  const queue = [...replies]
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url)
      const text = await request.clone().text()
      calls.push({
        method: request.method,
        path: url.pathname + url.search,
        headers: request.headers,
        credentials: request.credentials,
        body: text === '' ? undefined : (JSON.parse(text) as unknown),
      })
      const next = queue.shift()
      if (!next) throw new Error('예상하지 못한 추가 요청')
      return next
    }),
  )
  return { calls }
}

/** 네트워크 자체가 실패하는 fetch(서버 꺼짐). */
export function stubNetworkDown(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }),
  )
}

/** 서버 UserRef 응답 조각. */
export function userRefBody(id: number, name: string, resigned = false, role: 'admin' | 'sales' | 'user' = 'user') {
  return { id, name, label: resigned ? `${name}(퇴사)` : name, resigned, role }
}
