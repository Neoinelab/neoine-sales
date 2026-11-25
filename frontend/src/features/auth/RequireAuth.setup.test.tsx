import { waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockControl } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('로그인하지 않은 방문자의 보호 화면', () => {
  it.each(['/login', '/deals'])('로그인된 관리자도 %s에서 재설정이 필요하면 설정 화면으로 간다', async (path) => {
    const reset = mockControl.resetData.bind(mockControl)
    vi.spyOn(mockControl, 'resetData').mockImplementation(() => {
      reset()
      mockControl.restartSetup()
    })
    const { location } = await renderAt(path, { role: 'admin' })
    await waitFor(() => expect(location()).toBe('/setup'))
  })

  it.each(['/deals', '/admin/users'])(
    '로그인하지 않은 방문자가 %s를 열면 최초 설정이 필요할 때 설정 화면으로 간다',
    async (path) => {
      // given: renderAt이 데이터를 초기화하므로, 초기화 뒤에 최초 설정이 안 된 상태로 되돌린다
      const reset = mockControl.resetData.bind(mockControl)
      vi.spyOn(mockControl, 'resetData').mockImplementation(() => {
        reset()
        mockControl.restartSetup()
      })
      // when: 보호 화면을 연다 (전제: 로그인하지 않음, 최초 설정 전)
      const { location } = await renderAt(path, { role: null })

      // then: 주소가 /setup이 된다
      await waitFor(() => expect(location()).toBe('/setup'))
    },
  )

  // 최초 설정이 끝났으면 로그인하지 않은 방문자는 보호 화면에서 로그인 화면으로 간다.
  // 테스트 코드: PL-051
  it.each(['/deals', '/admin/users'])('로그인하지 않은 방문자가 %s를 열면 최초 설정이 끝난 뒤에는 로그인 화면으로 간다', async (path) => {
    // when: 보호 화면을 연다 (전제: 로그인하지 않음, 최초 설정은 끝남)
    const { location } = await renderAt(path, { role: null })
    // then: 주소가 /login이 된다
    await waitFor(() => expect(location()).toBe('/login'))
  })
})
