import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderAt } from '../../test/mockApp'

afterEach(() => vi.unstubAllEnvs())

describe('목업 배너·패널은 mock 모드에서만 (AC-27)', () => {
  it('draws the banner and the mock menu in mock mode', async () => {
    vi.stubEnv('VITE_GATEWAY', 'mock')
    await renderAt('/login', { role: null })

    expect(await screen.findByRole('region', { name: '목업 안내' })).toBeVisible()
    expect(screen.getByRole('button', { name: '목업 메뉴' })).toBeVisible()
  })

  it('draws neither on the login screen in http mode', async () => {
    vi.stubEnv('VITE_GATEWAY', 'http')
    await renderAt('/login', { role: null })
    await screen.findByRole('button', { name: '로그인' })

    expect(screen.queryByRole('region', { name: '목업 안내' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '목업 메뉴' })).not.toBeInTheDocument()
    expect(screen.queryByText(/UI 목업/)).not.toBeInTheDocument()
  })
})

describe('목업 배너는 최초 설정 화면에서도 mock 모드에서만 (AC-27)', () => {
  it('draws no banner on the setup screen in http mode', async () => {
    vi.stubEnv('VITE_GATEWAY', 'http')
    await renderAt('/setup', { role: null })
    // 시드는 설정이 끝난 상태라 /setup은 로그인 화면으로 넘어간다. 어느 화면이든 배너는 없어야 한다.
    await screen.findByRole('button', { name: '로그인' })

    expect(screen.queryByRole('region', { name: '목업 안내' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '목업 메뉴' })).not.toBeInTheDocument()
  })
})
