import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { keys } from '../../../data/queryKeys'
import { gateway } from '../../../gateway'
import { USER_ID } from '../../../test/fake/seed/ids'
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
  // 목록은 기본으로 재직자만 보인다
  // 테스트 코드: US-077
  it('lists active users by default and hides the resigned one', async () => {
    // when: admin이 사용자 관리 화면을 연다 (전제: 퇴사자 old가 있는 사용자 목록)
    await openUsers()

    // then: 재직자 6명이 보이고 퇴사자 old는 없다
    for (const id of ['root', 'kim', 'park', 'lee', 'jung', 'han']) {
      expect(screen.getByRole('cell', { name: id })).toBeInTheDocument()
    }
    expect(screen.queryByRole('cell', { name: 'old' })).not.toBeInTheDocument()
  })

  // 표는 아이디·역할·이름·등록일·등록자·마지막 로그인 열과 값을 보인다
  // 테스트 코드: US-078
  it('lists id, role, name, created, creator and last login', async () => {
    // when: admin이 사용자 관리 화면을 연다
    await openUsers()

    // then: 머리글이 모두 있고 kim 행에 역할·이름·등록자가 보인다
    for (const header of ['아이디', '역할', '이름', '등록일', '등록자', '마지막 로그인', '퇴사 일시', '퇴사 사유']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument()
    }
    const kim = within(rowOf('kim'))
    expect(kim.getByText('sales')).toBeInTheDocument()
    expect(kim.getByText('김영업')).toBeInTheDocument()
    expect(kim.getByText('최관리')).toBeInTheDocument()
  })

  // 재직자 행의 퇴사 일시·퇴사 사유와 없는 전화번호는 -로 보인다
  // 테스트 코드: US-078
  it('shows "-" for resignation columns of active users', async () => {
    // when: admin이 사용자 관리 화면을 연다
    await openUsers()

    // then: kim 행에 - 가 세 칸 있다 (퇴사 일시·퇴사 사유 두 칸과, 전화번호가 없는 시드 사용자의 전화번호 칸)
    expect(within(rowOf('kim')).getAllByText('-')).toHaveLength(3)
  })

  // 상태 선택은 재직·퇴사·전체이고 퇴사를 고르면 퇴사자만 보인다
  // 테스트 코드: US-079
  it('offers 재직, 퇴사 and 전체 and can list only the resigned', async () => {
    // given: 사용자 관리 화면
    const { user } = await openUsers()
    const filter = screen.getByLabelText('상태')
    expect(within(filter).getAllByRole('option').map((o) => o.textContent)).toEqual(['재직', '퇴사', '전체'])

    // when: 상태를 퇴사로 고른다
    await user.selectOptions(filter, '퇴사')

    // then: 퇴사자 old만 보이고 kim은 사라진다
    expect(await screen.findByRole('cell', { name: 'old' })).toBeInTheDocument()
    expect(screen.queryByRole('cell', { name: 'kim' })).not.toBeInTheDocument()
  })

  // 퇴사 행은 이름(퇴사)·퇴사 사유를 보이고 작업 버튼이 없다
  // 테스트 코드: US-080
  it('shows a resigned row with 이름(퇴사), the resignation reason, and no delete button', async () => {
    // given: 사용자 관리 화면
    const { user } = await openUsers()

    // when: 상태를 전체로 고른다
    await user.selectOptions(screen.getByLabelText('상태'), '전체')

    const row = within(await screen.findByRole('row', { name: /^old\b/ }))
    // then: old 행에 강퇴사(퇴사)와 퇴사 사유가 있고 삭제 버튼이 없다
    expect(row.getByText('강퇴사(퇴사)')).toBeInTheDocument()
    expect(row.getByText('퇴사')).toBeInTheDocument()
    expect(row.queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(1 + 7)
  })

  // AD 모드 화면에는 비밀번호 칸·재설정 버튼이 없다
  // 테스트 코드: US-084
  it('has no password column, field or reset button in AD mode', async () => {
    // when: 사용자 관리 화면을 연다 (전제: AD 모드)
    await openUsers()

    // then: 비밀번호라는 글자·칸·버튼이 없다
    expect(screen.queryByRole('button', { name: '비밀번호 재설정' })).not.toBeInTheDocument()
    expect(screen.queryByText(/비밀번호/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/비밀번호/)).not.toBeInTheDocument()
  })

  // 사용자가 없으면 빈 메시지를 보인다
  // 테스트 코드: US-081
  it('shows the empty message when there are no users', async () => {
    // given: 사용자 목록이 비어 있는 게이트웨이
    vi.spyOn(gateway.users, 'list').mockResolvedValue([])
    // when: 사용자 관리 화면을 연다
    await renderAt('/admin/users', { role: 'admin' })

    // then: 등록된 사용자가 없다는 메시지가 보인다
    expect(await screen.findByText('등록된 사용자가 없습니다.')).toBeInTheDocument()
  })

  // 목록을 읽지 못하면 서버 문구를 오류로 보인다
  // 테스트 코드: US-082
  it('shows the message when the list cannot be loaded', async () => {
    // given: 목록 조회가 서버 오류로 실패하는 게이트웨이
    vi.spyOn(gateway.users, 'list').mockRejectedValue(await serverError())
    // when: 사용자 관리 화면을 연다
    await renderAt('/admin/users', { role: 'admin' })

    // then: 서버 문구가 오류로 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent(SERVER_MESSAGE)
  })
})

