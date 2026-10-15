import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router'
import { App } from '../App'
import { gateway, mockControl } from '../gateway'
import { defaultMock } from '../mock/default'
import { emptyBusinessSeed } from '../mock/seed'
import { buildSampleSeed } from './fixtures/sampleSeed'

/** 테스트에서 고를 수 있는 역할. null은 로그인하지 않은 상태. */
export type TestRole = 'admin' | 'sales' | 'user' | null

/** 역할별 시드 사용자 id(시드 약속: `u-<loginId>`). */
const ROLE_USER_ID = { admin: 'u-root', sales: 'u-kim', user: 'u-han' } as const

export interface RenderAtOptions {
  /** 기본 'sales'(김영업). null이면 로그인하지 않는다. */
  role?: TestRole
  /** role 대신 시드 사용자 id를 직접 지정한다(예: 'u-park'). */
  userId?: string
  /** 'sample'(기본)은 테스트 픽스처 시드, 'empty'는 앱 기본(업무 데이터 없음) 시드. */
  seed?: 'sample' | 'empty'
}

function LocationProbe() {
  const location = useLocation()
  // <output>은 status 역할이라 화면의 알림(role=status) 질의와 겹치므로 쓰지 않는다.
  return <span data-testid="location">{location.pathname + location.search}</span>
}

/**
 * 화면 테스트 공통 진입점.
 * - 시드 데이터로 초기화(지연 0ms는 테스트 모드에서 게이트웨이가 보장), 저장소 장애 끔
 * - 역할(또는 사용자 id)로 로그인한 상태에서 `url`부터 `<App />`을 렌더
 * - `location()`은 현재 경로(+쿼리)를 돌려준다(리다이렉트 검증용)
 */
export async function renderAt(url: string, options: RenderAtOptions = {}) {
  defaultMock.setSeed(options.seed === 'empty' ? emptyBusinessSeed : buildSampleSeed)
  mockControl.resetData() // 일부 테스트는 resetData를 감싸 최초 설정 상태를 만든다
  mockControl.setStorageFailure(false)
  const role = options.role === undefined ? 'sales' : options.role
  const userId = options.userId ?? (role ? ROLE_USER_ID[role] : null)
  if (userId) await gateway.auth.quickLogin(userId)
  else await gateway.auth.logout()

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <LocationProbe />
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  const user = userEvent.setup()
  const location = () => result.getByTestId('location').textContent ?? ''
  return { ...result, client, user, location }
}
