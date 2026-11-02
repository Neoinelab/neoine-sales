import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { USER_ID } from '../../../test/fake/seed/ids'
import { renderLocalAt } from '../../../test/localAccounts'
import { renderAt } from '../../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

type Rendered = Awaited<ReturnType<typeof renderAt>>

async function openUsers(local: boolean) {
  const view = await (local ? renderLocalAt : renderAt)('/admin/users', { role: 'admin' })
  await screen.findByRole('cell', { name: 'kim' })
  return view
}

const rowOf = (loginId: string) => screen.getByRole('row', { name: new RegExp(`^${loginId}\\b`) })
const dialog = async (name: string) => within(await screen.findByRole('dialog', { name }))

async function replace(user: Rendered['user'], scope: ReturnType<typeof within>, label: string, text: string) {
  const field = scope.getByLabelText(label)
  await user.clear(field)
  if (text) await user.type(field, text)
}

describe('사용자 목록의 이메일·전화번호 열 (AC-6)', () => {
  it('lists the email and phone columns and "-" for a missing value', async () => {
    await openUsers(true)

    expect(screen.getByRole('columnheader', { name: '이메일' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '전화번호' })).toBeInTheDocument()
    const kim = within(rowOf('kim'))
    expect(kim.getByText('kim@neoine.test')).toBeInTheDocument()
    expect(kim.getAllByText('-').length).toBeGreaterThanOrEqual(1) // 전화번호 없음
  })

  it('shows a saved phone on the row', async () => {
    const { client } = await openUsers(true)

    await gateway.users.update(USER_ID.kim, { phone: '010-1234-5678' })
    await client.invalidateQueries()

    expect(await within(rowOf('kim')).findByText('010-1234-5678')).toBeInTheDocument()
  })
})

