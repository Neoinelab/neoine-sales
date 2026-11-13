import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it } from 'vitest'
import { resetMock } from '../test/fake/default'
import { dealCode, fakeFile, TEST_NOW } from '../test/fake/testing'
import { ApiError } from '../shared/api/problem'
import { usePermissions, useLogin, useLogout, useMe } from './auth'
import { useAttachments, useUploadAttachment } from './attachments'
import { useCodeSet, useRenameCode, useCodes } from './codes'
import { useApplyDealChange, useDeal, useDeals, useRemoveDeal, useUpdateDeal } from './deals'
import { useForecastSummary } from './forecast'
import { useCreateAction, useActions } from './actions'
import { useActionTypes, useCreateActionType, useRemoveActionType, useRenameActionType } from './actionTypes'
import { useLabels } from './labels'
import { useHistory } from './history'
import { NO_SUCH_ID, USER_ID } from '../test/fake/seed/ids'
import { SEED_PASSWORD } from '../test/fake/seed/users'

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, wrapper }
}

beforeEach(() => {
  resetMock({ now: TEST_NOW, userId: USER_ID.kim })
})

describe('인증 훅', () => {
  // 로그인 전 내 정보 훅은 401이고 권한은 모두 false다.
  // 테스트 코드: AU-088
  it('로그인 전에는 useMe가 401 ApiError, usePermissions는 모두 false다', async () => {
    // given: 로그인하지 않은 상태
    resetMock({ now: TEST_NOW, userId: null })
    const { wrapper } = setup()
    // when: 내 정보 훅과 권한 훅을 렌더한다
    const me = renderHook(() => useMe(), { wrapper })
    await waitFor(() => expect(me.result.current.isError).toBe(true))
    // then: 401 ApiError이고 권한은 모두 false다
    expect(me.result.current.error).toBeInstanceOf(ApiError)
    expect(me.result.current.error?.status).toBe(401)
    const perm = renderHook(() => usePermissions(), { wrapper })
    await waitFor(() => expect(perm.result.current.role).toBeNull())
    expect(perm.result.current).toMatchObject({ canWrite: false, isAdmin: false, me: null })
  })

  // 로그인 훅이 성공하면 내 정보와 권한이 갱신된다.
  // 테스트 코드: AU-088
  it('useLogin 성공 후 useMe와 usePermissions가 갱신된다', async () => {
    // given: 로그인하지 않은 상태에서 내 정보가 401이다
    resetMock({ now: TEST_NOW, userId: null })
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ me: useMe(), login: useLogin(), perm: usePermissions() }), { wrapper })
    await waitFor(() => expect(result.current.me.isError).toBe(true))
    await act(async () => {
      // when: root가 로그인 훅으로 로그인한다
      await result.current.login.mutateAsync({ loginId: 'root', password: SEED_PASSWORD })
    })
    // then: 내 정보가 root로 바뀌고 admin 권한이 된다
    await waitFor(() => expect(result.current.me.data?.name).toBe('최관리'))
    expect(result.current.perm).toMatchObject({ role: 'admin', canWrite: true, isAdmin: true })
  })

  // 로그인 훅은 실패를 ApiError로 reject하고 비밀번호가 든 변수를 캐시에 남기지 않는다.
  // 테스트 코드: AU-088
  it('useLogin은 비밀번호가 든 변수를 mutation 캐시에 남기지 않고, 실패는 ApiError로 reject한다', async () => {
    // given: 로그인하지 않은 상태의 로그인 훅
    resetMock({ now: TEST_NOW, userId: null })
    const { wrapper, queryClient } = setup()
    const { result, unmount } = renderHook(() => useLogin(), { wrapper })
    await act(async () => {
      // when: 틀린 로그인 뒤 올바른 로그인을 한다
      await expect(result.current.mutateAsync({ loginId: 'nobody', password: 'x' })).rejects.toMatchObject({ status: 401 })
    })
    await act(async () => {
      await result.current.mutateAsync({ loginId: 'kim', password: SEED_PASSWORD })
    })
    // gcTime 0: 화면이 닫히면(옵서버 해제) 비밀번호가 든 변수가 캐시에 남지 않는다.
    // then: 401로 reject되었고 화면이 닫히면 변수가 mutation 캐시에 남지 않는다
    unmount()
    await waitFor(() => expect(queryClient.getMutationCache().getAll()).toHaveLength(0))
  })

  // 로그아웃 훅은 쿼리 캐시를 모두 비우고 이후 내 정보는 401이다.
  // 테스트 코드: AU-084
  it('useLogout은 쿼리 캐시를 모두 비우고 이후 useMe는 401이다', async () => {
    const { wrapper, queryClient } = setup()
    // given: 쿼리 캐시에 데이터가 하나 있다
    await queryClient.prefetchQuery({ queryKey: ['deals', 'list', {}], queryFn: () => 'cached' })
    expect(queryClient.getQueryCache().getAll()).toHaveLength(1)
    const { result } = renderHook(() => useLogout(), { wrapper })
    await act(async () => {
      // when: 로그아웃 훅을 실행한다
      await result.current.mutateAsync()
    })
    // then: 캐시가 비고 이후 내 정보 조회가 실패한다
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0)
    const me = renderHook(() => useMe(), { wrapper })
    await waitFor(() => expect(me.result.current.isError).toBe(true))
  })
})

