import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it } from 'vitest'
import { resetMock } from '../test/fake/default'
import { TEST_NOW } from '../test/fake/testing'
import { useSaveAlertSettings } from './alerts'
import { useDeals } from './deals'

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { wrapper }
}

beforeEach(() => {
  resetMock({ now: TEST_NOW, userId: 'u-root' })
})

describe('경고 기준 저장 훅 (R3 Minor 4)', () => {
  it('refreshes the cached deal list risk after a successful save', async () => {
    const { wrapper } = setup()
    const list = renderHook(() => useDeals({ keyword: '새론병원 PAM' }), { wrapper })
    await waitFor(() => expect(list.result.current.data?.items).toHaveLength(1))
    expect(list.result.current.data?.items[0]?.risk).toBe('stale')

    const save = renderHook(() => useSaveAlertSettings(), { wrapper })
    await act(async () => {
      await save.result.current.mutateAsync(365)
    })

    await waitFor(() => expect(list.result.current.data?.items[0]?.risk).toBeNull())
  })

  it('leaves the cached deal list untouched when the save is rejected', async () => {
    const { wrapper } = setup()
    const list = renderHook(() => useDeals({ keyword: '새론병원 PAM' }), { wrapper })
    await waitFor(() => expect(list.result.current.data?.items).toHaveLength(1))

    const save = renderHook(() => useSaveAlertSettings(), { wrapper })
    await act(async () => {
      await expect(save.result.current.mutateAsync(0)).rejects.toMatchObject({ status: 422 })
    })

    expect(list.result.current.data?.items[0]?.risk).toBe('stale')
  })
})
