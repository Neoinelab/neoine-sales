import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { act } from 'react'
import { MemoryRouter, useLocation, useNavigate, type NavigateFunction } from 'react-router'
import { App } from '../App'
import { gateway } from '../gateway'
import { mockControl } from './fake/default'
import { defaultMock } from './fake/default'
import { emptyBusinessSeed } from './fake/seed'
import { buildLegacySolutionSeed } from './fixtures/legacySolution'
import { buildSampleSeed } from './fixtures/sampleSeed'
import { USER_ID } from './fake/seed/ids'

/** 테스트에서 고를 수 있는 역할. null은 로그인하지 않은 상태. */
export type TestRole = 'admin' | 'sales' | 'user' | null

/** 역할별 시드 사용자 id(시드 약속: `u-<loginId>`). */
const ROLE_USER_ID = { admin: USER_ID.root, sales: USER_ID.kim, user: USER_ID.han } as const

const SEEDS = { sample: buildSampleSeed, empty: emptyBusinessSeed, 'legacy-solution': buildLegacySolutionSeed }

export interface RenderAtOptions {
  /** 기본 'sales'(김영업). null이면 로그인하지 않는다. */
  role?: TestRole
  /** role 대신 시드 사용자 id를 직접 지정한다(예: USER_ID.park). */
  userId?: number
  /** 'sample'(기본)은 테스트 픽스처 시드, 'empty'는 앱 기본(업무 데이터 없음) 시드, 'legacy-solution'은 모든 Deal의 Solution이 빈 레거시 시드. */
  seed?: 'sample' | 'empty' | 'legacy-solution'
}

function LocationProbe() {
  const location = useLocation()
  // <output>은 status 역할이라 화면의 알림(role=status) 질의와 겹치므로 쓰지 않는다.
  return <span data-testid="location">{location.pathname + location.search}</span>
}

/** 화면에 링크가 없는 경로(예: 상세 → 수정 화면)로 가는 테스트용 이동 함수를 밖으로 꺼낸다. */
function NavigateProbe({ onReady }: { onReady: (navigate: NavigateFunction) => void }) {
  const navigate = useNavigate()
  onReady(navigate)
  return null
}

/**
 * 화면 테스트 공통 진입점.
 * - 시드 데이터로 초기화(지연 0ms는 테스트 모드에서 게이트웨이가 보장), 저장소 장애 끔
 * - 역할(또는 사용자 id)로 로그인한 상태에서 `url`부터 `<App />`을 렌더
 * - `location()`은 현재 경로(+쿼리)를 돌려준다(리다이렉트 검증용)
 * - `goTo(path)`는 화면에 링크가 없는 경로로 이동하고, 숫자(-1)면 브라우저 뒤로 가기와 같은 history 이동을 한다
 */
export async function renderAt(url: string, options: RenderAtOptions = {}) {
  defaultMock.setSeed(SEEDS[options.seed ?? 'sample'])
  mockControl.resetData() // 일부 테스트는 resetData를 감싸 최초 설정 상태를 만든다
  mockControl.setStorageFailure(false)
  const role = options.role === undefined ? 'sales' : options.role
  const userId = options.userId ?? (role ? ROLE_USER_ID[role] : null)
  if (userId) await gateway.auth.quickLogin(userId)
  else await gateway.auth.logout()

  const navigateRef: { current: NavigateFunction | null } = { current: null }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <LocationProbe />
        <NavigateProbe onReady={(navigate) => (navigateRef.current = navigate)} />
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  const user = userEvent.setup()
  const location = () => result.getByTestId('location').textContent ?? ''
  const goTo = (path: string | number) => {
    act(() => {
      // NavigateFunction은 string | number 오버로드라 합집합 인자를 직접 받지 못해 좁힌 시그니처로 호출한다.
      const go = navigateRef.current as ((to: string | number) => void | Promise<void>) | null
      void go?.(path)
    })
  }
  return { ...result, client, user, location, goTo }
}