describe('Deal 훅', () => {
  // useDeals는 Forecast 필터를 적용하고, useDeal은 없는 코드면 404, 코드가 없으면 조회하지 않는다.
  it('useDeals 필터와 useDeal 404', async () => {
    const { wrapper } = setup()
    // when: Won만 필터해 목록을 읽는다
    const list = renderHook(() => useDeals({ forecastKeys: ['won'] }), { wrapper })
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true))
    // then: Won Deal 3건이다
    expect(list.result.current.data?.total).toBe(3)
    // when: 없는 코드로 상세를 읽는다
    const missing = renderHook(() => useDeal('20000101-ZZZZ'), { wrapper })
    await waitFor(() => expect(missing.result.current.isError).toBe(true))
    // then: 404 오류다
    expect(missing.result.current.error?.status).toBe(404)
    // when: 코드 없이 상세 훅을 렌더한다
    const idle = renderHook(() => useDeal(undefined), { wrapper })
    // then: 조회하지 않고 대기 상태다
    expect(idle.result.current.fetchStatus).toBe('idle')
  })

  // 테스트 코드: FC-084
  it('useApplyDealChange는 목록·상세·History·Forecast 요약을 무효화해 다시 불러온다', async () => {
    // given: Deal 목록·상세·History와 열려 있는 Forecast 요약
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
    // when: Deal의 Forecast를 commit으로 바꾼다
    await act(async () => {
      await result.current.apply.mutateAsync({ code, request: { change: { field: 'forecastKey', value: 'commit' } } })
    })
    // then: 목록·상세·History가 새 값으로 다시 읽히고 Forecast 요약의 commit 건수가 1건 늘어난다
    await waitFor(() => expect(result.current.deals.data?.items[0]?.forecastKey).toBe('commit'))
    await waitFor(() => expect(result.current.deal.data?.forecastKey).toBe('commit'))
    await waitFor(() => expect(result.current.history.data?.length).toBe(historyBefore + 1))
    await waitFor(() => expect(result.current.forecast.data?.totalRow.cells.commit?.count).toBe(commitBefore + 1))
  })

  // Deal을 삭제하면 그 Deal의 하위 쿼리 캐시가 사라지고 목록이 다시 읽힌다.
  it('useRemoveDeal은 하위 쿼리를 제거하고 목록을 다시 불러온다', async () => {
    // given: 상세 화면이 닫힌 뒤(옵서버 없음)의 Action 캐시와 열린 Deal 목록 (KIM이 지울 수 있는 완료되지 않은 Deal)
    const code = dealCode(2)
    const { wrapper, queryClient } = setup()
    const detail = renderHook(() => useActions(code), { wrapper })
    await waitFor(() => expect(detail.result.current.isSuccess).toBe(true))
    detail.unmount()
    const { result } = renderHook(() => ({ deals: useDeals({ limit: 100 }), remove: useRemoveDeal() }), { wrapper })
    await waitFor(() => expect(result.current.deals.isSuccess).toBe(true))
    // when: Deal을 삭제한다
    await act(async () => {
      await result.current.remove.mutateAsync({ code, confirmCode: code })
    })
    // then: Action 캐시가 없어지고 목록 총 건수가 줄어든다
    expect(queryClient.getQueryCache().find({ queryKey: ['actions', code] })).toBeUndefined()
    await waitFor(() => expect(result.current.deals.data?.total).toBe(23))
  })

  // 거부된 변경은 ApiError(422)로 reject된다.
  it('거부된 변경은 ApiError(422)로 reject한다', async () => {
    // given: 변경 적용 훅
    const { wrapper } = setup()
    const { result } = renderHook(() => useApplyDealChange(), { wrapper })
    await act(async () => {
      // when·then: 허용되지 않는 Status로 바꾸면 422로 reject된다
      await expect(
        result.current.mutateAsync({ code: dealCode(1), request: { change: { field: 'statusKey', value: 'contract_completed' } } }),
      ).rejects.toMatchObject({ status: 422 })
    })
  })
})

