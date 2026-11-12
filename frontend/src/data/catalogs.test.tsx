import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it } from 'vitest'
import { gateway } from '../gateway'
import { resetMock } from '../test/fake/default'
import { USER_ID } from '../test/fake/seed/ids'
import { TEST_NOW } from '../test/fake/testing'
import { useCreateActionType, useRemoveActionType, useRenameActionType } from './actionTypes'
import { useCreateLabel, useRemoveLabel, useRenameLabel } from './labels'
import { keys } from './queryKeys'
import { useCreateVendor, useRemoveVendor, useRenameVendor } from './vendors'

const DEAL_LIST = [...keys.deals, 'list', 'cached'] as const
const ACTION_LIST = ['actions', 'cached-deal'] as const

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  // 세 목록 화면과 이름을 보여 주는 Deal·Action 조회가 캐시에 있는 상태
  queryClient.setQueryData(keys.labels, [])
  queryClient.setQueryData(keys.actionTypes, [])
  queryClient.setQueryData(keys.vendors, [])
  queryClient.setQueryData(DEAL_LIST, [])
  queryClient.setQueryData(ACTION_LIST, [])
  const stale = (key: readonly unknown[]) => queryClient.getQueryState(key)?.isInvalidated === true
  return { wrapper, stale }
}

beforeEach(() => {
  resetMock({ now: TEST_NOW, userId: USER_ID.root })
})

