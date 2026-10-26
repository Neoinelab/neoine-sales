import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../gateway'
import { resetMock } from '../test/fake/default'
import { dealCode, dealInput, TEST_NOW } from '../test/fake/testing'
import { USER_ID } from '../test/fake/seed/ids'
import { useApplyDealChange, useCreateDeal, useRemoveDeal, useUpdateDeal } from './deals'
import { useDealYears, useYearOptions } from './dealYears'
import { keys } from './queryKeys'
import { ApiError } from '../shared/api/problem'

/** 연도 선택지 훅(R2): 서버는 가장 이른 연도만 주고, 선택지는 `selectableYears`가 올해(앱 시계)로 만든다. TEST_NOW = 2026-10-15. */

beforeEach(() => resetMock({ now: TEST_NOW, userId: USER_ID.kim }))
afterEach(() => vi.restoreAllMocks())

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  return { queryClient, wrapper }
}

describe('keys.dealYears', () => {
  it('lives under the deals key so every deal change refreshes it', () => {
    expect(keys.dealYears).toEqual(['deals', 'years'])
  })
})

describe('useDealYears', () => {
  it('reads gateway.deals.years', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2021 })
    const { wrapper } = setup()

    const { result } = renderHook(() => useDealYears(), { wrapper })

    await waitFor(() => expect(result.current.data).toEqual({ earliestYear: 2021 }))
  })

  it('stores the answer under keys.dealYears', async () => {
    const { wrapper, queryClient } = setup()
    const { result } = renderHook(() => useDealYears(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(queryClient.getQueryData(keys.dealYears)).toEqual(result.current.data)
  })
})

describe('useYearOptions', () => {
  it('builds earliest..next year once the earliest year is known', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    const { wrapper } = setup()

    const { result } = renderHook(() => useYearOptions(), { wrapper })

    await waitFor(() => expect(result.current.years).toEqual([2023, 2024, 2025, 2026, 2027]))
    expect(result.current.error).toBeNull()
  })

  it('offers this and next year while the list is loading', async () => {
    vi.spyOn(gateway.deals, 'years').mockReturnValue(new Promise(() => {}))
    const { wrapper } = setup()

    const { result } = renderHook(() => useYearOptions(), { wrapper })

    expect(result.current.years).toEqual([2026, 2027])
    expect(result.current.error).toBeNull()
  })

  it('offers this and next year and reports the error when the list fails', async () => {
    const failure = new ApiError(500)
    vi.spyOn(gateway.deals, 'years').mockRejectedValue(failure)
    const { wrapper } = setup()

    const { result } = renderHook(() => useYearOptions(), { wrapper })

    await waitFor(() => expect(result.current.error).toBe(failure))
    expect(result.current.years).toEqual([2026, 2027])
  })

  it('adds a current year outside the range once', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    const { wrapper } = setup()

    const { result } = renderHook(() => useYearOptions(2031), { wrapper })

    await waitFor(() => expect(result.current.years).toEqual([2023, 2024, 2025, 2026, 2027, 2031]))
  })

  it('has no this year + 2 any more', async () => {
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    const { wrapper } = setup()

    const { result } = renderHook(() => useYearOptions(), { wrapper })

    await waitFor(() => expect(result.current.years).toContain(2023))
    expect(result.current.years).not.toContain(2028)
  })
})

describe('연도 선택지 재계산 (AC2-6)', () => {
  /** 연도 조회와 변경 훅을 한 트리에 마운트한다(변경 뒤 재조회 결과가 같은 트리에서 보인다). */
  async function mounted() {
    const spy = vi.spyOn(gateway.deals, 'years')
    const { wrapper } = setup()
    const hook = renderHook(
      () => ({ years: useDealYears(), create: useCreateDeal(), update: useUpdateDeal(), apply: useApplyDealChange(), remove: useRemoveDeal() }),
      { wrapper },
    )
    await waitFor(() => expect(hook.result.current.years.isSuccess).toBe(true))
    expect(spy).toHaveBeenCalledTimes(1)
    return { spy, result: hook.result }
  }

  it('asks again after a deal is created and shows an earlier year', async () => {
    const { spy, result } = await mounted()

    await act(async () => {
      await result.current.create.mutateAsync(dealInput(USER_ID.kim, { revenueDate: '2019-05-01' }))
    })

    await waitFor(() => expect(result.current.years.data).toEqual({ earliestYear: 2019 }))
    expect(spy.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('asks again after a deal is updated', async () => {
    const { spy, result } = await mounted()

    await act(async () => {
      await result.current.update.mutateAsync({ code: dealCode(2), patch: { revenueDate: '2018-02-03' } })
    })

    await waitFor(() => expect(result.current.years.data).toEqual({ earliestYear: 2018 }))
    expect(spy.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('asks again after a deal is changed inline (Expected Close)', async () => {
    const { spy, result } = await mounted()

    await act(async () => {
      await result.current.apply.mutateAsync({ code: dealCode(2), request: { change: { field: 'revenueDate', value: '2017-01-02' } } })
    })

    await waitFor(() => expect(result.current.years.data).toEqual({ earliestYear: 2017 }))
    expect(spy.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('asks again after the earliest deal is deleted and shows the next year', async () => {
    const { result } = await mounted()
    let created = ''
    await act(async () => {
      created = (await result.current.create.mutateAsync(dealInput(USER_ID.kim, { revenueDate: '2016-05-01' }))).code
    })
    await waitFor(() => expect(result.current.years.data).toEqual({ earliestYear: 2016 }))

    await act(async () => {
      await result.current.remove.mutateAsync({ code: created, confirmCode: created })
    })

    await waitFor(() => expect(result.current.years.data).toEqual({ earliestYear: 2026 }))
  })
})