describe('Action·첨부·코드 훅', () => {
  // Action을 등록하면 Action 목록과 History가 다시 읽힌다.
  it('useCreateAction은 Action 목록과 History를 갱신한다', async () => {
    // given: Deal의 Action 목록과 History
    const code = dealCode(2)
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ actions: useActions(code), history: useHistory(code), create: useCreateAction() }), { wrapper })
    await waitFor(() => expect(result.current.actions.isSuccess && result.current.history.isSuccess).toBe(true))
    const n = result.current.actions.data?.length ?? 0
    // when: Action을 등록한다
    await act(async () => {
      await result.current.create.mutateAsync({ dealCode: code, input: { type: { name: '통화' }, progress: '확인', nextAction: '회신', dueDate: '2026-10-20', memo: '' } })
    })
    // then: Action이 한 건 늘고 History 맨 위가 action이다
    await waitFor(() => expect(result.current.actions.data?.length).toBe(n + 1))
    await waitFor(() => expect(result.current.history.data?.[0]?.category).toBe('action'))
  })

  // 같은 이름 파일은 409로 거절되고, replace로 다시 올리면 덮어쓴다.
  it('useUploadAttachment: 같은 이름은 file-exists(409) 후 replace로 다시 호출', async () => {
    // given: 같은 이름의 첨부가 있는 Deal과 같은 이름의 새 파일
    const code = dealCode(1)
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ list: useAttachments(code), upload: useUploadAttachment() }), { wrapper })
    await waitFor(() => expect(result.current.list.isSuccess).toBe(true))
    const file = fakeFile('견적서_한빛은행_v2.pdf', 55)
    await act(async () => {
      // when·then: ask로 올리면 409로 reject된다
      await expect(result.current.upload.mutateAsync({ dealCode: code, input: { file, description: '', onExists: 'ask' } })).rejects.toMatchObject({ status: 409 })
    })
    // when: replace로 다시 올린다
    await act(async () => {
      await result.current.upload.mutateAsync({ dealCode: code, input: { file, description: '', onExists: 'replace' } })
    })
    // then: 첨부 목록의 그 파일 크기가 55로 바뀐다
    await waitFor(() => expect(result.current.list.data?.find((a) => a.fileName === '견적서_한빛은행_v2.pdf')?.size).toBe(55))
  })

  // 코드 이름을 바꾸면 코드 집합이 갱신된다.
  it('useRenameCode는 코드 집합을 갱신해 새 이름이 배지에 반영된다', async () => {
    // given: admin으로 읽은 코드 집합과 status 코드 목록
    resetMock({ now: TEST_NOW, userId: USER_ID.root })
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ set: useCodeSet(), list: useCodes('status'), rename: useRenameCode() }), { wrapper })
    await waitFor(() => expect(result.current.set.isSuccess && result.current.list.isSuccess).toBe(true))
    const target = result.current.list.data?.find((c) => c.key === 'prospecting')
    // when: prospecting 코드 이름을 '발굴'로 바꾼다
    await act(async () => {
      await result.current.rename.mutateAsync({ id: target?.id ?? NO_SUCH_ID, name: '발굴' })
    })
    // then: 코드 집합의 첫 Status 이름이 '발굴'이다
    await waitFor(() => expect(result.current.set.data?.statuses[0]?.name).toBe('발굴'))
  })
})

