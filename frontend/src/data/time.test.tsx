import { focusManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clock, gateway } from '../gateway'
import { resetMock } from '../test/fake/default'
import { USER_ID } from '../test/fake/seed/ids'
import { useServerTimeSync } from './time'

/** 서버 시각 동기 훅: 켜진 뒤에만 게이트웨이로 시계를 맞춘다. */

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
  // 훅이 꺼져 있으면 서버 시각을 요청하지 않는다.
  // 테스트 코드: TM-031
  it('does not request before it is enabled', async () => {
    // given: 시계 동기와 게이트웨이 감시
    const sync = vi.spyOn(clock, 'syncWith')
    const get = vi.spyOn(gateway.time, 'get')
    const { wrapper } = setup()

    // when: enabled=false로 훅을 렌더한다
    const { result } = renderHook(() => useServerTimeSync(false), { wrapper })

    // then: 요청 0회, 데이터 없음
    await Promise.resolve()
    expect(sync).not.toHaveBeenCalled()
    expect(get).not.toHaveBeenCalled()
    expect(result.current.data).toBeUndefined()
  })

  // 켜지면 게이트웨이로 시계를 한 번 맞춘다.
  it('syncs the clock through the gateway once enabled', async () => {
    // given: 시계 동기와 게이트웨이 감시
    const sync = vi.spyOn(clock, 'syncWith')
    const get = vi.spyOn(gateway.time, 'get')
    const { wrapper } = setup()

    // when: enabled=true로 훅을 렌더한다
    const { result } = renderHook(() => useServerTimeSync(true), { wrapper })

    // then: 시계 동기와 서버 시각 요청이 1회씩이고 데이터는 서버 시각이다
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(sync).toHaveBeenCalledTimes(1)
    expect(get).toHaveBeenCalledTimes(1)
    expect(result.current.data).toEqual({ now: '2026-10-23T09:30:00+09:00', today: '2026-10-23' })
  })

  // 켜지는 순간 1회 요청한다.
  // 테스트 코드: TM-031
  it('starts requesting when enabled turns true', async () => {
    // given: 꺼진 채로 렌더한 훅(요청 없음)
    const sync = vi.spyOn(clock, 'syncWith')
    const { wrapper } = setup()
    const { result, rerender } = renderHook(({ enabled }: { enabled: boolean }) => useServerTimeSync(enabled), {
      wrapper,
      initialProps: { enabled: false },
    })
    expect(sync).not.toHaveBeenCalled()

    // when: enabled가 true가 된다
    rerender({ enabled: true })

    // then: 1회 동기한다
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(sync).toHaveBeenCalledTimes(1)
  })

  // 거절된 동기는 ApiError로 보고하고 재시도하지 않는다.
  // 테스트 코드: TM-031, TM-033
  it('reports a rejected sync as an ApiError without retrying', async () => {
    // given: 로그인하지 않아 서버 시각이 401이다
    resetMock({ now: '2026-10-23T09:30:00+09:00', userId: null })
    const get = vi.spyOn(gateway.time, 'get')
    const { wrapper } = setup()

    // when: 훅을 켠다
    const { result } = renderHook(() => useServerTimeSync(true), { wrapper })

    // then: 401 오류이고 요청은 1회뿐이다
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.status).toBe(401)
    expect(get).toHaveBeenCalledTimes(1)
  })

  // 30분마다 다시 동기한다.
  // 테스트 코드: TM-034
  it('syncs again every 30 minutes', async () => {
    // given: 첫 동기가 끝났다
    // RTL waitFor는 setInterval을 쓰므로 가짜 타이머를 켠 동안은 쓰지 않고, 실제 시간으로 잠깐 기다려 비동기 조회를 마무리한다.
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    const sync = vi.spyOn(clock, 'syncWith')
    const { wrapper } = setup()
    renderHook(() => useServerTimeSync(true), { wrapper })
    await settle()
    expect(sync).toHaveBeenCalledTimes(1)

    // when: 29분이 지나고, 이어서 2분이 더 지난다
    vi.advanceTimersByTime(29 * MINUTE)
    await settle()
    expect(sync).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(2 * MINUTE)
    await settle()

    // then: 29분 시점까지 1회, 31분 시점에 2회다
    expect(sync).toHaveBeenCalledTimes(2)
  })

  // 30분이 지난 뒤 창에 포커스가 돌아오면 다시 동기한다.
  // 테스트 코드: TM-035
  it('syncs again when the window regains focus after the data went stale', async () => {
    // given: 첫 동기가 끝났다
    vi.useFakeTimers({ toFake: ['Date'] })
    const sync = vi.spyOn(clock, 'syncWith')
    const { wrapper } = setup()
    const { result } = renderHook(() => useServerTimeSync(true), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(sync).toHaveBeenCalledTimes(1)

    // when: 31분 뒤 창이 포커스를 잃었다가 되찾는다
    vi.setSystemTime(Date.now() + 31 * MINUTE)
    focusManager.setFocused(false)
    focusManager.setFocused(true)

    // then: 동기가 한 번 더 일어난다(합 2회)
    await waitFor(() => expect(sync).toHaveBeenCalledTimes(2))
  })

  // 재동기가 실패해도 직전 값이 유지된다.
  // 테스트 코드: TM-036
  it('keeps the previous data when a later sync fails', async () => {
    // given: 첫 동기가 끝났고 이후 서버 시각 요청은 실패한다
    vi.useFakeTimers({ toFake: ['Date'] })
    const { wrapper } = setup()
    const { result } = renderHook(() => useServerTimeSync(true), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const first = result.current.data
    vi.spyOn(gateway.time, 'get').mockRejectedValue(new Error('down'))

    // when: 31분 뒤 포커스가 돌아와 재동기가 실패한다
    vi.setSystemTime(Date.now() + 31 * MINUTE)
    focusManager.setFocused(false)
    focusManager.setFocused(true)

    // then: 훅의 데이터는 첫 동기 값 그대로다
    await waitFor(() => expect(gateway.time.get).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(result.current.isFetching).toBe(false))
    expect(result.current.data).toEqual(first)
  })
})
