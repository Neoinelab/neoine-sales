import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { DEFAULT_DEALS_URL_PATTERN } from '../../test/dealsUrl'
import { openLocalAdminStep, openUserMenu } from '../../test/localAccounts'

afterEach(() => vi.restoreAllMocks())

type Rendered = Awaited<ReturnType<typeof openLocalAdminStep>>

interface Values {
  loginId?: string
  password?: string
  confirm?: string
  name?: string
  email?: string
  phone?: string
}

async function fill(user: Rendered['user'], v: Values) {
  const typeInto = async (label: string, text: string | undefined) => {
    if (text) await user.type(screen.getByLabelText(label), text)
  }
  await typeInto('아이디', v.loginId)
  await typeInto('비밀번호', v.password)
  await typeInto('비밀번호 확인', v.confirm ?? v.password)
  await typeInto('이름', v.name)
  await typeInto('이메일', v.email)
  await typeInto('전화번호', v.phone)
}

const GOOD: Values = { loginId: 'boss', password: 'Passw0rd-ok', name: '보스', email: 'boss@corp.test', phone: '02-123-4567' }

const submit = (user: Rendered['user']) => user.click(screen.getByRole('button', { name: '관리자 등록' }))

describe('최초 설정 3단계: local 관리자 등록 (AC-4)', () => {
  it('asks for id, password, password confirmation, name, email and phone', async () => {
    await openLocalAdminStep()

    for (const label of ['아이디', '비밀번호', '비밀번호 확인', '이름', '이메일', '전화번호']) {
      expect(screen.getByLabelText(label)).toBeInTheDocument()
    }
    expect(screen.queryByLabelText('AD 아이디')).not.toBeInTheDocument()
    expect(screen.getByLabelText('비밀번호')).toHaveAttribute('type', 'password')
    expect(screen.getByLabelText('비밀번호')).toHaveAttribute('autocomplete', 'new-password')
    expect(screen.getByLabelText('비밀번호 확인')).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: '인증 방식 다시 선택' })).toBeInTheDocument()
  })

  it('registers the admin with the profile and moves to the main page signed in as that admin', async () => {
    const { user, location } = await openLocalAdminStep()
    const register = vi.spyOn(gateway.setup, 'registerAdmin')
    await fill(user, GOOD)

    await submit(user)

    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    expect(register).toHaveBeenCalledTimes(1)
    expect(register).toHaveBeenCalledWith('boss', 'Passw0rd-ok', {
      name: '보스',
      email: 'boss@corp.test',
      phone: '02-123-4567',
    })
    await openUserMenu(user)
    expect(await screen.findByText('보스 (admin)')).toBeInTheDocument()
  })

  it('sends empty email and phone as null', async () => {
    const { user, location } = await openLocalAdminStep()
    const register = vi.spyOn(gateway.setup, 'registerAdmin')
    await fill(user, { loginId: 'boss', password: 'Passw0rd-ok', name: '보스' })

    await submit(user)

    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    expect(register).toHaveBeenCalledWith('boss', 'Passw0rd-ok', { name: '보스', email: null, phone: null })
  })

  it('does not submit when the password confirmation differs', async () => {
    const { user } = await openLocalAdminStep()
    const register = vi.spyOn(gateway.setup, 'registerAdmin')
    await fill(user, { ...GOOD, confirm: 'Passw0rd-no' })

    await submit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('비밀번호 확인이 일치하지 않습니다.')
    expect(register).not.toHaveBeenCalled()
    expect(screen.getByRole('heading', { name: '관리자 등록' })).toBeInTheDocument()
  })

  it('shows the server message for a weak password and clears both password fields', async () => {
    const { user } = await openLocalAdminStep()
    await fill(user, { ...GOOD, password: 'short7!' })

    await submit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('비밀번호는 8자 이상이어야 합니다.')
    expect(screen.getByLabelText('비밀번호')).toHaveValue('')
    expect(screen.getByLabelText('비밀번호 확인')).toHaveValue('')
    expect(screen.getByLabelText('아이디')).toHaveValue('boss')
    expect(screen.getByLabelText('이름')).toHaveValue('보스')
  })

  it('shows the server message when the name is missing and stays on step 3', async () => {
    const { user } = await openLocalAdminStep()
    await fill(user, { ...GOOD, name: undefined })

    await submit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('이름을 입력하세요.')
    expect(screen.getByRole('heading', { name: '관리자 등록' })).toBeInTheDocument()
  })

  it('goes back to the auth mode choice', async () => {
    const { user } = await openLocalAdminStep()

    await user.click(screen.getByRole('button', { name: '인증 방식 다시 선택' }))

    expect(await screen.findByRole('heading', { name: '인증 방식' })).toBeInTheDocument()
  })

  it('does not call the directory registration of the AD flow', async () => {
    const { user, location } = await openLocalAdminStep()
    const saveDirectory = vi.spyOn(gateway.setup, 'saveDirectory')
    await fill(user, GOOD)

    await submit(user)

    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    expect(saveDirectory).not.toHaveBeenCalled()
  })
})

describe('최초 설정 3단계: 빈 비밀번호는 서버 호출 전에 막는다 (리뷰 Minor 3)', () => {
  it.each([
    ['both password fields empty', { ...GOOD, password: undefined, confirm: undefined }],
    ['empty password with a filled confirmation', { ...GOOD, password: undefined, confirm: 'Passw0rd-ok' }],
  ])('does not call the server with %s', async (_name, values) => {
    const { user } = await openLocalAdminStep()
    const register = vi.spyOn(gateway.setup, 'registerAdmin')
    await fill(user, values)

    await submit(user)

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(register).not.toHaveBeenCalled()
    expect(screen.getByRole('heading', { name: '관리자 등록' })).toBeInTheDocument()
  })

  it('says the password is required when both fields are empty', async () => {
    const { user } = await openLocalAdminStep()
    await fill(user, { ...GOOD, password: undefined, confirm: undefined })

    await submit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('비밀번호를 입력하세요.')
  })
})
