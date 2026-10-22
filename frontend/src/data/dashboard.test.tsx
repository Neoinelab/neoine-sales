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

/** Dashboard 요약 훅(Dashboard AC-20 keepPreviousData, 변경 훅의 무효화). */

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  return { queryClient, wrapper }
}

beforeEach(() => {
  resetMock({ now: TEST_NOW, userId: USER_ID.kim })
})

describe('useDashboardSummary', () => {
  it('loads the summary for the query', async () => {
    const { wrapper } = setup()

    const { result } = renderHook(() => useDashboardSummary({ year: 2026 }), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.period).toMatchObject({ year: 2026, quarter: null })
  })

  it('keeps the previous summary while the next condition loads', async () => {
    const { wrapper } = setup()
    const { result, rerender } = renderHook(({ quarter }: { quarter?: 1 | 2 | 3 | 4 }) => useDashboardSummary({ year: 2026, quarter }), {
      wrapper,
      initialProps: {},
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    rerender({ quarter: 2 })

    expect(result.current.data).toBeDefined()
    await waitFor(() => expect(result.current.data?.period.quarter).toBe(2))
  })

  it('reports a rejected request as an ApiError without retrying', async () => {
    resetMock({ now: TEST_NOW, userId: null })
    const { wrapper } = setup()

    const { result } = renderHook(() => useDashboardSummary({ year: 2026 }), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.status).toBe(401)
  })

  it('refreshes after a deal change (the Forecast cell moves)', async () => {
    const code = dealCode(2)
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ summary: useDashboardSummary({ year: 2026 }), apply: useApplyDealChange() }), { wrapper })
    await waitFor(() => expect(result.current.summary.isSuccess).toBe(true))
    const commitBefore = result.current.summary.data?.forecast.cells.commit?.count ?? 0

    await act(async () => {
      await result.current.apply.mutateAsync({ code, request: { change: { field: 'forecastKey', value: 'commit' } } })
    })

    await waitFor(() => expect(result.current.summary.data?.forecast.cells.commit?.count).toBe(commitBefore + 1))
  })

  it('refreshes the stale days after the alert settings are saved', async () => {
    resetMock({ now: TEST_NOW, userId: USER_ID.root })
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ summary: useDashboardSummary({ year: 2026 }), save: useSaveAlertSettings() }), { wrapper })
    await waitFor(() => expect(result.current.summary.isSuccess).toBe(true))
    expect(result.current.summary.data?.attention.staleDays).not.toBe(365)

    await act(async () => {
      await result.current.save.mutateAsync(365)
    })

    await waitFor(() => expect(result.current.summary.data?.attention.staleDays).toBe(365))
  })
})
