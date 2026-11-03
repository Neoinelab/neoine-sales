import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { mockControl } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'

afterEach(() => {
  vi.restoreAllMocks()
})

/** renderAt이 데이터를 초기화하므로, 초기화 뒤에 최초 설정이 안 된 상태로 되돌린다. */
function needSetup() {
  const reset = mockControl.resetData.bind(mockControl)
  vi.spyOn(mockControl, 'resetData').mockImplementation(() => {
    reset()
    mockControl.restartSetup()
  })
}

describe('로그인 화면의 서버 설정 반영 (AC-27)', () => {
  it('shows no quick login area, only the id and password form', async () => {
    await renderAt('/login', { role: null })

    await screen.findByRole('button', { name: '로그인' })
    expect(screen.queryByRole('region', { name: '빠른 로그인' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '관리자' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '영업' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '조회자' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('아이디')).toBeVisible()
    expect(screen.queryByRole('link', { name: /최초 설정/ })).not.toBeInTheDocument()
  })

  it('always sends the visitor to the first-time setup when the server needs it', async () => {
    needSetup()
    const { location } = await renderAt('/login', { role: null })

    await waitFor(() => expect(location()).toBe('/setup'))
    expect(screen.queryByLabelText('아이디')).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '빠른 로그인' })).not.toBeInTheDocument()
  })

  it('asks the browser for the right autofill on the login fields', async () => {
    await renderAt('/login', { role: null })

    expect(await screen.findByLabelText('아이디')).toHaveAttribute('autocomplete', 'username')
    expect(screen.getByLabelText('비밀번호')).toHaveAttribute('autocomplete', 'current-password')
  })

  it('still shows the form and the reason when the config cannot be read', async () => {
    await gateway.auth.logout()
    const error = await gateway.auth.me().catch((e: unknown) => e)
    vi.spyOn(gateway.auth, 'config').mockRejectedValue(error)
    await renderAt('/login', { role: null })

    expect(await screen.findByRole('alert')).toHaveTextContent('로그인이 필요합니다.')
    expect(screen.getByRole('button', { name: '로그인' })).toBeVisible()
    expect(screen.queryByRole('region', { name: '빠른 로그인' })).not.toBeInTheDocument()
  })

  it('never says any password works', async () => {
    await renderAt('/login', { role: null })

    await screen.findByRole('button', { name: '로그인' })
    expect(screen.queryByText(/아무 비밀번호나 입력해도 됩니다/)).not.toBeInTheDocument()
  })
})
