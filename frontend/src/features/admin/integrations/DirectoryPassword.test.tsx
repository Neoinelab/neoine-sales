import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

async function openIntegrations() {
  const view = await renderAt('/admin/integrations', { role: 'admin' })
  await screen.findByLabelText(/^호스트/)
  return view
}

function directory() {
  return within(screen.getByRole('region', { name: 'AD(LDAP) 서버 설정' }))
}

describe('외부연동 AD 설정의 관리자 비밀번호 확인 (AC-27)', () => {
  it('asks for the current admin password as a masked field', async () => {
    await openIntegrations()

    const password = directory().getByLabelText(/현재 관리자 비밀번호/)
    expect(password).toHaveAttribute('type', 'password')
    expect(password).toHaveValue('')
  })

  it('sends the password and the loaded revision when saving', async () => {
    const save = vi.spyOn(gateway.settings, 'saveDirectory')
    const { user } = await openIntegrations()
    const revision = Number(/설정 버전 (\d+)/.exec(directory().getByText(/설정 버전 \d+/).textContent ?? '')?.[1])

    await user.type(directory().getByLabelText(/현재 관리자 비밀번호/), 'pw-root')
    await user.click(directory().getByRole('button', { name: '저장' }))

    await directory().findByText('저장했습니다')
    expect(save).toHaveBeenCalledWith(expect.anything(), { password: 'pw-root', expectedRevision: revision })
  })

  it('sends the password when testing the connection, without saving', async () => {
    const test = vi.spyOn(gateway.settings, 'testDirectory')
    const save = vi.spyOn(gateway.settings, 'saveDirectory')
    const { user } = await openIntegrations()

    await user.type(directory().getByLabelText(/현재 관리자 비밀번호/), 'pw-root')
    await user.click(directory().getByRole('button', { name: '연결 테스트' }))

    await directory().findByText('연결 테스트에 성공했습니다.')
    expect(test).toHaveBeenCalledWith(expect.anything(), 'pw-root')
    expect(save).not.toHaveBeenCalled()
  })

  it('sends null when the password is left empty (dev-login admin)', async () => {
    const test = vi.spyOn(gateway.settings, 'testDirectory')
    const { user } = await openIntegrations()

    await user.click(directory().getByRole('button', { name: '연결 테스트' }))

    await directory().findByText('연결 테스트에 성공했습니다.')
    expect(test).toHaveBeenCalledWith(expect.anything(), null)
  })

  it('empties the password field once the request ends, on success and on failure', async () => {
    const { user } = await openIntegrations()
    const field = directory().getByLabelText(/현재 관리자 비밀번호/)

    await user.type(field, 'pw-1')
    await user.click(directory().getByRole('button', { name: '저장' }))
    await directory().findByText('저장했습니다')
    expect(field).toHaveValue('')

    const failure = new ApiError(422, { type: 'https://x/problems/validation', title: 't', status: 422, detail: '비밀번호가 올바르지 않습니다.' })
    vi.spyOn(gateway.settings, 'testDirectory').mockRejectedValue(failure)
    await user.type(field, 'pw-2')
    await user.click(directory().getByRole('button', { name: '연결 테스트' }))
    await directory().findByRole('alert')
    expect(field).toHaveValue('')
  })
})
