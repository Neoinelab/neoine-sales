import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it } from 'vitest'
import { gateway } from '../gateway'
import { resetMock } from '../test/fake/default'
import { USER_ID } from '../test/fake/seed/ids'
import { TEST_NOW } from '../test/fake/testing'
import { useCreateCode, useRemoveCode, useRenameCode, useReorderCodes } from './codes'
import { keys } from './queryKeys'

const DEAL_LIST = [...keys.deals, 'list', 'cached'] as const
const FORECAST_SUMMARY = [...keys.forecast, 'summary', 'cached'] as const

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  // 코드 화면과 Deal·Forecast 조회가 캐시에 있는 상태
  queryClient.setQueryData(keys.codeSet, { statuses: [], forecasts: [] })
  queryClient.setQueryData(keys.codeList('status'), [])
  queryClient.setQueryData(DEAL_LIST, [])
  queryClient.setQueryData(FORECAST_SUMMARY, {})
  const stale = (key: readonly unknown[]) => queryClient.getQueryState(key)?.isInvalidated === true
  return { wrapper, stale }
}

beforeEach(() => {
  resetMock({ now: TEST_NOW, userId: USER_ID.root })
})

describe('코드 변경 뒤 캐시 갱신 (CD-R23)', () => {
  // 이름 변경이 성공하면 코드 목록·사용 현황·Deal·Forecast 조회를 다시 읽게 한다.
  // 테스트 코드: CD-067
  it('이름 변경 성공 뒤 코드·Deal·Forecast 조회가 무효화된다', async () => {
    // given: 코드 화면과 Deal·Forecast 조회 캐시가 있다
    const { wrapper, stale } = setup()
    const { result } = renderHook(() => useRenameCode(), { wrapper })
    const target = (await gateway.codes.all()).statuses[1]
    if (!target) throw new Error('시드 코드가 없습니다.')

    // when: 이름 변경이 성공한다
    await act(async () => {
      await result.current.mutateAsync({ id: target.id, name: '소개' })
    })

    // then: 코드 목록·사용 현황·Deal·Forecast 조회가 모두 무효화된다
    expect(stale(keys.codeSet)).toBe(true)
    expect(stale(keys.codeList('status'))).toBe(true)
    expect(stale(DEAL_LIST)).toBe(true)
    expect(stale(FORECAST_SUMMARY)).toBe(true)
  })

  // 순서 변경이 성공하면 코드 목록·사용 현황·Deal·Forecast 조회를 다시 읽게 한다.
  // 테스트 코드: CD-067
  it('순서 변경 성공 뒤 코드·Deal·Forecast 조회가 무효화된다', async () => {
    // given: 코드 화면과 Deal·Forecast 조회 캐시가 있다
    const { wrapper, stale } = setup()
    const { result } = renderHook(() => useReorderCodes(), { wrapper })
    const ids = (await gateway.codes.list('status')).map((c) => c.id)

    // when: 순서 변경이 성공한다
    await act(async () => {
      await result.current.mutateAsync({ kind: 'status', orderedIds: [...ids].reverse() })
    })

    // then: 코드 목록·사용 현황·Deal·Forecast 조회가 모두 무효화된다
    expect(stale(keys.codeSet)).toBe(true)
    expect(stale(keys.codeList('status'))).toBe(true)
    expect(stale(DEAL_LIST)).toBe(true)
    expect(stale(FORECAST_SUMMARY)).toBe(true)
  })

  // 추가가 성공하면 코드 조회만 다시 읽게 한다.
  // 테스트 코드: CD-067
  it('추가 성공 뒤에는 코드 조회만 무효화된다', async () => {
    // given: 코드 화면과 Deal·Forecast 조회 캐시가 있다
    const { wrapper, stale } = setup()
    const { result } = renderHook(() => useCreateCode(), { wrapper })

    // when: 코드 추가가 성공한다
    await act(async () => {
      await result.current.mutateAsync({ kind: 'status', name: '내부검토' })
    })

    // then: 코드 조회만 무효화되고 Deal·Forecast 조회는 그대로다
    expect(stale(keys.codeSet)).toBe(true)
    expect(stale(keys.codeList('status'))).toBe(true)
    expect(stale(DEAL_LIST)).toBe(false)
    expect(stale(FORECAST_SUMMARY)).toBe(false)
  })

  // 삭제가 성공하면 코드 조회만 다시 읽게 한다.
  // 테스트 코드: CD-067
  it('삭제 성공 뒤에는 코드 조회만 무효화된다', async () => {
    // given: 코드 화면과 Deal·Forecast 조회 캐시가 있고, 쓰이지 않는 코드를 하나 만들어 둔다
    const created = await gateway.codes.create({ kind: 'status', name: '내부검토' })
    const { wrapper, stale } = setup()
    const { result } = renderHook(() => useRemoveCode(), { wrapper })

    // when: 그 코드 삭제가 성공한다
    await act(async () => {
      await result.current.mutateAsync(created.id)
    })

    // then: 코드 조회만 무효화되고 Deal·Forecast 조회는 그대로다
    expect(stale(keys.codeSet)).toBe(true)
    expect(stale(keys.codeList('status'))).toBe(true)
    expect(stale(DEAL_LIST)).toBe(false)
    expect(stale(FORECAST_SUMMARY)).toBe(false)
  })
})
