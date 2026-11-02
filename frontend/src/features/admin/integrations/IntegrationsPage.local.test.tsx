import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderLocalAt } from '../../../test/localAccounts'
import { renderAt } from '../../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

/** 앱에서 계정을 직접 관리하는 시스템의 외부연동: AD 설정 대신 안내를 보인다 (AC-13). */
describe('외부연동: local 모드', () => {
  it('shows the guidance instead of the AD settings section', async () => {
    await renderLocalAt('/admin/integrations', { role: 'admin' })

    expect(await screen.findByText(/앱에서 계정을 직접 관리합니다/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'AD(LDAP) 서버 설정' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/^호스트/)).not.toBeInTheDocument()
  })

  it('does not read the AD settings from the server', async () => {
    const read = vi.spyOn(gateway.settings, 'getDirectory')

    await renderLocalAt('/admin/integrations', { role: 'admin' })
    await screen.findByText(/앱에서 계정을 직접 관리합니다/)

    expect(read).not.toHaveBeenCalled()
  })

  it('keeps the storage section as it is', async () => {
    await renderLocalAt('/admin/integrations', { role: 'admin' })

    expect(await screen.findByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
    expect(await screen.findByLabelText('저장 경로')).toBeInTheDocument()
  })

  it('keeps the AD settings section in AD mode and shows no guidance', async () => {
    await renderAt('/admin/integrations', { role: 'admin' })

    expect(await screen.findByRole('heading', { name: 'AD(LDAP) 서버 설정' })).toBeInTheDocument()
    expect(screen.queryByText(/앱에서 계정을 직접 관리합니다/)).not.toBeInTheDocument()
  })
})