describe('사용자 등록 (T-ADMIN-02)', () => {
  // AD 아이디를 고른 역할로 등록하면 목록에 행이 생기고 폼이 빈다
  // 테스트 코드: US-086
  it('registers an AD id with the chosen role and refreshes the list', async () => {
    // given: 사용자 관리 화면
    const { user } = await openUsers()

    // when: AD 아이디·이름·역할을 입력하고 추가한다
    await addUser(user, { loginId: 'newbie', name: '신입영업', role: 'user' })

    // then: 새 행이 역할·이름·등록자와 함께 보이고 폼 칸이 비워진다
    const row = within(await screen.findByRole('row', { name: /^newbie\b/ }))
    expect(row.getByText('user')).toBeInTheDocument()
    expect(row.getByText('신입영업')).toBeInTheDocument()
    expect(row.getByText('최관리')).toBeInTheDocument()
    expect(screen.getByLabelText('AD 아이디')).toHaveValue('')
    expect(screen.getByLabelText('이름')).toHaveValue('')
  })

  // 등록 폼의 역할 기본값은 sales다
  // 테스트 코드: US-086
  it('defaults the role to sales', async () => {
    // when: 등록 폼을 본다 (전제: 사용자 관리 화면)
    await openUsers()

    // then: 역할 선택이 sales다
    expect(screen.getByLabelText('역할')).toHaveValue('sales')
  })

  // 등록이 거절되면 서버 문구를 보이고 입력은 유지한다
  // 테스트 코드: US-090
  it('shows the server message and keeps the input when the id already exists', async () => {
    // given: 사용자 관리 화면, 이미 있는 아이디
    const { user } = await openUsers()

    // when: 이미 있는 아이디로 추가한다
    await addUser(user, { loginId: 'kim', name: '또김' })

    // then: 서버 문구가 보이고 아이디·이름 입력이 그대로다
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 존재하는 사용자입니다: kim')
    expect(screen.getByLabelText('AD 아이디')).toHaveValue('kim')
    expect(screen.getByLabelText('이름')).toHaveValue('또김')
  })

  // AD 모드에서 필수 칸이 비면 요청하지 않고 안내 문구를 보인다
  // 테스트 코드: US-087
  it('blocks empty input with a message instead of sending a request', async () => {
    // given: 사용자 관리 화면과 create 감시
    const { user } = await openUsers()
    const create = vi.spyOn(gateway.users, 'create')

    // when: 빈 폼으로 추가한다
    await user.click(within(screen.getByRole('form', { name: '사용자 등록' })).getByRole('button', { name: '추가' }))

    // then: 안내 문구가 보이고 create가 호출되지 않는다
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

  // 등록하면 사용자 선택 목록을 다시 읽게 한다
  // 테스트 코드: US-107
  it('invalidates user-options after adding a user', async () => {
    // given: 선택 목록 조회가 캐시에 있다
    const { user, client } = await openUsers()
    const invalidated = await watchOptions(client)

    // when: 사용자를 등록한다
    await addUser(user, { loginId: 'newbie', name: '신입영업' })

    // then: 선택 목록이 무효화된다
    await waitFor(() => expect(invalidated()).toBe(true))
  })

  // 삭제하면 사용자 선택 목록을 다시 읽게 한다
  // 테스트 코드: US-107
  it('invalidates user-options after deleting a user', async () => {
    // given: 선택 목록 조회가 캐시에 있다
    const { user, client } = await openUsers()
    const invalidated = await watchOptions(client)

    await user.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))
    // when: kim을 삭제한다
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    // then: 선택 목록이 무효화된다
    await waitFor(() => expect(invalidated()).toBe(true))
  })
})

