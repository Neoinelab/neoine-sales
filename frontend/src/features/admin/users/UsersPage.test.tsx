import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { keys } from '../../../data/queryKeys'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'

type Rendered = Awaited<ReturnType<typeof renderAt>>

afterEach(() => vi.restoreAllMocks())

/** 게이트웨이가 실제로 던지는 ApiError 하나(로그아웃 상태의 me() → 401). 로그인 전에 얻는다. */
async function serverError(): Promise<unknown> {
  await gateway.auth.logout()
  return gateway.auth.me().catch((e: unknown) => e)
}
const SERVER_MESSAGE = '로그인이 필요합니다.'

/** 화면 본문만 본다(테스트 도우미의 위치 표시 `<output>`도 status 역할이라 전체 문서에서는 겹친다). */
function inPage() {
  return within(screen.getByRole('main'))
}

async function openUsers() {
  const view = await renderAt('/admin/users', { role: 'admin' })
  await screen.findByRole('cell', { name: 'kim' })
  return view
}

function rowOf(loginId: string) {
  return screen.getByRole('row', { name: new RegExp(`^${loginId}\\b`) })
}

async function addUser(
  user: Awaited<ReturnType<typeof renderAt>>['user'],
  values: { loginId: string; name: string; role?: string },
) {
  const form = within(screen.getByRole('form', { name: '사용자 등록' }))
  await user.type(form.getByLabelText('AD 아이디'), values.loginId)
  await user.type(form.getByLabelText('이름'), values.name)
  if (values.role) await user.selectOptions(form.getByLabelText('역할'), values.role)
  await user.click(form.getByRole('button', { name: '추가' }))
}