describe('Action 유형 훅', () => {
  // 기본 Action 유형 8개를 서버 순서로 읽는다.
  it('useActionTypes는 기본 유형 8개를 서버 순서로 읽는다', async () => {
    const { wrapper } = setup()
    // when: Action 유형 목록을 읽는다
    const { result } = renderHook(() => useActionTypes(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    // then: 기본 8개가 서버 순서다
    expect(result.current.data?.map((t) => t.name)).toEqual(['통화', '미팅', '이메일', '데모', '제안', '협상', '계약', '기타'])
  })

  // 유형을 만들면 유형 목록이 갱신된다.
  it('useCreateActionType은 유형 목록을 갱신한다', async () => {
    // given: 읽어 둔 유형 목록
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ list: useActionTypes(), create: useCreateActionType() }), { wrapper })
    await waitFor(() => expect(result.current.list.isSuccess).toBe(true))
    // when: '웨비나' 유형을 만든다
    await act(async () => {
      await result.current.create.mutateAsync('웨비나')
    })
    // then: 목록에 '웨비나'가 보인다
    await waitFor(() => expect(result.current.list.data?.some((t) => t.name === '웨비나')).toBe(true))
  })

  // 새 이름의 유형으로 Action을 등록하면 그 유형이 만들어져 목록에 보인다.
  it('이름이 새 유형인 Action을 등록하면 유형 목록에 그 유형이 보인다', async () => {
    // given: 읽어 둔 유형 목록
    const code = dealCode(2)
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ types: useActionTypes(), create: useCreateAction() }), { wrapper })
    await waitFor(() => expect(result.current.types.isSuccess).toBe(true))
    // when: 목록에 없는 '현장 점검' 유형으로 Action을 등록한다
    await act(async () => {
      await result.current.create.mutateAsync({ dealCode: code, input: { type: { name: '현장 점검' }, progress: '확인', nextAction: '회신', dueDate: '2026-10-20', memo: '' } })
    })
    // then: 유형 목록에 '현장 점검'이 사용 1건으로 보인다
    await waitFor(() => expect(result.current.types.data?.find((t) => t.name === '현장 점검')?.usageCount).toBe(1))
  })

  // 유형 이름을 바꾸면 유형 목록과 Action 목록의 이름이 함께 바뀐다.
  it('useRenameActionType은 유형 목록과 Action 목록의 이름을 함께 갱신한다', async () => {
    // given: admin으로 읽은 유형 목록과 '협상' 유형 Action이 있는 Deal의 Action 목록
    resetMock({ now: TEST_NOW, userId: USER_ID.root })
    const code = dealCode(1)
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ types: useActionTypes(), actions: useActions(code), rename: useRenameActionType() }), { wrapper })
    await waitFor(() => expect(result.current.types.isSuccess && result.current.actions.isSuccess).toBe(true))
    const negotiation = result.current.types.data?.find((t) => t.name === '협상')
    expect(result.current.actions.data?.some((a) => a.type === '협상')).toBe(true)
    // when: '협상' 유형 이름을 '가격 협상'으로 바꾼다
    await act(async () => {
      await result.current.rename.mutateAsync({ id: negotiation?.id ?? NO_SUCH_ID, name: '가격 협상' })
    })
    // then: 유형 목록과 Action 목록 모두 새 이름이고 옛 이름은 없다
    await waitFor(() => expect(result.current.types.data?.some((t) => t.name === '가격 협상')).toBe(true))
    await waitFor(() => expect(result.current.actions.data?.some((a) => a.type === '가격 협상')).toBe(true))
    expect(result.current.actions.data?.some((a) => a.type === '협상')).toBe(false)
  })

  // 쓰지 않는 유형을 지우면 목록에서 사라진다.
  it('useRemoveActionType은 쓰지 않는 유형을 지우고 목록을 갱신한다', async () => {
    // given: admin으로 만든 '임시' 유형이 보이는 목록
    resetMock({ now: TEST_NOW, userId: USER_ID.root })
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ list: useActionTypes(), create: useCreateActionType(), remove: useRemoveActionType() }), { wrapper })
    await waitFor(() => expect(result.current.list.isSuccess).toBe(true))
    let id = 0
    await act(async () => {
      id = (await result.current.create.mutateAsync('임시')).id
    })
    await waitFor(() => expect(result.current.list.data?.some((t) => t.id === id)).toBe(true))
    // when: 그 유형을 지운다
    await act(async () => {
      await result.current.remove.mutateAsync(id)
    })
    // then: 목록에서 사라진다
    await waitFor(() => expect(result.current.list.data?.some((t) => t.id === id)).toBe(false))
  })
})

describe('Deal 저장이 만든 BANT Label', () => {
  // Deal에 새 BANT Label 이름을 저장하면 Label 목록에 그 Label이 만들어진다.
  it('useUpdateDeal로 새 Label 이름을 저장하면 Label 목록에 그 Label이 보인다', async () => {
    // given: 읽어 둔 Label 목록
    const code = dealCode(2)
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ labels: useLabels(), update: useUpdateDeal() }), { wrapper })
    await waitFor(() => expect(result.current.labels.isSuccess).toBe(true))
    // when: Timeline에 목록에 없는 Label 이름을 저장한다
    await act(async () => {
      await result.current.update.mutateAsync({ code, patch: { bant: { budget: null, authority: null, need: null, timeline: { name: '내후년 구매 검토' } } } })
    })
    // then: timeline 구분에 사용 1건인 Label이 보인다
    await waitFor(() => expect(result.current.labels.data?.find((l) => l.name === '내후년 구매 검토')).toMatchObject({ category: 'timeline', usageCount: 1 }))
  })
})