describe('사용자 삭제·퇴사 (T-ADMIN-01)', () => {
  // 본인 행에는 작업 버튼이 없고 다른 재직 행에는 삭제가 있다
  // 테스트 코드: US-083
  it('hides the delete button on the row of the signed-in admin (last admin and self protection)', async () => {
    // when: 목록을 본다 (전제: 사용자 관리 화면)
    await openUsers()

    // then: root 행에는 삭제 버튼이 없고 kim 행에는 있다
    expect(within(rowOf('root')).queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    expect(within(rowOf('kim')).getByRole('button', { name: '삭제' })).toBeInTheDocument()
  })

  // 삭제 확인을 취소하면 요청하지 않는다
  // 테스트 코드: US-104
  it('does nothing when the confirmation is declined', async () => {
    // given: 사용자 관리 화면과 remove 감시
    const { user } = await openUsers()
    const remove = vi.spyOn(gateway.users, 'remove')

    await user.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))
    const dialog = within(await screen.findByRole('dialog', { name: '사용자 삭제' }))
    expect(dialog.getByText(/연결된 데이터가 있으면 퇴사 처리되고, 없으면 완전히 삭제됩니다/)).toBeInTheDocument()
    // when: 삭제 확인에서 취소를 누른다
    await user.click(dialog.getByRole('button', { name: '취소' }))

    // then: 대화상자가 닫히고 remove가 호출되지 않으며 kim이 그대로 있다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(remove).not.toHaveBeenCalled()
    expect(screen.getByRole('cell', { name: 'kim' })).toBeInTheDocument()
  })

  // 연결된 데이터가 있으면 퇴사 처리 알림을 보이고 목록에서 뺀다
  // 테스트 코드: US-105
  it('says the user was processed as resigned when data was linked', async () => {
    // given: 연결된 데이터가 있는 kim
    const { user } = await openUsers()

    await user.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))
    // when: kim을 삭제 확인한다
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    // then: 퇴사 처리 알림이 보이고 재직 목록에서 빠지며 퇴사 목록에 나온다
    expect(await inPage().findByRole('status')).toHaveTextContent(/kim.*퇴사 처리되었습니다/)
    await waitFor(() => expect(screen.queryByRole('cell', { name: 'kim' })).not.toBeInTheDocument())
    // when: 상태 필터를 퇴사로 바꾼다
    await user.selectOptions(screen.getByLabelText('상태'), '퇴사')
    // then: 퇴사 목록에 나온다
    expect(await screen.findByText('김영업(퇴사)')).toBeInTheDocument()
  })

  // 연결된 데이터가 없으면 삭제 알림을 보이고 목록에서 뺀다
  // 테스트 코드: US-105
  it('says the user was deleted when nothing was linked', async () => {
    // given: 방금 등록한 연결 없는 temp
    const { user } = await openUsers()
    await addUser(user, { loginId: 'temp', name: '임시' })
    await screen.findByRole('cell', { name: 'temp' })

    await user.click(within(rowOf('temp')).getByRole('button', { name: '삭제' }))
    // when: temp를 삭제 확인한다
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    // then: 삭제 알림이 보이고 목록에서 빠진다
    expect(await inPage().findByRole('status')).toHaveTextContent(/temp.*삭제되었습니다/)
    await waitFor(() => expect(screen.queryByRole('cell', { name: 'temp' })).not.toBeInTheDocument())
  })

  // 삭제가 거절되면 대화상자를 닫고 오류 배너를 보인다
  // 테스트 코드: US-106
  it('shows the server message and closes the dialog when deletion is refused', async () => {
    // given: 삭제가 서버 오류로 실패하는 게이트웨이
    const error = await serverError()
    const { user } = await openUsers()
    vi.spyOn(gateway.users, 'remove').mockRejectedValue(error)

    await user.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))
    // when: kim을 삭제 확인한다
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    // then: 서버 문구가 오류 배너에 보이고 대화상자가 닫힌다
    expect(await screen.findByRole('alert')).toHaveTextContent(SERVER_MESSAGE)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 다음 삭제가 실패하면 이전 성공 알림을 지운다
  // 테스트 코드: US-106
  it('clears the previous result message when the next delete fails', async () => {
    // given: 한 번 삭제에 성공해 알림이 떠 있고 다음 삭제는 실패한다
    const error = await serverError()
    const { user } = await openUsers()
    await user.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))
    await inPage().findByRole('status')
    vi.spyOn(gateway.users, 'remove').mockRejectedValue(error)

    await user.click(within(rowOf('park')).getByRole('button', { name: '삭제' }))
    // when: park을 삭제 확인한다
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    // then: 오류 배너가 보이고 이전 알림은 사라진다
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(inPage().queryByRole('status')).not.toBeInTheDocument()
  })
})

