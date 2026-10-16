import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { renderAt } from '../../test/mockApp'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
})

describe('로그인 화면의 서버 설정 반영 (AC-27)', () => {
  it('draws the quick login buttons when the server allows dev login', async () => {
    vi.spyOn(gateway.auth, 'config').mockResolvedValue({ quickLogin: true, needsSetup: false })
    await renderAt('/login', { role: null })

    expect(await screen.findByRole('region', { name: '빠른 로그인' })).toBeVisible()
    expect(screen.getByRole('button', { name: '관리자 최관리' })).toBeVisible()
  })

  it('draws no quick login when the server switches dev login off', async () => {
    vi.spyOn(gateway.auth, 'config').mockResolvedValue({ quickLogin: false, needsSetup: false })
    await renderAt('/login', { role: null })

    await screen.findByRole('button', { name: '로그인' })
    expect(screen.queryByRole('region', { name: '빠른 로그인' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '관리자 최관리' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('아이디')).toBeVisible()
    expect(screen.queryByRole('link', { name: /최초 설정/ })).not.toBeInTheDocument()
  })

  it('sends the visitor to the first-time setup when the server still needs it', async () => {
    vi.spyOn(gateway.auth, 'config').mockResolvedValue({ quickLogin: false, needsSetup: true })
    const { location } = await renderAt('/login', { role: null })

    await waitFor(() => expect(location()).toBe('/setup'))
  })

  it('keeps the login form and offers a setup link when dev login is on', async () => {
    vi.spyOn(gateway.auth, 'config').mockResolvedValue({ quickLogin: true, needsSetup: true })
    const { location } = await renderAt('/login', { role: null })

    expect(await screen.findByRole('link', { name: /최초 설정/ })).toHaveAttribute('href', '/setup')
    expect(location()).toBe('/login')
    expect(screen.getByRole('region', { name: '빠른 로그인' })).toBeVisible()
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

  it('says any password works only in mock mode', async () => {
    vi.stubEnv('VITE_GATEWAY', 'http')
    await renderAt('/login', { role: null })

    await screen.findByRole('button', { name: '로그인' })
    expect(screen.queryByText(/아무 비밀번호나 입력해도 됩니다/)).not.toBeInTheDocument()
  })
})
