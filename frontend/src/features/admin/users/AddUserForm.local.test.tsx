import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderLocalAt } from '../../../test/localAccounts'
import { renderAt } from '../../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

type Rendered = Awaited<ReturnType<typeof renderAt>>

async function openLocalUsers() {
  const view = await renderLocalAt('/admin/users', { role: 'admin' })
  await screen.findByRole('cell', { name: 'kim' })
  return view
}

const form = () => within(screen.getByRole('form', { name: '사용자 등록' }))

interface Values {
  loginId?: string
  password?: string
  confirm?: string
  name?: string
  email?: string
  phone?: string
  role?: string
}

async function fillForm(user: Rendered['user'], v: Values) {
  const f = form()
  const typeInto = async (label: string, text: string | undefined) => {
    if (text) await user.type(f.getByLabelText(label), text)
  }
  await typeInto('아이디', v.loginId)
  await typeInto('비밀번호', v.password)
  await typeInto('비밀번호 확인', v.confirm ?? v.password)
  await typeInto('이름', v.name)
  await typeInto('이메일', v.email)
  await typeInto('전화번호', v.phone)
  if (v.role) await user.selectOptions(f.getByLabelText('역할'), v.role)
}

const submit = (user: Rendered['user']) => user.click(form().getByRole('button', { name: '추가' }))

const GOOD: Values = { loginId: 'newbie', password: 'Passw0rd-ok', name: '신입영업', email: 'newbie@corp.test', phone: '010-1234-5678' }

describe('사용자 등록: local 모드 (AC-6)', () => {
  it('asks for id, password, confirmation, name, email, phone and role', async () => {
    await openLocalUsers()

    for (const label of ['아이디', '비밀번호', '비밀번호 확인', '이름', '이메일', '전화번호', '역할']) {
      expect(form().getByLabelText(label)).toBeInTheDocument()
    }
    expect(form().queryByLabelText('AD 아이디')).not.toBeInTheDocument()
    expect(form().getByLabelText('비밀번호')).toHaveAttribute('type', 'password')
    expect(form().getByLabelText('비밀번호')).toHaveAttribute('autocomplete', 'new-password')
    expect(form().getByLabelText('역할')).toHaveValue('sales')
  })

  it('registers the user with the password and profile, lists the phone and clears the form', async () => {
    const { user } = await openLocalUsers()
    const create = vi.spyOn(gateway.users, 'create')

    await fillForm(user, { ...GOOD, role: 'user' })
    await submit(user)

    const row = within(await screen.findByRole('row', { name: /^newbie\b/ }))
    expect(create).toHaveBeenCalledTimes(1)
    expect(create).toHaveBeenCalledWith({
      loginId: 'newbie',
      name: '신입영업',
      role: 'user',
      password: 'Passw0rd-ok',
      email: 'newbie@corp.test',
      phone: '010-1234-5678',
    })
    expect(row.getByText('010-1234-5678')).toBeInTheDocument()
    expect(row.getByText('newbie@corp.test')).toBeInTheDocument()
    expect(form().getByLabelText('아이디')).toHaveValue('')
    expect(form().getByLabelText('비밀번호')).toHaveValue('')
    expect(form().getByLabelText('비밀번호 확인')).toHaveValue('')
  })

  it('sends empty email and phone as null', async () => {
    const { user } = await openLocalUsers()
    const create = vi.spyOn(gateway.users, 'create')

    await fillForm(user, { loginId: 'newbie', password: 'Passw0rd-ok', name: '신입영업' })
    await submit(user)

    await screen.findByRole('row', { name: /^newbie\b/ })
    expect(create).toHaveBeenCalledWith(expect.objectContaining({ email: null, phone: null }))
  })

  it('the new user can sign in with the given password', async () => {
    const { user } = await openLocalUsers()
    await fillForm(user, GOOD)
    await submit(user)
    await screen.findByRole('row', { name: /^newbie\b/ })
    await gateway.auth.logout()

    const result = await gateway.auth.login('newbie', 'Passw0rd-ok')

    expect(result.me).toMatchObject({ loginId: 'newbie', name: '신입영업', role: 'sales' })
  })

  it('does not send a request when the confirmation differs', async () => {
    const { user } = await openLocalUsers()
    const create = vi.spyOn(gateway.users, 'create')

    await fillForm(user, { ...GOOD, confirm: 'Passw0rd-no' })
    await submit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('비밀번호 확인이 일치하지 않습니다.')
    expect(create).not.toHaveBeenCalled()
  })

  it('blocks missing id, password or name with a message instead of sending a request', async () => {
    const { user } = await openLocalUsers()
    const create = vi.spyOn(gateway.users, 'create')

    await submit(user)

    expect(screen.getByRole('alert')).toHaveTextContent('아이디, 비밀번호, 이름을 입력하세요.')
    expect(create).not.toHaveBeenCalled()
  })

  it('shows the server message for a weak password, keeps the other input and clears the passwords', async () => {
    const { user } = await openLocalUsers()

    await fillForm(user, { ...GOOD, password: 'short7!' })
    await submit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('비밀번호는 8자 이상이어야 합니다.')
    expect(form().getByLabelText('아이디')).toHaveValue('newbie')
    expect(form().getByLabelText('이름')).toHaveValue('신입영업')
    expect(form().getByLabelText('비밀번호')).toHaveValue('')
    expect(form().getByLabelText('비밀번호 확인')).toHaveValue('')
  })

  it('shows the server message when the id is already in use', async () => {
    const { user } = await openLocalUsers()

    await fillForm(user, { ...GOOD, loginId: 'kim' })
    await submit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('이미 사용 중인 아이디입니다.')
    expect(form().getByLabelText('아이디')).toHaveValue('kim')
  })
})

