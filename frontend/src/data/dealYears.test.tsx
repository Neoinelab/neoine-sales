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
  it('연도 조회 키는 deals 키 아래에 있어 Deal이 바뀔 때마다 함께 갱신된다', () => {
    // when·then: 키 값을 확인한다
    expect(keys.dealYears).toEqual(['deals', 'years'])
  })
})

describe('useDealYears', () => {
  it('연도 조회 훅은 게이트웨이의 연도 응답을 그대로 읽는다', async () => {
    // given: 게이트웨이가 가장 이른 연도 2021을 답한다
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2021 })
    const { wrapper } = setup()

    // when: 연도 조회 훅을 렌더한다
    const { result } = renderHook(() => useDealYears(), { wrapper })

    // then: 응답 데이터가 그대로 보인다
    await waitFor(() => expect(result.current.data).toEqual({ earliestYear: 2021 }))
  })

  it('연도 응답을 keys.dealYears 키로 캐시에 저장한다', async () => {
    const { wrapper, queryClient } = setup()
    // when: 연도 조회 훅을 렌더하고 성공할 때까지 기다린다
    const { result } = renderHook(() => useDealYears(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // then: 캐시의 같은 키에 응답이 들어 있다
    expect(queryClient.getQueryData(keys.dealYears)).toEqual(result.current.data)
  })
})

describe('useYearOptions', () => {
  it('가장 이른 연도를 알면 그 연도부터 내년까지 선택지를 만든다', async () => {
    // given: 가장 이른 연도가 2023이다
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    const { wrapper } = setup()

    // when: 연도 선택지 훅을 렌더한다
    const { result } = renderHook(() => useYearOptions(), { wrapper })

    // then: 2023부터 내년(2027)까지이고 오류가 없다
    await waitFor(() => expect(result.current.years).toEqual([2023, 2024, 2025, 2026, 2027]))
    expect(result.current.error).toBeNull()
  })

  it('연도 목록을 읽는 동안에는 올해와 내년만 선택지로 준다', async () => {
    // given: 연도 응답이 오지 않는다
    vi.spyOn(gateway.deals, 'years').mockReturnValue(new Promise(() => {}))
    const { wrapper } = setup()

    // when: 연도 선택지 훅을 렌더한다
    const { result } = renderHook(() => useYearOptions(), { wrapper })

    // then: 올해·내년만 보이고 오류가 없다
    expect(result.current.years).toEqual([2026, 2027])
    expect(result.current.error).toBeNull()
  })

  it('연도 목록 조회가 실패하면 올해와 내년만 주고 오류를 알린다', async () => {
    // given: 연도 조회가 500으로 실패한다
    const failure = new ApiError(500)
    vi.spyOn(gateway.deals, 'years').mockRejectedValue(failure)
    const { wrapper } = setup()

    // when: 연도 선택지 훅을 렌더한다
    const { result } = renderHook(() => useYearOptions(), { wrapper })

    // then: 오류가 전달되고 선택지는 올해·내년이다
    await waitFor(() => expect(result.current.error).toBe(failure))
    expect(result.current.years).toEqual([2026, 2027])
  })

  it('범위 밖의 현재 선택 연도는 한 번만 덧붙인다', async () => {
    // given: 가장 이른 연도가 2023이다
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    const { wrapper } = setup()

    // when: 범위 밖 연도 2031을 현재 값으로 넘겨 렌더한다
    const { result } = renderHook(() => useYearOptions(2031), { wrapper })

    // then: 2031이 목록 끝에 한 번 더해진다
    await waitFor(() => expect(result.current.years).toEqual([2023, 2024, 2025, 2026, 2027, 2031]))
  })

  it('올해+2년은 더 이상 선택지에 없다', async () => {
    // given: 가장 이른 연도가 2023이다
    vi.spyOn(gateway.deals, 'years').mockResolvedValue({ earliestYear: 2023 })
    const { wrapper } = setup()

    // when: 연도 선택지 훅을 렌더하고 목록이 채워질 때까지 기다린다
    const { result } = renderHook(() => useYearOptions(), { wrapper })
    await waitFor(() => expect(result.current.years).toContain(2023))

    // then: 2028은 없다
    expect(result.current.years).not.toContain(2028)
  })
})

describe('연도 선택지 재계산', () => {
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

  it('Deal을 등록하면 연도를 다시 묻고 더 이른 연도를 보여 준다', async () => {
    const { spy, result } = await mounted()

    // when: 2019년 매출일의 Deal을 등록한다
    await act(async () => {
      await result.current.create.mutateAsync(dealInput(USER_ID.kim, { revenueDate: '2019-05-01' }))
    })

    // then: 가장 이른 연도가 2019가 되고 연도 조회가 다시 일어난다
    await waitFor(() => expect(result.current.years.data).toEqual({ earliestYear: 2019 }))
    expect(spy.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('Deal을 수정하면 연도를 다시 묻는다', async () => {
    const { spy, result } = await mounted()

    // when: Deal의 매출일을 2018년으로 수정한다
    await act(async () => {
      await result.current.update.mutateAsync({ code: dealCode(2), patch: { revenueDate: '2018-02-03' } })
    })

    // then: 가장 이른 연도가 2018이 되고 연도 조회가 다시 일어난다
    await waitFor(() => expect(result.current.years.data).toEqual({ earliestYear: 2018 }))
    expect(spy.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('목록에서 Deal의 Expected Close를 바로 바꾸면 연도를 다시 묻는다', async () => {
    const { spy, result } = await mounted()

    // when: 변경 적용으로 매출일을 2017년으로 바꾼다
    await act(async () => {
      await result.current.apply.mutateAsync({ code: dealCode(2), request: { change: { field: 'revenueDate', value: '2017-01-02' } } })
    })

    // then: 가장 이른 연도가 2017이 되고 연도 조회가 다시 일어난다
    await waitFor(() => expect(result.current.years.data).toEqual({ earliestYear: 2017 }))
    expect(spy.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('가장 이른 Deal을 삭제하면 연도를 다시 묻고 다음 연도를 보여 준다', async () => {
    const { result } = await mounted()
    // given: 2016년 매출일의 Deal을 등록해 가장 이른 연도가 2016이다
    let created = ''
    await act(async () => {
      created = (await result.current.create.mutateAsync(dealInput(USER_ID.kim, { revenueDate: '2016-05-01' }))).code
    })
    await waitFor(() => expect(result.current.years.data).toEqual({ earliestYear: 2016 }))

    // when: 그 Deal을 삭제한다
    await act(async () => {
      await result.current.remove.mutateAsync({ code: created, confirmCode: created })
    })

    // then: 가장 이른 연도가 2026으로 돌아온다
    await waitFor(() => expect(result.current.years.data).toEqual({ earliestYear: 2026 }))
  })
})
