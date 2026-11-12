import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { keys } from '../../data/queryKeys'
import { gateway } from '../../gateway'
import type { ServerTime } from '../../gateway/types'
import { ApiError } from '../../shared/api/problem'
import { resetMock } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'

/**
 * 로그인 뒤 서버 시각 첫 응답 전에는 로그인 후 화면 대신 "불러오는 중…"이 보이고(D3),
 * 첫 동기가 실패하면 오류 배너가 보인다. 이후 재동기 실패는 화면을 막지 않는다.
 */

afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const NAV = { name: '주 메뉴' }
const SERVER_TIME: ServerTime = { now: '2026-10-23T09:30:00+09:00', today: '2026-10-23' }

/** 직접 풀어 줄 때까지 끝나지 않는 서버 시각 응답. */
function deferredTime() {
  let resolve!: (value: ServerTime) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<ServerTime>((res, rej) => {
    resolve = res
    reject = rej
  })
  const spy = vi.spyOn(gateway.time, 'get').mockReturnValue(promise)
  return { spy, resolve, reject }
}

describe('RequireAuth와 서버 시각', () => {
  // 첫 동기 응답 전에는 레이아웃 대신 불러오는 중을 보인다.
  // 테스트 코드: TM-032
  it('holds the layout until the server time arrives', async () => {
    // given: 로그인했고 서버 시각 응답이 아직 오지 않았다
    const time = deferredTime()
    // when: /deals를 연다
    await renderAt('/deals')
    await waitFor(() => expect(time.spy).toHaveBeenCalledTimes(1))

    // then: "불러오는 중…"이 보이고 주 메뉴는 없다
    expect(screen.getByText('불러오는 중…')).toBeVisible()
    expect(screen.queryByRole('navigation', NAV)).not.toBeInTheDocument()

    // when: 서버 시각 응답이 온다
    time.resolve(SERVER_TIME)

    // then: 주 메뉴가 보인다
    expect(await screen.findByRole('navigation', NAV)).toBeVisible()
  })

  // 첫 동기가 실패하면 레이아웃 없이 오류 배너를 보이고 재시도하지 않는다.
  // 테스트 코드: TM-033
  it('shows an error and no layout when the first sync fails', async () => {
    // given: 로그인했고 /deals를 열어 서버 시각을 기다린다
    const time = deferredTime()
    await renderAt('/deals')
    await waitFor(() => expect(time.spy).toHaveBeenCalledTimes(1))

    // when: 서버 시각 요청이 500으로 실패한다
    time.reject(new ApiError(500, { type: 'about:blank', title: '서버 오류', status: 500, detail: '서버 시각을 불러오지 못했습니다.' }))

    // then: 오류 배너가 보이고 주 메뉴는 없으며 요청은 1회뿐이다
    expect(await screen.findByRole('alert')).toHaveTextContent('서버 시각을 불러오지 못했습니다.')
    expect(screen.queryByRole('navigation', NAV)).not.toBeInTheDocument()
    expect(time.spy).toHaveBeenCalledTimes(1)
  })

  // 로그인하지 않았으면 서버 시각을 요청하지 않고 로그인 화면으로 간다.
  // 테스트 코드: TM-031
  it('does not request the server time before login is confirmed', async () => {
    // given: 로그인하지 않았다
    const time = deferredTime()
    // when: /deals를 연다
    const { location } = await renderAt('/deals', { role: null })

    // then: /login으로 이동하고 서버 시각 요청은 0회다
    await waitFor(() => expect(location()).toBe('/login'))
    expect(time.spy).not.toHaveBeenCalled()
  })

  // 로그인 세션의 첫 화면 진입에서 서버 시각 요청은 1회다.
  // 테스트 코드: TM-032
  it('requests the server time once for a logged-in session', async () => {
    // given: 로그인했다
    const spy = vi.spyOn(gateway.time, 'get')
    // when: /deals를 열어 레이아웃이 보일 때까지 기다린다
    await renderAt('/deals')
    await screen.findByRole('navigation', NAV)

    // then: 서버 시각 요청은 1회다
    expect(spy).toHaveBeenCalledTimes(1)
  })

  // 재동기가 실패해도 레이아웃이 유지된다.
  // 테스트 코드: TM-036
  it('keeps the layout when a later resync fails', async () => {
    // given: 첫 동기가 끝나 레이아웃이 보이고, 이후 서버 시각 요청은 503으로 실패한다
    const { client } = await renderAt('/deals')
    await screen.findByRole('navigation', NAV)
    vi.spyOn(gateway.time, 'get').mockRejectedValue(new ApiError(503, { type: 'about:blank', title: '점검', status: 503, detail: '일시적 오류' }))

    // when: 서버 시각을 다시 동기한다
    await client.invalidateQueries({ queryKey: keys.serverTime })

    // then: 주 메뉴가 계속 보이고 오류 배너는 없다
    expect(screen.getByRole('navigation', NAV)).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
