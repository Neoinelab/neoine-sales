import { waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockControl } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('로그인하지 않은 방문자의 보호 화면 (AC-12)', () => {
  it.each(['/deals', '/admin/users'])(
    'sends an anonymous visitor of %s to the setup when the first-time setup is still needed',
    async (path) => {
      // renderAt이 데이터를 초기화하므로, 초기화 뒤에 최초 설정이 안 된 상태로 되돌린다.
      const reset = mockControl.resetData.bind(mockControl)
      vi.spyOn(mockControl, 'resetData').mockImplementation(() => {
        reset()
        mockControl.restartSetup()
      })
      const { location } = await renderAt(path, { role: null })

      await waitFor(() => expect(location()).toBe('/setup'))
    },
  )

  it.each(['/deals', '/admin/users'])('sends an anonymous visitor of %s to the login when the setup is done', async (path) => {
    const { location } = await renderAt(path, { role: null })

    await waitFor(() => expect(location()).toBe('/login'))
  })
})
