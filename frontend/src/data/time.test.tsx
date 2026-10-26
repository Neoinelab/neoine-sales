import { focusManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clock, gateway } from '../gateway'
import { resetMock } from '../test/fake/default'
import { USER_ID } from '../test/fake/seed/ids'
import { useServerTimeSync } from './time'

/** 서버 시각 동기 훅(시간 기준 서버 통일 AC3·AC4): 켜진 뒤에만 게이트웨이로 시계를 맞춘다. */

const MINUTE = 60_000

/** 실제 타이머로 잠깐 기다려 진행 중인 조회를 끝낸다. */
const settle = () => act(() => new Promise<void>((resolve) => setTimeout(resolve, 40)))

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  return { queryClient, wrapper }
}

beforeEach(() => resetMock({ now: '2026-10-23T09:30:00+09:00', userId: USER_ID.kim }))
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  focusManager.setFocused(undefined)
  resetMock({ now: null })
})

describe('useServerTimeSync', () => {
  it('does not request before it is enabled', async () => {
    const sync = vi.spyOn(clock, 'syncWith')
    const get = vi.spyOn(gateway.time, 'get')
    const { wrapper } = setup()

    const { result } = renderHook(() => useServerTimeSync(false), { wrapper })

    await Promise.resolve()
    expect(sync).not.toHaveBeenCalled()
    expect(get).not.toHaveBeenCalled()
    expect(result.current.data).toBeUndefined()
  })

  it('syncs the clock through the gateway once enabled', async () => {
    const sync = vi.spyOn(clock, 'syncWith')
    const get = vi.spyOn(gateway.time, 'get')
    const { wrapper } = setup()

    const { result } = renderHook(() => useServerTimeSync(true), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(sync).toHaveBeenCalledTimes(1)
    expect(get).toHaveBeenCalledTimes(1)
    expect(result.current.data).toEqual({ now: '2026-10-23T09:30:00+09:00', today: '2026-10-23' })
  })

  it('starts requesting when enabled turns true', async () => {
    const sync = vi.spyOn(clock, 'syncWith')
    const { wrapper } = setup()
    const { result, rerender } = renderHook(({ enabled }: { enabled: boolean }) => useServerTimeSync(enabled), {
      wrapper,
      initialProps: { enabled: false },
    })
    expect(sync).not.toHaveBeenCalled()

    rerender({ enabled: true })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(sync).toHaveBeenCalledTimes(1)
  })

  it('reports a rejected sync as an ApiError without retrying', async () => {
    resetMock({ now: '2026-10-23T09:30:00+09:00', userId: null }) // 로그인하지 않아 401
    const get = vi.spyOn(gateway.time, 'get')
    const { wrapper } = setup()

    const { result } = renderHook(() => useServerTimeSync(true), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.status).toBe(401)
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('syncs again every 30 minutes', async () => {
    // RTL waitFor는 setInterval을 쓰므로 가짜 타이머를 켠 동안은 쓰지 않고, 실제 시간으로 잠깐 기다려 비동기 조회를 마무리한다.
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    const sync = vi.spyOn(clock, 'syncWith')
    const { wrapper } = setup()
    renderHook(() => useServerTimeSync(true), { wrapper })
    await settle()
    expect(sync).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(29 * MINUTE)
    await settle()
    expect(sync).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(2 * MINUTE)
    await settle()

    expect(sync).toHaveBeenCalledTimes(2)
  })

  it('syncs again when the window regains focus after the data went stale', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    const sync = vi.spyOn(clock, 'syncWith')
    const { wrapper } = setup()
    const { result } = renderHook(() => useServerTimeSync(true), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(sync).toHaveBeenCalledTimes(1)

    vi.setSystemTime(Date.now() + 31 * MINUTE)
    focusManager.setFocused(false)
    focusManager.setFocused(true)

    await waitFor(() => expect(sync).toHaveBeenCalledTimes(2))
  })

  it('keeps the previous data when a later sync fails', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    const { wrapper } = setup()
    const { result } = renderHook(() => useServerTimeSync(true), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const first = result.current.data
    vi.spyOn(gateway.time, 'get').mockRejectedValue(new Error('down'))

    vi.setSystemTime(Date.now() + 31 * MINUTE)
    focusManager.setFocused(false)
    focusManager.setFocused(true)

    await waitFor(() => expect(gateway.time.get).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(result.current.isFetching).toBe(false))
    expect(result.current.data).toEqual(first)
  })
})