describe('역할 변경 (R1 AC1-10~12)', () => {
  const OWNER_WARNING = 'sales가 아니면 새 Deal의 Owner로 지정할 수 없습니다. 이미 Owner인 Deal은 그대로 남습니다.'

  async function openRoleDialog(user: Rendered['user'], loginId: string) {
    await user.click(within(rowOf(loginId)).getByRole('button', { name: '역할 변경' }))
    return within(await screen.findByRole('dialog', { name: '역할 변경' }))
  }

  // 역할 변경 버튼은 본인 행과 퇴사 행에는 없다
  // 테스트 코드: US-083, US-080
  it('shows 역할 변경 only on active rows other than the signed-in admin', async () => {
    // given: 사용자 관리 화면
    const { user } = await openUsers()

    expect(within(rowOf('kim')).getByRole('button', { name: '역할 변경' })).toBeInTheDocument()
    expect(within(rowOf('han')).getByRole('button', { name: '역할 변경' })).toBeInTheDocument()
    expect(within(rowOf('root')).queryByRole('button', { name: '역할 변경' })).not.toBeInTheDocument()

    // when: 상태를 퇴사로 고른다
    await user.selectOptions(screen.getByLabelText('상태'), '퇴사')
    // then: 퇴사 행에는 역할 변경 버튼이 없다(본인 행에도 없다)
    const resigned = within(await screen.findByRole('row', { name: /^old\b/ }))
    expect(resigned.queryByRole('button', { name: '역할 변경' })).not.toBeInTheDocument()
  })

  // 역할 변경 대화상자는 현재 역할을 고른 채 열리고 변경이 비활성이다
  // 테스트 코드: US-099
  it('opens a dialog with the current role selected and the 변경 button disabled', async () => {
    // given: 사용자 관리 화면
    const { user } = await openUsers()

    // when: kim의 역할 변경을 연다
    const dialog = await openRoleDialog(user, 'kim')

    // then: 현재 역할 sales가 선택되고 변경 버튼이 비활성이다
    expect(dialog.getByLabelText('역할')).toHaveValue('sales')
    expect(dialog.getByRole('button', { name: '변경' })).toBeDisabled()
    expect(within(await screen.findByRole('dialog')).getByText(/kim \(김영업\)/)).toBeInTheDocument()
    expect(within(screen.getByRole('dialog')).getByText(/다음 요청부터 적용/)).toBeInTheDocument()
  })

  // 역할 선택지는 admin·sales·user다
  // 테스트 코드: US-099
  it('offers admin, sales and user', async () => {
    // given: 사용자 관리 화면
    const { user } = await openUsers()

    // when: kim의 역할 변경을 연다
    const dialog = await openRoleDialog(user, 'kim')

    // then: 선택지가 세 값이다
    expect(within(dialog.getByLabelText('역할')).getAllByRole('option').map((o) => o.textContent)).toEqual(['admin', 'sales', 'user'])
  })

  // 다른 역할을 골라야 변경 버튼이 켜진다
  // 테스트 코드: US-099
  it('enables 변경 only for a different role', async () => {
    // given: kim의 역할 변경 대화상자
    const { user } = await openUsers()
    const dialog = await openRoleDialog(user, 'kim')

    // when: 다른 역할 user를 고른다
    await user.selectOptions(dialog.getByLabelText('역할'), 'user')
    // then: 변경이 활성이다
    expect(dialog.getByRole('button', { name: '변경' })).toBeEnabled()

    // when: 다시 원래 역할을 고른다
    await user.selectOptions(dialog.getByLabelText('역할'), 'sales')
    // then: 변경이 비활성이다
    expect(dialog.getByRole('button', { name: '변경' })).toBeDisabled()
  })

  // 역할을 바꾸면 대화상자가 닫히고 알림과 역할 칸이 바뀐다
  // 테스트 코드: US-100
  it('changes the role, closes the dialog, announces it and updates the role cell', async () => {
    // given: kim의 역할 변경 대화상자에서 user를 고른 상태
    const { user } = await openUsers()
    const dialog = await openRoleDialog(user, 'kim')
    await user.selectOptions(dialog.getByLabelText('역할'), 'user')

    // when: 변경을 누른다
    await user.click(dialog.getByRole('button', { name: '변경' }))

    // then: 알림이 보이고 대화상자가 닫히며 역할 칸이 user다
    expect(await inPage().findByRole('status')).toHaveTextContent('kim 사용자의 역할이 sales에서 user(으)로 바뀌었습니다.')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await waitFor(() => expect(within(rowOf('kim')).getByText('user')).toBeInTheDocument())
    expect(within(rowOf('kim')).queryByText('sales')).not.toBeInTheDocument()
  })

  // 변경을 누르면 대상 id와 고른 역할이 게이트웨이로 간다
  // 테스트 코드: US-100
  it('sends the user id and the chosen role to the gateway', async () => {
    // given: han의 역할 변경 대화상자에서 sales를 고른 상태
    const changeRole = vi.spyOn(gateway.users, 'changeRole')
    const { user } = await openUsers()
    const dialog = await openRoleDialog(user, 'han')
    await user.selectOptions(dialog.getByLabelText('역할'), 'sales')

    // when: 변경을 누른다
    await user.click(dialog.getByRole('button', { name: '변경' }))

    // then: 게이트웨이가 한 번 han의 id와 sales로 호출된다
    await waitFor(() => expect(changeRole).toHaveBeenCalledTimes(1))
    expect(changeRole).toHaveBeenCalledWith(USER_ID.han, 'sales')
  })

  // 역할 변경 취소는 요청하지 않는다
  // 테스트 코드: US-101
  it('does nothing when the dialog is cancelled', async () => {
    // given: kim의 역할 변경 대화상자에서 user를 고른 상태
    const changeRole = vi.spyOn(gateway.users, 'changeRole')
    const { user } = await openUsers()
    const dialog = await openRoleDialog(user, 'kim')
    await user.selectOptions(dialog.getByLabelText('역할'), 'user')

    // when: 취소를 누른다
    await user.click(dialog.getByRole('button', { name: '취소' }))

    // then: 대화상자가 닫히고 요청이 없으며 kim은 sales 그대로다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(changeRole).not.toHaveBeenCalled()
    expect(within(rowOf('kim')).getByText('sales')).toBeInTheDocument()
  })

  // 역할 변경이 거절되면 대화상자를 닫고 오류 배너를 보인다
  // 테스트 코드: US-102
  it('shows the server message in the page error banner when the change is refused', async () => {
    // given: 역할 변경이 서버 오류로 실패하는 게이트웨이
    const error = await serverError()
    const { user } = await openUsers()
    vi.spyOn(gateway.users, 'changeRole').mockRejectedValue(error)
    const dialog = await openRoleDialog(user, 'kim')
    await user.selectOptions(dialog.getByLabelText('역할'), 'user')

    // when: 변경을 누른다
    await user.click(dialog.getByRole('button', { name: '변경' }))

    // then: 서버 문구가 배너에 보이고 대화상자가 닫히며 역할은 그대로다
    expect(await screen.findByRole('alert')).toHaveTextContent(SERVER_MESSAGE)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(within(rowOf('kim')).getByText('sales')).toBeInTheDocument()
  })

  // 다음 변경이 실패하면 이전 성공 알림을 지운다
  // 테스트 코드: US-102
  it('clears the previous result message when the next change fails', async () => {
    // given: 한 번 변경에 성공해 알림이 떠 있고 다음 변경은 실패한다
    const error = await serverError()
    const { user } = await openUsers()
    let dialog = await openRoleDialog(user, 'kim')
    await user.selectOptions(dialog.getByLabelText('역할'), 'user')
    await user.click(dialog.getByRole('button', { name: '변경' }))
    await inPage().findByRole('status')
    vi.spyOn(gateway.users, 'changeRole').mockRejectedValue(error)

    dialog = await openRoleDialog(user, 'park')
    await user.selectOptions(dialog.getByLabelText('역할'), 'user')
    // when: park의 역할 변경을 누른다
    await user.click(dialog.getByRole('button', { name: '변경' }))

    // then: 오류 배너가 보이고 이전 알림은 사라진다
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(inPage().queryByRole('status')).not.toBeInTheDocument()
  })

  // sales를 다른 역할로 고르면 Owner 안내를 보인다
  // 테스트 코드: US-103
  it('warns about owner eligibility when a sales user is moved to another role', async () => {
    // given: sales인 kim의 역할 변경 대화상자
    const { user } = await openUsers()
    const dialog = await openRoleDialog(user, 'kim')
    expect(dialog.queryByText(OWNER_WARNING)).not.toBeInTheDocument()

    // when: 역할을 user로 고른다
    await user.selectOptions(dialog.getByLabelText('역할'), 'user')

    // then: Owner 안내 문구가 보인다
    expect(dialog.getByText(OWNER_WARNING)).toBeInTheDocument()
  })

  // sales가 아니거나 sales로 두면 Owner 안내가 없다
  // 테스트 코드: US-103
  it('does not warn when the user was not sales or stays sales', async () => {
    // given: sales가 아닌 han의 역할 변경 대화상자
    const { user } = await openUsers()
    const dialog = await openRoleDialog(user, 'han')

    // when: sales를 고른다
    await user.selectOptions(dialog.getByLabelText('역할'), 'sales')
    // then: 안내가 없다
    expect(dialog.queryByText(OWNER_WARNING)).not.toBeInTheDocument()

    // when: admin을 고른다
    await user.selectOptions(dialog.getByLabelText('역할'), 'admin')
    // then: 안내가 없다
    expect(dialog.queryByText(OWNER_WARNING)).not.toBeInTheDocument()
  })

  // 역할을 바꾸면 선택 목록과 Deal 목록을 다시 읽게 한다
  // 테스트 코드: US-107
  it('invalidates user-options and the deal lists after a role change', async () => {
    // given: 선택 목록과 Deal 목록이 캐시에 있다
    const { user, client } = await openUsers()
    const queryKey = keys.userOptions({ role: 'sales' })
    await client.prefetchQuery({ queryKey, queryFn: () => gateway.users.options({ role: 'sales' }) })
    await client.prefetchQuery({ queryKey: keys.dealList({}), queryFn: () => gateway.deals.list({}) })
    const dialog = await openRoleDialog(user, 'kim')
    await user.selectOptions(dialog.getByLabelText('역할'), 'user')

    // when: kim의 역할을 바꾼다
    await user.click(dialog.getByRole('button', { name: '변경' }))

    // then: 두 조회가 모두 무효화된다
    await waitFor(() => expect(client.getQueryState(queryKey)?.isInvalidated).toBe(true))
    await waitFor(() => expect(client.getQueryState(keys.dealList({}))?.isInvalidated).toBe(true))
  })

  // 역할을 바꾼 사용자는 sales 선택 목록에서 빠진다
  // 테스트 코드: US-107
  it('drops the changed user from the sales owner options', async () => {
    // given: sales인 kim
    const { user } = await openUsers()
    const dialog = await openRoleDialog(user, 'kim')
    await user.selectOptions(dialog.getByLabelText('역할'), 'user')
    // when: kim을 user로 바꾼다
    await user.click(dialog.getByRole('button', { name: '변경' }))
    await inPage().findByRole('status')

    const sales = await gateway.users.options({ role: 'sales' })

    // then: sales 선택 목록에 kim이 없다
    expect(sales.map((u) => u.id)).not.toContain(USER_ID.kim)
  })
})

