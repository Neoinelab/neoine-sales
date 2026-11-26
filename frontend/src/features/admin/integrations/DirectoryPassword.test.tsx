import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { DIRECTORY_SAVED } from '../../../test/directoryFixtures'
import { passDirectoryTest, setField } from '../../../test/directoryForm'
import { renderAt } from '../../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

describe('AD 테스트 계정의 휘발성 입력', () => {
  // 테스트 코드: IN-076
  it('creates the first connection using a tested proof and a null revision', async () => {
    vi.spyOn(gateway.settings, 'getDirectory').mockResolvedValue(null)
    vi.spyOn(gateway.settings, 'testDirectory').mockResolvedValue({ baseDn: 'dc=corp,dc=test', testToken: 'first-proof' })
    const save = vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue({ ...DIRECTORY_SAVED, revision: 1 })
    const { user } = await renderAt('/admin/integrations', { role: 'admin' })
    await screen.findByLabelText('호스트')
    setField('호스트', 'new.corp.test')
    await passDirectoryTest(user)
    await user.click(within(screen.getByRole('region', { name: 'AD(LDAP) 서버 설정' })).getByRole('button', { name: '저장' }))
    await screen.findByText('저장했습니다.')
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ testToken: 'first-proof', host: 'new.corp.test' }), { expectedRevision: null })
  })
  // 테스트 코드: IN-059, IN-062, IN-065, IN-067, IN-087
  it('asks for credentials only in the test dialog and saves only the proof', async () => {
    const save = vi.spyOn(gateway.settings, 'saveDirectory')
    const test = vi.spyOn(gateway.settings, 'testDirectory')
    const { user } = await renderAt('/admin/integrations', { role: 'admin' })
    await screen.findByLabelText(/^호스트/)
    expect(screen.queryByLabelText(/바인드/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/현재 관리자 비밀번호/)).not.toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'AD(LDAP) 서버 설정' })).getByRole('button', { name: '저장' })).toBeDisabled()
    expect(screen.getByLabelText('호스트')).toHaveValue('dc1.corp.test')
    await passDirectoryTest(user)
    expect(save).not.toHaveBeenCalled()
    expect(test).toHaveBeenCalledWith(expect.objectContaining({ bindAccount: 'operator', bindPassword: 'Svc-Dummy-pw-1!' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(within(screen.getByRole('region', { name: 'AD(LDAP) 서버 설정' })).getByRole('button', { name: '저장' }))
    await screen.findByText('저장했습니다.')
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ testToken: expect.any(String) }), expect.objectContaining({ expectedRevision: expect.any(Number) }))
    const sent = save.mock.calls[0]?.[0]
    expect(sent).not.toHaveProperty('bindAccount')
    expect(sent).not.toHaveProperty('bindPassword')
    expect(JSON.stringify(sent)).not.toContain('Svc-Dummy-pw-1!')
    await user.click(screen.getByRole('button', { name: '연결 테스트' }))
    expect(screen.queryByText('저장했습니다.')).not.toBeInTheDocument()
  })
  it('clears cancelled credentials and invalidates the proof when the endpoint changes', async () => {
    const { user } = await renderAt('/admin/integrations', { role: 'admin' })
    await screen.findByLabelText(/^호스트/)
    await user.click(screen.getByRole('button', { name: '연결 테스트' }))
    setField(/^바인드 계정/, 'private-account')
    setField(/^바인드 비밀번호/, 'private-password')
    await user.click(screen.getByRole('button', { name: '취소' }))
    await user.click(screen.getByRole('button', { name: '연결 테스트' }))
    expect(screen.getByLabelText(/^바인드 계정/)).toHaveValue('')
    expect(screen.getByLabelText(/^바인드 비밀번호/)).toHaveValue('')
    await user.click(screen.getByRole('button', { name: '취소' }))
    await passDirectoryTest(user)
    expect(within(screen.getByRole('region', { name: 'AD(LDAP) 서버 설정' })).getByRole('button', { name: '저장' })).toBeEnabled()
    setField(/^호스트/, 'other.corp.test')
    await waitFor(() => expect(within(screen.getByRole('region', { name: 'AD(LDAP) 서버 설정' })).getByRole('button', { name: '저장' })).toBeDisabled())
  })
})
