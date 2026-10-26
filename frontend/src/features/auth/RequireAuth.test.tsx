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
 * 첫 동기가 실패하면 오류 배너가 보인다. 이후 재동기 실패는 화면을 막지 않는다(시간 기준 서버 통일 AC3·AC4).
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
  it('holds the layout until the server time arrives', async () => {
    const time = deferredTime()
    await renderAt('/deals')
    await waitFor(() => expect(time.spy).toHaveBeenCalledTimes(1))

    expect(screen.getByText('불러오는 중…')).toBeVisible()
    expect(screen.queryByRole('navigation', NAV)).not.toBeInTheDocument()

    time.resolve(SERVER_TIME)

    expect(await screen.findByRole('navigation', NAV)).toBeVisible()
  })

  it('shows an error and no layout when the first sync fails', async () => {
    const time = deferredTime()
    await renderAt('/deals')
    await waitFor(() => expect(time.spy).toHaveBeenCalledTimes(1))

    time.reject(new ApiError(500, { type: 'about:blank', title: '서버 오류', status: 500, detail: '서버 시각을 불러오지 못했습니다.' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('서버 시각을 불러오지 못했습니다.')
    expect(screen.queryByRole('navigation', NAV)).not.toBeInTheDocument()
  })

  it('does not request the server time before login is confirmed', async () => {
    const time = deferredTime()
    const { location } = await renderAt('/deals', { role: null })

    await waitFor(() => expect(location()).toBe('/login'))
    expect(time.spy).not.toHaveBeenCalled()
  })

  it('requests the server time once for a logged-in session', async () => {
    const spy = vi.spyOn(gateway.time, 'get')
    await renderAt('/deals')
    await screen.findByRole('navigation', NAV)

    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('keeps the layout when a later resync fails', async () => {
    const { client } = await renderAt('/deals')
    await screen.findByRole('navigation', NAV)
    vi.spyOn(gateway.time, 'get').mockRejectedValue(new ApiError(503, { type: 'about:blank', title: '점검', status: 503, detail: '일시적 오류' }))

    await client.invalidateQueries({ queryKey: keys.serverTime })

    expect(screen.getByRole('navigation', NAV)).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
