import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it } from 'vitest'
import { resetMock } from '../mock/default'
import { dealCode, fakeFile, TEST_NOW } from '../mock/testing'
import { ApiError } from '../shared/api/problem'
import { usePermissions, useLogin, useLogout, useMe, useQuickLogin } from './auth'
import { useAttachments, useUploadAttachment } from './attachments'
import { useCodeSet, useRenameCode, useCodes } from './codes'
import { useApplyDealChange, useDeal, useDeals, useRemoveDeal } from './deals'
import { useForecastSummary } from './forecast'
import { useCreateAction, useActions } from './actions'
import { useHistory } from './history'

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, wrapper }
}

beforeEach(() => {
  resetMock({ now: TEST_NOW, userId: 'u-kim' })
})

describe('인증 훅', () => {
  it('로그인 전에는 useMe가 401 ApiError, usePermissions는 모두 false다', async () => {
    resetMock({ now: TEST_NOW, userId: null })
    const { wrapper } = setup()
    const me = renderHook(() => useMe(), { wrapper })
    await waitFor(() => expect(me.result.current.isError).toBe(true))
    expect(me.result.current.error).toBeInstanceOf(ApiError)
    expect(me.result.current.error?.status).toBe(401)
    const perm = renderHook(() => usePermissions(), { wrapper })
    await waitFor(() => expect(perm.result.current.role).toBeNull())
    expect(perm.result.current).toMatchObject({ canWrite: false, isAdmin: false, me: null })
  })

  it('useQuickLogin 성공 후 useMe와 usePermissions가 갱신된다', async () => {
    resetMock({ now: TEST_NOW, userId: null })
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ me: useMe(), login: useQuickLogin(), perm: usePermissions() }), { wrapper })
    await waitFor(() => expect(result.current.me.isError).toBe(true))
    await act(async () => {
      await result.current.login.mutateAsync('u-root')
    })
    await waitFor(() => expect(result.current.me.data?.name).toBe('최관리'))
    expect(result.current.perm).toMatchObject({ role: 'admin', canWrite: true, isAdmin: true })
  })

  it('useLogin은 비밀번호가 든 변수를 mutation 캐시에 남기지 않고, 실패는 ApiError로 reject한다', async () => {
    resetMock({ now: TEST_NOW, userId: null })
    const { wrapper, queryClient } = setup()
    const { result, unmount } = renderHook(() => useLogin(), { wrapper })
    await act(async () => {
      await expect(result.current.mutateAsync({ loginId: 'nobody', password: 'x' })).rejects.toMatchObject({ status: 401 })
    })
    await act(async () => {
      await result.current.mutateAsync({ loginId: 'kim', password: 'secret-pw' })
    })
    // gcTime 0: 화면이 닫히면(옵서버 해제) 비밀번호가 든 변수가 캐시에 남지 않는다.
    unmount()
    await waitFor(() => expect(queryClient.getMutationCache().getAll()).toHaveLength(0))
  })

  it('useLogout은 쿼리 캐시를 모두 비우고 이후 useMe는 401이다', async () => {
    const { wrapper, queryClient } = setup()
    await queryClient.prefetchQuery({ queryKey: ['deals', 'list', {}], queryFn: () => 'cached' })
    expect(queryClient.getQueryCache().getAll()).toHaveLength(1)
    const { result } = renderHook(() => useLogout(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync()
    })
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0)
    const me = renderHook(() => useMe(), { wrapper })
    await waitFor(() => expect(me.result.current.isError).toBe(true))
  })
})