describe('선택 목록 변경 뒤 캐시 갱신 (CL-R23)', () => {
  // Label을 등록하면 Label 목록만 다시 읽게 한다.
  // 테스트 코드: CL-093
  it('Label 등록 성공 뒤 Label 목록이 무효화되고 Deal 조회는 그대로다', async () => {
    // given: 세 목록과 Deal·Action 조회 캐시가 있다
    const { wrapper, stale } = setup()
    const { result } = renderHook(() => useCreateLabel(), { wrapper })

    // when: Label 등록이 성공한다
    await act(async () => {
      await result.current.mutateAsync({ category: 'need', name: '규제 대응' })
    })

    // then: Label 목록만 무효화된다
    expect(stale(keys.labels)).toBe(true)
    expect(stale(DEAL_LIST)).toBe(false)
  })

  // Label 이름을 바꾸면 Label 목록과 Label 이름을 보여 주는 Deal 조회를 다시 읽게 한다.
  // 테스트 코드: CL-093
  it('Label 이름 변경 성공 뒤 Label 목록과 Deal 조회가 무효화된다', async () => {
    // given: 세 목록과 Deal·Action 조회 캐시가 있다
    const { wrapper, stale } = setup()
    const { result } = renderHook(() => useRenameLabel(), { wrapper })
    const target = (await gateway.labels.list())[0]
    if (!target) throw new Error('시드 Label이 없습니다.')

    // when: 이름 변경이 성공한다
    await act(async () => {
      await result.current.mutateAsync({ id: target.id, name: '바꾼 이름' })
    })

    // then: Label 목록과 Deal 조회가 무효화된다
    expect(stale(keys.labels)).toBe(true)
    expect(stale(DEAL_LIST)).toBe(true)
  })

  // Label을 삭제하면 Label 목록을 다시 읽게 한다.
  // 테스트 코드: CL-093
  it('Label 삭제 성공 뒤 Label 목록이 무효화된다', async () => {
    // given: 쓰이지 않는 Label과 캐시가 있다
    const { wrapper, stale } = setup()
    const { result } = renderHook(() => useRemoveLabel(), { wrapper })
    const created = await gateway.labels.create('need', '삭제할 Label')

    // when: 삭제가 성공한다
    await act(async () => {
      await result.current.mutateAsync(created.id)
    })

    // then: Label 목록이 무효화된다
    expect(stale(keys.labels)).toBe(true)
  })

  // 유형을 등록하면 유형 목록만 다시 읽게 한다.
  // 테스트 코드: CL-093
  it('유형 등록 성공 뒤 유형 목록이 무효화되고 Action 조회는 그대로다', async () => {
    // given: 세 목록과 Deal·Action 조회 캐시가 있다
    const { wrapper, stale } = setup()
    const { result } = renderHook(() => useCreateActionType(), { wrapper })

    // when: 유형 등록이 성공한다
    await act(async () => {
      await result.current.mutateAsync('웨비나')
    })

    // then: 유형 목록만 무효화된다
    expect(stale(keys.actionTypes)).toBe(true)
    expect(stale(ACTION_LIST)).toBe(false)
  })

  // 유형 이름을 바꾸면 유형 목록과 유형 이름을 보여 주는 Action 조회를 다시 읽게 한다.
  // 테스트 코드: CL-093
  it('유형 이름 변경 성공 뒤 유형 목록과 Action 조회가 무효화된다', async () => {
    // given: 세 목록과 Deal·Action 조회 캐시가 있다
    const { wrapper, stale } = setup()
    const { result } = renderHook(() => useRenameActionType(), { wrapper })
    const target = (await gateway.actionTypes.list())[0]
    if (!target) throw new Error('시드 유형이 없습니다.')

    // when: 이름 변경이 성공한다
    await act(async () => {
      await result.current.mutateAsync({ id: target.id, name: '바꾼 유형' })
    })

    // then: 유형 목록과 Action 조회가 무효화된다
    expect(stale(keys.actionTypes)).toBe(true)
    expect(stale(ACTION_LIST)).toBe(true)
  })

  // 유형을 삭제하면 유형 목록을 다시 읽게 한다.
  // 테스트 코드: CL-093
  it('유형 삭제 성공 뒤 유형 목록이 무효화된다', async () => {
    // given: 쓰이지 않는 유형과 캐시가 있다
    const { wrapper, stale } = setup()
    const { result } = renderHook(() => useRemoveActionType(), { wrapper })
    const created = await gateway.actionTypes.create('삭제할 유형')

    // when: 삭제가 성공한다
    await act(async () => {
      await result.current.mutateAsync(created.id)
    })

    // then: 유형 목록이 무효화된다
    expect(stale(keys.actionTypes)).toBe(true)
  })

  // Vendor를 등록하면 Vendor 목록만 다시 읽게 한다.
  // 테스트 코드: CL-093
  it('Vendor 등록 성공 뒤 Vendor 목록이 무효화되고 Deal 조회는 그대로다', async () => {
    // given: 세 목록과 Deal·Action 조회 캐시가 있다
    const { wrapper, stale } = setup()
    const { result } = renderHook(() => useCreateVendor(), { wrapper })

    // when: Vendor 등록이 성공한다
    await act(async () => {
      await result.current.mutateAsync('Acme')
    })

    // then: Vendor 목록만 무효화된다
    expect(stale(keys.vendors)).toBe(true)
    expect(stale(DEAL_LIST)).toBe(false)
  })

  // Vendor 이름을 바꾸면 Vendor 목록과 Vendor 이름을 보여 주는 Deal 조회를 다시 읽게 한다.
  // 테스트 코드: CL-093
  it('Vendor 이름 변경 성공 뒤 Vendor 목록과 Deal 조회가 무효화된다', async () => {
    // given: 세 목록과 Deal·Action 조회 캐시가 있다
    const { wrapper, stale } = setup()
    const { result } = renderHook(() => useRenameVendor(), { wrapper })
    const target = (await gateway.vendors.list())[0]
    if (!target) throw new Error('시드 Vendor가 없습니다.')

    // when: 이름 변경이 성공한다
    await act(async () => {
      await result.current.mutateAsync({ id: target.id, name: '바꾼 Vendor' })
    })

    // then: Vendor 목록과 Deal 조회가 무효화된다
    expect(stale(keys.vendors)).toBe(true)
    expect(stale(DEAL_LIST)).toBe(true)
  })

  // Vendor를 삭제하면 Vendor 목록을 다시 읽게 한다.
  // 테스트 코드: CL-093
  it('Vendor 삭제 성공 뒤 Vendor 목록이 무효화된다', async () => {
    // given: 쓰이지 않는 Vendor와 캐시가 있다
    const { wrapper, stale } = setup()
    const { result } = renderHook(() => useRemoveVendor(), { wrapper })
    const created = await gateway.vendors.create('삭제할 Vendor')

    // when: 삭제가 성공한다
    await act(async () => {
      await result.current.mutateAsync(created.id)
    })

    // then: Vendor 목록이 무효화된다
    expect(stale(keys.vendors)).toBe(true)
  })
})
