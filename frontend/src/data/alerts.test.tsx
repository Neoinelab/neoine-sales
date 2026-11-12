import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it } from 'vitest'
import { resetMock } from '../test/fake/default'
import { TEST_NOW } from '../test/fake/testing'
import { useSaveAlertSettings } from './alerts'
import { useDeals } from './deals'
import { USER_ID } from '../test/fake/seed/ids'

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { wrapper }
}

beforeEach(() => {
  resetMock({ now: TEST_NOW, userId: USER_ID.root })
})

describe('경고 기준 저장 훅 (R3 Minor 4)', () => {
  // 경고 기준 저장에 성공하면 캐시된 Deal 목록의 경고가 새 기준으로 다시 계산된다.
  // 테스트 코드: RK-053
  it('refreshes the cached deal list risk after a successful save', async () => {
    // given: 새론병원 PAM이 stale로 읽힌 Deal 목록이 캐시에 있다
    const { wrapper } = setup()
    const list = renderHook(() => useDeals({ keyword: '새론병원 PAM' }), { wrapper })
    await waitFor(() => expect(list.result.current.data?.items).toHaveLength(1))
    expect(list.result.current.data?.items[0]?.risk).toBe('stale')

    const save = renderHook(() => useSaveAlertSettings(), { wrapper })
    await act(async () => {
      // when: 경고 기준을 365일로 저장한다
      await save.result.current.mutateAsync(365)
    })

    // then: 캐시된 목록 행의 risk가 null이 된다
    await waitFor(() => expect(list.result.current.data?.items[0]?.risk).toBeNull())
  })

  // 저장이 거절되면 캐시된 Deal 목록은 그대로다.
  // 테스트 코드: RK-053
  it('leaves the cached deal list untouched when the save is rejected', async () => {
    // given: Deal 목록이 캐시에 있다
    const { wrapper } = setup()
    const list = renderHook(() => useDeals({ keyword: '새론병원 PAM' }), { wrapper })
    await waitFor(() => expect(list.result.current.data?.items).toHaveLength(1))

    const save = renderHook(() => useSaveAlertSettings(), { wrapper })
    await act(async () => {
      // when: 범위 밖 값(0)을 저장하려 한다
      await expect(save.result.current.mutateAsync(0)).rejects.toMatchObject({ status: 422 })
    })

    // then: 422로 거절되고 목록 행의 risk는 그대로 stale이다
    expect(list.result.current.data?.items[0]?.risk).toBe('stale')
  })
})