describe('Deal 훅', () => {
  it('useDeals 필터와 useDeal 404', async () => {
    const { wrapper } = setup()
    const list = renderHook(() => useDeals({ forecastKey: 'won' }), { wrapper })
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true))
    expect(list.result.current.data?.total).toBe(3)
    const missing = renderHook(() => useDeal('20000101-ZZZZ'), { wrapper })
    await waitFor(() => expect(missing.result.current.isError).toBe(true))
    expect(missing.result.current.error?.status).toBe(404)
    const idle = renderHook(() => useDeal(undefined), { wrapper })
    expect(idle.result.current.fetchStatus).toBe('idle')
  })

  it('useApplyDealChange는 목록·상세·History·Forecast 요약을 무효화해 다시 불러온다', async () => {
    const code = dealCode(2)
    const { wrapper } = setup()
    const { result } = renderHook(
      () => ({
        deals: useDeals({ keyword: code }),
        deal: useDeal(code),
        history: useHistory(code),
        forecast: useForecastSummary({ year: 2026 }),
        apply: useApplyDealChange(),
      }),
      { wrapper },
    )
    await waitFor(() => expect(result.current.history.isSuccess && result.current.forecast.isSuccess).toBe(true))
    const historyBefore = result.current.history.data?.length ?? 0
    const commitBefore = result.current.forecast.data?.totalRow.cells.commit?.count ?? 0
    await act(async () => {
      await result.current.apply.mutateAsync({ code, request: { change: { field: 'forecastKey', value: 'commit' } } })
    })
    await waitFor(() => expect(result.current.deals.data?.items[0]?.forecastKey).toBe('commit'))
    await waitFor(() => expect(result.current.deal.data?.forecastKey).toBe('commit'))
    await waitFor(() => expect(result.current.history.data?.length).toBe(historyBefore + 1))
    await waitFor(() => expect(result.current.forecast.data?.totalRow.cells.commit?.count).toBe(commitBefore + 1))
  })

  it('useRemoveDeal은 하위 쿼리를 제거하고 목록을 다시 불러온다', async () => {
    const code = dealCode(11)
    const { wrapper, queryClient } = setup()
    // 상세 화면이 닫힌 뒤(옵서버 없음)의 캐시 상태를 확인한다.
    const detail = renderHook(() => useActions(code), { wrapper })
    await waitFor(() => expect(detail.result.current.isSuccess).toBe(true))
    detail.unmount()
    const { result } = renderHook(() => ({ deals: useDeals({ limit: 100 }), remove: useRemoveDeal() }), { wrapper })
    await waitFor(() => expect(result.current.deals.isSuccess).toBe(true))
    await act(async () => {
      await result.current.remove.mutateAsync({ code, confirmCode: code })
    })
    expect(queryClient.getQueryCache().find({ queryKey: ['actions', code] })).toBeUndefined()
    await waitFor(() => expect(result.current.deals.data?.total).toBe(23))
  })

  it('거부된 변경은 ApiError(422)로 reject한다', async () => {
    const { wrapper } = setup()
    const { result } = renderHook(() => useApplyDealChange(), { wrapper })
    await act(async () => {
      await expect(
        result.current.mutateAsync({ code: dealCode(1), request: { change: { field: 'statusKey', value: 'contract_completed' } } }),
      ).rejects.toMatchObject({ status: 422 })
    })
  })
})

describe('Action·첨부·코드 훅', () => {
  it('useCreateAction은 Action 목록과 History를 갱신한다', async () => {
    const code = dealCode(2)
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ actions: useActions(code), history: useHistory(code), create: useCreateAction() }), { wrapper })
    await waitFor(() => expect(result.current.actions.isSuccess && result.current.history.isSuccess).toBe(true))
    const n = result.current.actions.data?.length ?? 0
    await act(async () => {
      await result.current.create.mutateAsync({ dealCode: code, input: { type: '통화', progress: '확인', nextAction: '회신', dueDate: '2026-10-20', memo: '' } })
    })
    await waitFor(() => expect(result.current.actions.data?.length).toBe(n + 1))
    await waitFor(() => expect(result.current.history.data?.[0]?.category).toBe('action'))
  })

  it('useUploadAttachment: 같은 이름은 file-exists(409) 후 replace로 다시 호출', async () => {
    const code = dealCode(1)
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ list: useAttachments(code), upload: useUploadAttachment() }), { wrapper })
    await waitFor(() => expect(result.current.list.isSuccess).toBe(true))
    const file = fakeFile('제안서_ITDR.pptx', 55)
    await act(async () => {
      await expect(result.current.upload.mutateAsync({ dealCode: code, input: { file, description: '', onExists: 'ask' } })).rejects.toMatchObject({ status: 409 })
    })
    await act(async () => {
      await result.current.upload.mutateAsync({ dealCode: code, input: { file, description: '', onExists: 'replace' } })
    })
    await waitFor(() => expect(result.current.list.data?.find((a) => a.fileName === '제안서_ITDR.pptx')?.size).toBe(55))
  })

  it('useRenameCode는 코드 집합을 갱신해 새 이름이 배지에 반영된다', async () => {
    resetMock({ now: TEST_NOW, userId: 'u-root' })
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ set: useCodeSet(), list: useCodes('status'), rename: useRenameCode() }), { wrapper })
    await waitFor(() => expect(result.current.set.isSuccess && result.current.list.isSuccess).toBe(true))
    const target = result.current.list.data?.find((c) => c.key === 'prospecting')
    await act(async () => {
      await result.current.rename.mutateAsync({ id: target?.id ?? '', name: '발굴' })
    })
    await waitFor(() => expect(result.current.set.data?.statuses[0]?.name).toBe('발굴'))
  })
})
