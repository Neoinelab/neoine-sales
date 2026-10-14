import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import { ME_SALES, userRef } from './authFixtures'

export interface RecordedRequest {
  method: string
  path: string
  query: URLSearchParams
  body: unknown
  headers: Headers
}

type Reply = { status?: number; body?: unknown }
type Handler = Reply | ((request: RecordedRequest) => Reply)

/** "GET /api/v1/auth/me" 같은 키로 응답을 정하는 가짜 fetch. 정하지 않은 요청은 404. */
export function mockApi(routes: Record<string, Handler>) {
  // 화면은 로그인한 사용자의 역할(me)로 쓰기 UI를 정한다. 정하지 않은 테스트는 sales(쓰기 가능)로 본다.
  // 사용자 선택 목록(user-options)도 기본 제공한다: 김영업(me)과 박영업.
  const userOptions = { items: [userRef('u-2', '김영업'), userRef('u-3', '박영업')], offset: 0, limit: 200 }
  const withDefaults: Record<string, Handler> = {
    'GET /api/v1/auth/me': { body: ME_SALES },
    'GET /api/v1/user-options': { body: userOptions },
    ...routes,
  }
  const requests: RecordedRequest[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: Request) => {
      const url = new URL(input.url)
      const text = await input.clone().text()
      const recorded: RecordedRequest = {
        method: input.method,
        path: url.pathname,
        query: url.searchParams,
        body: text ? JSON.parse(text) : undefined,
        headers: input.headers,
      }
      requests.push(recorded)
      const handler = withDefaults[`${input.method} ${url.pathname}`]
      const reply = typeof handler === 'function' ? handler(recorded) : (handler ?? { status: 404 })
      const status = reply.status ?? 200
      const hasBody = reply.body !== undefined && status !== 204
      return new Response(hasBody ? JSON.stringify(reply.body) : null, {
        status,
        headers: hasBody ? { 'content-type': status >= 400 ? 'application/problem+json' : 'application/json' } : {},
      })
    }),
  )
  return requests
}

export function renderApp(ui: ReactElement, route = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

export function problem(status: number, kind: string, detail: string, extra: Record<string, unknown> = {}) {
  return {
    status,
    body: { type: `https://neoine-sales.example/problems/${kind}`, title: kind, status, detail, instance: '/x', ...extra },
  }
}

/** 사용자(me) 응답이 화면에 반영될 시간을 준다. "버튼이 없다"를 확인하기 전에, 로딩 중이라 없는 것이 아님을 보장한다. */
export async function settled() {
  await new Promise((resolve) => setTimeout(resolve, 60))
}
