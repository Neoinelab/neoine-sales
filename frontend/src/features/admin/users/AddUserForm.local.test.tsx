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

describe('사용자 등록: local 모드', () => {
  // local 모드 등록 폼은 아이디·비밀번호·확인·이름·이메일·전화번호·역할을 받는다
  it('asks for id, password, confirmation, name, email, phone and role', async () => {
    // when: 사용자 관리 화면을 연다 (전제: local 모드)
    await openLocalUsers()

    // then: 일곱 칸이 모두 있고 비밀번호 칸은 password 형식이다
    for (const label of ['아이디', '비밀번호', '비밀번호 확인', '이름', '이메일', '전화번호', '역할']) {
      expect(form().getByLabelText(label)).toBeInTheDocument()
    }
    expect(form().queryByLabelText('AD 아이디')).not.toBeInTheDocument()
    expect(form().getByLabelText('비밀번호')).toHaveAttribute('type', 'password')
    expect(form().getByLabelText('비밀번호')).toHaveAttribute('autocomplete', 'new-password')
    expect(form().getByLabelText('역할')).toHaveValue('sales')
  })

  // local 등록은 비밀번호·프로필을 보내고 성공하면 폼을 비운다
  // 테스트 코드: US-089
  it('registers the user with the password and profile, lists the phone and clears the form', async () => {
    // given: local 모드와 create 감시
    const { user } = await openLocalUsers()
    const create = vi.spyOn(gateway.users, 'create')

    await fillForm(user, { ...GOOD, role: 'user' })
    // when: 모든 칸을 입력하고 추가한다
    await submit(user)

    // then: create가 비밀번호·프로필과 함께 호출되고 행이 생기며 폼이 비워진다
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

  // 빈 이메일·전화는 null로 보낸다
  // 테스트 코드: US-089
  it('sends empty email and phone as null', async () => {
    // given: local 모드와 create 감시
    const { user } = await openLocalUsers()
    const create = vi.spyOn(gateway.users, 'create')

    await fillForm(user, { loginId: 'newbie', password: 'Passw0rd-ok', name: '신입영업' })
    // when: 이메일·전화 없이 추가한다
    await submit(user)

    // then: create가 이메일·전화 null로 호출된다
    await screen.findByRole('row', { name: /^newbie\b/ })
    expect(create).toHaveBeenCalledWith(expect.objectContaining({ email: null, phone: null }))
  })

  // 등록한 사용자는 그 비밀번호로 로그인된다
  it('the new user can sign in with the given password', async () => {
    // given: 방금 등록하고 로그아웃한 newbie
    const { user } = await openLocalUsers()
    await fillForm(user, GOOD)
    await submit(user)
    await screen.findByRole('row', { name: /^newbie\b/ })
    await gateway.auth.logout()

    // when: 그 비밀번호로 로그인한다
    const result = await gateway.auth.login('newbie', 'Passw0rd-ok')

    // then: newbie로 로그인된다
    expect(result.me).toMatchObject({ loginId: 'newbie', name: '신입영업', role: 'sales' })
  })

  // local 등록에서 비밀번호 확인이 다르면 요청하지 않는다
  // 테스트 코드: US-088
  it('does not send a request when the confirmation differs', async () => {
    // given: local 모드와 create 감시
    const { user } = await openLocalUsers()
    const create = vi.spyOn(gateway.users, 'create')

    await fillForm(user, { ...GOOD, confirm: 'Passw0rd-no' })
    // when: 확인이 다른 값으로 추가한다
    await submit(user)

    // then: 확인 불일치 문구가 보이고 create가 호출되지 않는다
    expect(await screen.findByRole('alert')).toHaveTextContent('비밀번호 확인이 일치하지 않습니다.')
    expect(create).not.toHaveBeenCalled()
  })

  // local 모드에서 필수 칸이 비면 요청하지 않고 안내 문구를 보인다
  // 테스트 코드: US-087
  it('blocks missing id, password or name with a message instead of sending a request', async () => {
    // given: local 모드와 create 감시
    const { user } = await openLocalUsers()
    const create = vi.spyOn(gateway.users, 'create')

    // when: 빈 폼으로 추가한다
    await submit(user)

    // then: 안내 문구가 보이고 create가 호출되지 않는다
    expect(screen.getByRole('alert')).toHaveTextContent('아이디, 비밀번호, 이름을 입력하세요.')
    expect(create).not.toHaveBeenCalled()
  })

  // 등록이 거절되면 서버 문구를 보이고 비밀번호 칸만 비운다
  // 테스트 코드: US-090
  it('shows the server message for a weak password, keeps the other input and clears the passwords', async () => {
    // given: local 모드
    const { user } = await openLocalUsers()

    await fillForm(user, { ...GOOD, password: 'short7!' })
    // when: 약한 비밀번호로 추가한다
    await submit(user)

    // then: 서버 문구가 보이고 아이디·이름은 유지되며 비밀번호 칸은 비워진다
    expect(await screen.findByRole('alert')).toHaveTextContent('비밀번호는 8자 이상이어야 합니다')
    expect(form().getByLabelText('아이디')).toHaveValue('newbie')
    expect(form().getByLabelText('이름')).toHaveValue('신입영업')
    expect(form().getByLabelText('비밀번호')).toHaveValue('')
    expect(form().getByLabelText('비밀번호 확인')).toHaveValue('')
  })

  // 이미 있는 아이디로 등록하면 서버 문구를 보이고 입력은 유지한다
  // 테스트 코드: US-090
  it('shows the server message when the id is already in use', async () => {
    // given: local 모드
    const { user } = await openLocalUsers()

    await fillForm(user, { ...GOOD, loginId: 'kim' })
    // when: 이미 있는 아이디로 추가한다
    await submit(user)

    // then: 서버 문구가 보이고 아이디 입력이 유지된다
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 존재하는 사용자입니다: kim')
    expect(form().getByLabelText('아이디')).toHaveValue('kim')
  })
})

describe('사용자 등록: AD 모드는 비밀번호 없이 이메일·전화를 선택으로 받는다', () => {
  // AD 모드 폼은 AD 아이디 칸이 있고 비밀번호 칸이 없다
  // 테스트 코드: US-084
  it('keeps the AD id label and adds optional email and phone but no password', async () => {
    // given: AD 모드
    await renderAt('/admin/users', { role: 'admin' })

    // when: 사용자 관리 화면을 연다
    await screen.findByRole('cell', { name: 'kim' })

    // then: AD 아이디·이메일·전화번호 칸이 있고 비밀번호 칸은 없다
    expect(form().getByLabelText('AD 아이디')).toBeInTheDocument()
    expect(form().getByLabelText('이메일')).toBeInTheDocument()
    expect(form().getByLabelText('전화번호')).toBeInTheDocument()
    expect(form().queryByLabelText('비밀번호')).not.toBeInTheDocument()
    expect(form().queryByLabelText('비밀번호 확인')).not.toBeInTheDocument()
  })

  // AD 모드 등록은 비밀번호 없이 전화를 보낸다
  // 테스트 코드: US-086
  it('registers without a password and passes the phone', async () => {
    // given: AD 모드와 create 감시
    const { user } = await renderAt('/admin/users', { role: 'admin' })
    await screen.findByRole('cell', { name: 'kim' })
    const create = vi.spyOn(gateway.users, 'create')

    await user.type(form().getByLabelText('AD 아이디'), 'newbie')
    await user.type(form().getByLabelText('이름'), '신입영업')
    await user.type(form().getByLabelText('전화번호'), '010-1234-5678')
    // when: 아이디·이름·전화를 입력하고 추가한다
    await user.click(form().getByRole('button', { name: '추가' }))

    // then: create가 비밀번호 없이 전화와 함께 호출된다
    await screen.findByRole('row', { name: /^newbie\b/ })
    expect(create).toHaveBeenCalledTimes(1)
    const input = create.mock.calls[0]?.[0]
    expect(input).toMatchObject({ loginId: 'newbie', name: '신입영업', role: 'sales', phone: '010-1234-5678' })
    expect(input).not.toHaveProperty('password')
  })
})

describe('사용자 등록: 비밀번호는 캐시에 남지 않는다 (리뷰 Major)', () => {
  // 입력한 비밀번호는 성공·실패 뒤 요청 캐시에 남지 않는다
  // 테스트 코드: US-091
  it('does not keep the typed passwords in the mutation cache, on success or failure', async () => {
    // given: local 모드
    const { user, client } = await openLocalUsers()

    await fillForm(user, { ...GOOD, loginId: 'kim', password: 'Secret-fail-1' })
    await submit(user)
    await screen.findByRole('alert')
    await user.clear(form().getByLabelText('아이디'))
    await fillForm(user, { loginId: 'newbie', password: 'Secret-ok-2' })
    // when: 실패하는 등록과 성공하는 등록을 차례로 한다
    await submit(user)
    await screen.findByRole('row', { name: /^newbie\b/ })

    // then: 뮤테이션 캐시에 두 비밀번호가 모두 남아 있지 않다
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