describe('사용자 등록: AD 모드는 비밀번호 없이 이메일·전화를 선택으로 받는다', () => {
  it('keeps the AD id label and adds optional email and phone but no password', async () => {
    await renderAt('/admin/users', { role: 'admin' })
    await screen.findByRole('cell', { name: 'kim' })

    expect(form().getByLabelText('AD 아이디')).toBeInTheDocument()
    expect(form().getByLabelText('이메일')).toBeInTheDocument()
    expect(form().getByLabelText('전화번호')).toBeInTheDocument()
    expect(form().queryByLabelText('비밀번호')).not.toBeInTheDocument()
    expect(form().queryByLabelText('비밀번호 확인')).not.toBeInTheDocument()
  })

  it('registers without a password and passes the phone', async () => {
    const { user } = await renderAt('/admin/users', { role: 'admin' })
    await screen.findByRole('cell', { name: 'kim' })
    const create = vi.spyOn(gateway.users, 'create')

    await user.type(form().getByLabelText('AD 아이디'), 'newbie')
    await user.type(form().getByLabelText('이름'), '신입영업')
    await user.type(form().getByLabelText('전화번호'), '010-1234-5678')
    await user.click(form().getByRole('button', { name: '추가' }))

    await screen.findByRole('row', { name: /^newbie\b/ })
    expect(create).toHaveBeenCalledTimes(1)
    const input = create.mock.calls[0]?.[0]
    expect(input).toMatchObject({ loginId: 'newbie', name: '신입영업', role: 'sales', phone: '010-1234-5678' })
    expect(input).not.toHaveProperty('password')
  })
})

describe('사용자 등록: 비밀번호는 캐시에 남지 않는다 (리뷰 Major)', () => {
  it('does not keep the typed passwords in the mutation cache, on success or failure', async () => {
    const { user, client } = await openLocalUsers()

    await fillForm(user, { ...GOOD, loginId: 'kim', password: 'Secret-fail-1' })
    await submit(user)
    await screen.findByRole('alert')
    await user.clear(form().getByLabelText('아이디'))
    await fillForm(user, { loginId: 'newbie', password: 'Secret-ok-2' })
    await submit(user)
    await screen.findByRole('row', { name: /^newbie\b/ })

    const kept = JSON.stringify(
      client
        .getMutationCache()
        .getAll()
        .map((m) => m.state.variables),
    )
    expect(kept).not.toContain('Secret-fail-1')
    expect(kept).not.toContain('Secret-ok-2')
  })
})