describe('정보 수정 (AC-8)', () => {
  it('offers 정보 수정 on other users but not on the signed-in admin row', async () => {
    await openUsers(true)

    expect(within(rowOf('kim')).getByRole('button', { name: '정보 수정' })).toBeInTheDocument()
    expect(within(rowOf('root')).queryByRole('button', { name: '정보 수정' })).not.toBeInTheDocument()
  })

  it('opens a dialog filled with the current values', async () => {
    const { user } = await openUsers(true)

    await user.click(within(rowOf('kim')).getByRole('button', { name: '정보 수정' }))

    const d = await dialog('정보 수정')
    expect(d.getByLabelText('이름')).toHaveValue('김영업')
    expect(d.getByLabelText('이메일')).toHaveValue('kim@neoine.test')
    expect(d.getByLabelText('전화번호')).toHaveValue('')
    expect(d.getByLabelText('이름')).toBeEnabled()
  })

  it('saves only the changed fields, closes the dialog and refreshes the row', async () => {
    const { user } = await openUsers(true)
    const update = vi.spyOn(gateway.users, 'update')
    await user.click(within(rowOf('kim')).getByRole('button', { name: '정보 수정' }))
    const d = await dialog('정보 수정')
    await replace(user, d, '이름', '김새이름')
    await user.type(d.getByLabelText('전화번호'), '02-123-4567')

    await user.click(d.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('cell', { name: '김새이름' })).toBeInTheDocument()
    expect(update).toHaveBeenCalledTimes(1)
    expect(update).toHaveBeenCalledWith(USER_ID.kim, { name: '김새이름', phone: '02-123-4567' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(within(rowOf('kim')).getByText('02-123-4567')).toBeInTheDocument()
  })

  it('keeps the save button disabled until something changes', async () => {
    const { user } = await openUsers(true)
    await user.click(within(rowOf('kim')).getByRole('button', { name: '정보 수정' }))

    const d = await dialog('정보 수정')

    expect(d.getByRole('button', { name: '저장' })).toBeDisabled()
  })

  it('shows the server message and keeps the dialog open for an invalid email', async () => {
    const { user } = await openUsers(true)
    await user.click(within(rowOf('kim')).getByRole('button', { name: '정보 수정' }))
    const d = await dialog('정보 수정')
    await replace(user, d, '이메일', 'not-an-email')

    await user.click(d.getByRole('button', { name: '저장' }))

    expect(await d.findByRole('alert')).toHaveTextContent('이메일 형식이 올바르지 않습니다.')
    expect(d.getByLabelText('이메일')).toHaveValue('not-an-email')
  })

  it('cancels without calling the server', async () => {
    const { user } = await openUsers(true)
    const update = vi.spyOn(gateway.users, 'update')
    await user.click(within(rowOf('kim')).getByRole('button', { name: '정보 수정' }))

    await user.click((await dialog('정보 수정')).getByRole('button', { name: '취소' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(update).not.toHaveBeenCalled()
  })

  it('lets the admin edit only the phone in AD mode', async () => {
    const { user } = await openUsers(false)
    const update = vi.spyOn(gateway.users, 'update')
    await user.click(within(rowOf('kim')).getByRole('button', { name: '정보 수정' }))
    const d = await dialog('정보 수정')

    expect(d.getByLabelText('이름')).toBeDisabled()
    expect(d.getByLabelText('이메일')).toBeDisabled()
    expect(d.getByLabelText('전화번호')).toBeEnabled()
    expect(d.getByText(/이름·이메일은 AD에서 관리합니다/)).toBeInTheDocument()
    await user.type(d.getByLabelText('전화번호'), '02-123-4567')
    await user.click(d.getByRole('button', { name: '저장' }))

    await screen.findByText('02-123-4567')
    expect(update).toHaveBeenCalledWith(USER_ID.kim, { phone: '02-123-4567' })
  })

  it('does not offer 정보 수정 on a resigned user', async () => {
    const { user } = await openUsers(true)

    await user.selectOptions(screen.getByLabelText('상태'), '전체')

    expect(within(await screen.findByRole('row', { name: /^old\b/ })).queryByRole('button', { name: '정보 수정' })).not.toBeInTheDocument()
  })
})

describe('비밀번호 재설정 (AC-7)', () => {
  it('offers 비밀번호 재설정 on other users in local mode but not on the admin row', async () => {
    await openUsers(true)

    expect(within(rowOf('kim')).getByRole('button', { name: '비밀번호 재설정' })).toBeInTheDocument()
    expect(within(rowOf('root')).queryByRole('button', { name: '비밀번호 재설정' })).not.toBeInTheDocument()
  })

  it('is not offered in AD mode', async () => {
    await openUsers(false)

    expect(screen.queryByRole('button', { name: '비밀번호 재설정' })).not.toBeInTheDocument()
  })

  it('resets the password, closes the dialog and says the sessions of that user ended', async () => {
    const { user } = await openUsers(true)
    const reset = vi.spyOn(gateway.users, 'resetPassword')
    await user.click(within(rowOf('kim')).getByRole('button', { name: '비밀번호 재설정' }))
    const d = await dialog('비밀번호 재설정')
    await user.type(d.getByLabelText('새 비밀번호'), 'Fresh-passw0rd')
    await user.type(d.getByLabelText('새 비밀번호 확인'), 'Fresh-passw0rd')

    await user.click(d.getByRole('button', { name: '재설정' }))

    expect(await screen.findByText(/kim 사용자의 비밀번호가 재설정되었습니다/)).toBeInTheDocument()
    expect(screen.getByText(/로그인은 모두 종료됩니다/)).toBeInTheDocument()
    expect(reset).toHaveBeenCalledTimes(1)
    expect(reset).toHaveBeenCalledWith(USER_ID.kim, 'Fresh-passw0rd')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('does not submit when the confirmation differs', async () => {
    const { user } = await openUsers(true)
    const reset = vi.spyOn(gateway.users, 'resetPassword')
    await user.click(within(rowOf('kim')).getByRole('button', { name: '비밀번호 재설정' }))
    const d = await dialog('비밀번호 재설정')
    await user.type(d.getByLabelText('새 비밀번호'), 'Fresh-passw0rd')
    await user.type(d.getByLabelText('새 비밀번호 확인'), 'Fresh-passw0rX')

    await user.click(d.getByRole('button', { name: '재설정' }))

    expect(await d.findByRole('alert')).toHaveTextContent('새 비밀번호 확인이 일치하지 않습니다.')
    expect(reset).not.toHaveBeenCalled()
  })

  it('shows the server message for a weak password and keeps the dialog open', async () => {
    const { user } = await openUsers(true)
    await user.click(within(rowOf('kim')).getByRole('button', { name: '비밀번호 재설정' }))
    const d = await dialog('비밀번호 재설정')
    await user.type(d.getByLabelText('새 비밀번호'), 'short7!')
    await user.type(d.getByLabelText('새 비밀번호 확인'), 'short7!')

    await user.click(d.getByRole('button', { name: '재설정' }))

    expect(await d.findByRole('alert')).toHaveTextContent('비밀번호는 8자 이상이어야 합니다.')
    expect(screen.getByRole('dialog', { name: '비밀번호 재설정' })).toBeInTheDocument()
  })

  it('never shows a password in the user list', async () => {
    await openUsers(true)

    expect(within(screen.getByRole('table')).queryByText(/비밀번호|password/i)).not.toBeInTheDocument()
  })
})