describe('사용자 관리 목록 (T-ADMIN-01)', () => {
  it('lists active users by default and hides the resigned one', async () => {
    await openUsers()

    for (const id of ['root', 'kim', 'park', 'lee', 'jung', 'han']) {
      expect(screen.getByRole('cell', { name: id })).toBeInTheDocument()
    }
    expect(screen.queryByRole('cell', { name: 'old' })).not.toBeInTheDocument()
  })

  it('lists id, role, name, created, creator and last login', async () => {
    await openUsers()

    for (const header of ['아이디', '역할', '이름', '등록일', '등록자', '마지막 로그인', '퇴사 일시', '퇴사 사유']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument()
    }
    const kim = within(rowOf('kim'))
    expect(kim.getByText('sales')).toBeInTheDocument()
    expect(kim.getByText('김영업')).toBeInTheDocument()
    expect(kim.getByText('최관리')).toBeInTheDocument()
  })

  it('shows "-" for resignation columns of active users', async () => {
    await openUsers()

    expect(within(rowOf('kim')).getAllByText('-')).toHaveLength(2)
  })

  it('offers 재직, 퇴사 and 전체 and can list only the resigned', async () => {
    const { user } = await openUsers()
    const filter = screen.getByLabelText('상태')
    expect(within(filter).getAllByRole('option').map((o) => o.textContent)).toEqual(['재직', '퇴사', '전체'])

    await user.selectOptions(filter, '퇴사')

    expect(await screen.findByRole('cell', { name: 'old' })).toBeInTheDocument()
    expect(screen.queryByRole('cell', { name: 'kim' })).not.toBeInTheDocument()
  })

  it('shows a resigned row with 이름(퇴사), the resignation reason, and no delete button', async () => {
    const { user } = await openUsers()

    await user.selectOptions(screen.getByLabelText('상태'), '전체')

    const row = within(await screen.findByRole('row', { name: /^old\b/ }))
    expect(row.getByText('강퇴사(퇴사)')).toBeInTheDocument()
    expect(row.getByText('개인 사정으로 퇴사')).toBeInTheDocument()
    expect(row.queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(1 + 7)
  })

  it('has no edit button and no password column or field anywhere', async () => {
    await openUsers()

    expect(screen.queryByRole('button', { name: /수정/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/비밀번호/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/비밀번호/)).not.toBeInTheDocument()
  })

  it('shows the empty message when there are no users', async () => {
    vi.spyOn(gateway.users, 'list').mockResolvedValue([])
    await renderAt('/admin/users', { role: 'admin' })

    expect(await screen.findByText('등록된 사용자가 없습니다.')).toBeInTheDocument()
  })

  it('shows the message when the list cannot be loaded', async () => {
    vi.spyOn(gateway.users, 'list').mockRejectedValue(await serverError())
    await renderAt('/admin/users', { role: 'admin' })

    expect(await screen.findByRole('alert')).toHaveTextContent(SERVER_MESSAGE)
  })
})

describe('사용자 등록 (T-ADMIN-02)', () => {
  it('registers an AD id with the chosen role and refreshes the list', async () => {
    const { user } = await openUsers()

    await addUser(user, { loginId: 'newbie', name: '신입영업', role: 'user' })

    const row = within(await screen.findByRole('row', { name: /^newbie\b/ }))
    expect(row.getByText('user')).toBeInTheDocument()
    expect(row.getByText('신입영업')).toBeInTheDocument()
    expect(row.getByText('최관리')).toBeInTheDocument()
    expect(screen.getByLabelText('AD 아이디')).toHaveValue('')
    expect(screen.getByLabelText('이름')).toHaveValue('')
  })

  it('defaults the role to sales', async () => {
    await openUsers()

    expect(screen.getByLabelText('역할')).toHaveValue('sales')
  })

  it('shows the server message and keeps the input when the id already exists', async () => {
    const { user } = await openUsers()

    await addUser(user, { loginId: 'kim', name: '또김' })

    expect(await screen.findByRole('alert')).toHaveTextContent('이미 사용 중인 아이디입니다.')
    expect(screen.getByLabelText('AD 아이디')).toHaveValue('kim')
    expect(screen.getByLabelText('이름')).toHaveValue('또김')
  })

  it('blocks empty input with a message instead of sending a request', async () => {
    const { user } = await openUsers()
    const create = vi.spyOn(gateway.users, 'create')

    await user.click(within(screen.getByRole('form', { name: '사용자 등록' })).getByRole('button', { name: '추가' }))

    expect(screen.getByRole('alert')).toHaveTextContent('AD 아이디와 이름을 입력하세요.')
    expect(create).not.toHaveBeenCalled()
  })
})

describe('사용자 선택 목록 갱신 (옛 hooks.test 이관)', () => {
  async function watchOptions(client: Rendered['client']) {
    const queryKey = keys.userOptions({ role: 'sales' })
    await client.prefetchQuery({ queryKey, queryFn: () => gateway.users.options({ role: 'sales' }) })
    expect(client.getQueryState(queryKey)?.isInvalidated).toBe(false)
    return () => client.getQueryState(queryKey)?.isInvalidated
  }

  it('invalidates user-options after adding a user', async () => {
    const { user, client } = await openUsers()
    const invalidated = await watchOptions(client)

    await addUser(user, { loginId: 'newbie', name: '신입영업' })

    await waitFor(() => expect(invalidated()).toBe(true))
  })

  it('invalidates user-options after deleting a user', async () => {
    const { user, client } = await openUsers()
    const invalidated = await watchOptions(client)

    await user.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(invalidated()).toBe(true))
  })
})

describe('사용자 삭제·퇴사 (T-ADMIN-01)', () => {
  it('hides the delete button on the row of the signed-in admin (last admin and self protection)', async () => {
    await openUsers()

    expect(within(rowOf('root')).queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    expect(within(rowOf('kim')).getByRole('button', { name: '삭제' })).toBeInTheDocument()
  })

  it('does nothing when the confirmation is declined', async () => {
    const { user } = await openUsers()
    const remove = vi.spyOn(gateway.users, 'remove')

    await user.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))
    const dialog = within(await screen.findByRole('dialog', { name: '사용자 삭제' }))
    expect(dialog.getByText(/연결된 데이터가 있으면 퇴사 처리되고, 없으면 완전히 삭제됩니다/)).toBeInTheDocument()
    await user.click(dialog.getByRole('button', { name: '취소' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(remove).not.toHaveBeenCalled()
    expect(screen.getByRole('cell', { name: 'kim' })).toBeInTheDocument()
  })

  it('says the user was processed as resigned when data was linked', async () => {
    const { user } = await openUsers()

    await user.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    expect(await inPage().findByRole('status')).toHaveTextContent(/kim.*퇴사 처리되었습니다/)
    await waitFor(() => expect(screen.queryByRole('cell', { name: 'kim' })).not.toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('상태'), '퇴사')
    expect(await screen.findByText('김영업(퇴사)')).toBeInTheDocument()
  })

  it('says the user was deleted when nothing was linked', async () => {
    const { user } = await openUsers()
    await addUser(user, { loginId: 'temp', name: '임시' })
    await screen.findByRole('cell', { name: 'temp' })

    await user.click(within(rowOf('temp')).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    expect(await inPage().findByRole('status')).toHaveTextContent(/temp.*삭제되었습니다/)
    await waitFor(() => expect(screen.queryByRole('cell', { name: 'temp' })).not.toBeInTheDocument())
  })

  it('shows the server message and closes the dialog when deletion is refused', async () => {
    const error = await serverError()
    const { user } = await openUsers()
    vi.spyOn(gateway.users, 'remove').mockRejectedValue(error)

    await user.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(SERVER_MESSAGE)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('clears the previous result message when the next delete fails', async () => {
    const error = await serverError()
    const { user } = await openUsers()
    await user.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))
    await inPage().findByRole('status')
    vi.spyOn(gateway.users, 'remove').mockRejectedValue(error)

    await user.click(within(rowOf('park')).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(inPage().queryByRole('status')).not.toBeInTheDocument()
  })
})
