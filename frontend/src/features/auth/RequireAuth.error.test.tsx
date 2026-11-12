import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { resetMock } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'

afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

describe('RequireAuth: 내 정보 조회 오류', () => {
  // 내 정보 조회가 401이 아닌 오류면 오류 배너만 보이고 레이아웃이 없다.
  // 테스트 코드: PL-052
  it.each([
    ['500 서버 오류', new ApiError(500, { type: 'about:blank', title: '서버 오류', status: 500, detail: '내 정보를 불러오지 못했습니다.' }), '내 정보를 불러오지 못했습니다.'],
    ['네트워크 오류', new ApiError(0, { type: 'about:blank', title: 'Network Error', status: 0, detail: '서버에 연결할 수 없습니다.' }), '서버에 연결할 수 없습니다.'],
  ])('shows only an error banner for %s and keeps the address', async (_name, failure, message) => {
    // given: 내 정보 조회가 401이 아닌 오류로 실패한다
    vi.spyOn(gateway.auth, 'me').mockRejectedValue(failure)
    // when: /deals를 연다
    const { location } = await renderAt('/deals')
    // then: 오류 배너가 보이고 주 메뉴가 없으며 주소는 /login으로 바뀌지 않는다
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.queryByRole('navigation', { name: '주 메뉴' })).not.toBeInTheDocument()
    await waitFor(() => expect(location()).not.toBe('/login'))
    expect(location()).toBe('/deals')
  })
})
