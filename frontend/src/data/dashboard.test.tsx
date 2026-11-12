import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it } from 'vitest'
import { resetMock } from '../test/fake/default'
import { dealCode, TEST_NOW } from '../test/fake/testing'
import { USER_ID } from '../test/fake/seed/ids'
import { useSaveAlertSettings } from './alerts'
import { useDashboardSummary } from './dashboard'
import { useApplyDealChange } from './deals'

/** Dashboard 요약 훅(keepPreviousData, 변경 훅의 무효화). */

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  return { queryClient, wrapper }
}

beforeEach(() => {
  resetMock({ now: TEST_NOW, userId: USER_ID.kim })
})

describe('useDashboardSummary', () => {
  // 테스트 코드: DSH-055
  it('조건에 맞는 요약을 읽는다', async () => {
    // given: Fake 게이트웨이와 조회 훅
    const { wrapper } = setup()

    // when: 2026년 요약을 읽는다
    const { result } = renderHook(() => useDashboardSummary({ year: 2026 }), { wrapper })

    // then: 성공하고 기간이 2026 전체다
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.period).toMatchObject({ year: 2026, quarter: null, quarters: [] })
  })

  // 테스트 코드: DSH-055
  it('다음 조건을 읽는 동안 이전 요약을 유지한다', async () => {
    // given: 연도만으로 읽은 요약
    const { wrapper } = setup()
    const { result, rerender } = renderHook(({ quarters }: { quarters?: (1 | 2 | 3 | 4)[] }) => useDashboardSummary({ year: 2026, quarters }), {
      wrapper,
      initialProps: {},
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // when: 조건을 Q2로 바꾼다
    rerender({ quarters: [2] })

    // then: 바로 이전 요약이 남아 있다가 새 응답으로 바뀐다
    expect(result.current.data).toBeDefined()
    await waitFor(() => expect(result.current.data?.period.quarter).toBe(2))
  })

  // 테스트 코드: DSH-055
  it('실패한 조회는 재시도 없이 ApiError로 알린다', async () => {
    // given: 로그인하지 않은 상태
    resetMock({ now: TEST_NOW, userId: null })
    const { wrapper } = setup()

    // when: 요약을 읽는다
    const { result } = renderHook(() => useDashboardSummary({ year: 2026 }), { wrapper })

    // then: 오류가 되고 상태는 401이다
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.status).toBe(401)
  })

  // 테스트 코드: DSH-055
  it('Deal을 바꾸면 요약을 다시 읽는다(Forecast 셀이 옮겨 간다)', async () => {
    // given: 요약을 읽은 상태와 Deal 변경 훅
    const code = dealCode(2)
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ summary: useDashboardSummary({ year: 2026 }), apply: useApplyDealChange() }), { wrapper })
    await waitFor(() => expect(result.current.summary.isSuccess).toBe(true))
    const commitBefore = result.current.summary.data?.forecast.cells.commit?.count ?? 0

    // when: Deal의 Forecast를 Commit으로 바꾼다
    await act(async () => {
      await result.current.apply.mutateAsync({ code, request: { change: { field: 'forecastKey', value: 'commit' } } })
    })

    // then: Commit 셀이 하나 늘어난다
    await waitFor(() => expect(result.current.summary.data?.forecast.cells.commit?.count).toBe(commitBefore + 1))
  })

  // 테스트 코드: DSH-055
  it('경고 기준을 저장하면 미업데이트 기준일을 다시 읽는다', async () => {
    // given: admin으로 읽은 요약과 경고 기준 저장 훅
    resetMock({ now: TEST_NOW, userId: USER_ID.root })
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ summary: useDashboardSummary({ year: 2026 }), save: useSaveAlertSettings() }), { wrapper })
    await waitFor(() => expect(result.current.summary.isSuccess).toBe(true))
    expect(result.current.summary.data?.attention.staleDays).not.toBe(365)

    // when: 경고 기준을 365일로 저장한다
    await act(async () => {
      await result.current.save.mutateAsync(365)
    })

    // then: 요약의 stale_days가 365다
    await waitFor(() => expect(result.current.summary.data?.attention.staleDays).toBe(365))
  })
})
