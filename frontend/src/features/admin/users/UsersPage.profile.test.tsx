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

describe('사용자 목록의 이메일·전화번호 열', () => {
  // 표에 이메일·전화번호 열이 있고 없는 값은 -로 보인다
  // 테스트 코드: US-078
  it('lists the email and phone columns and "-" for a missing value', async () => {
    // when: 사용자 관리 화면을 연다 (전제: local 모드)
    await openUsers(true)

    // then: 열 머리글이 있고 kim 행에 이메일이 보이며 전화번호는 -다
    expect(screen.getByRole('columnheader', { name: '이메일' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '전화번호' })).toBeInTheDocument()
    const kim = within(rowOf('kim'))
    expect(kim.getByText('kim@neoine.test')).toBeInTheDocument()
    expect(kim.getAllByText('-').length).toBeGreaterThanOrEqual(1) // 전화번호 없음
  })

  // 저장한 전화번호가 행에 보인다
  // 테스트 코드: US-078
  it('shows a saved phone on the row', async () => {
    // given: local 모드 화면
    const { client } = await openUsers(true)

    // when: kim의 전화번호를 저장하고 목록을 다시 읽는다
    await gateway.users.update(USER_ID.kim, { phone: '010-1234-5678' })
    await client.invalidateQueries()

    // then: 행에 전화번호가 보인다
    expect(await within(rowOf('kim')).findByText('010-1234-5678')).toBeInTheDocument()
  })
})

describe('정보 수정', () => {
  // 다른 사용자에게는 정보 수정이 있고 본인 행에는 없다
  // 테스트 코드: US-083
  it('offers 정보 수정 on other users but not on the signed-in admin row', async () => {
    // when: 사용자 관리 화면을 연다 (전제: local 모드)
    await openUsers(true)

    // then: kim 행에는 정보 수정이 있고 root 행에는 없다
    expect(within(rowOf('kim')).getByRole('button', { name: '정보 수정' })).toBeInTheDocument()
    expect(within(rowOf('root')).queryByRole('button', { name: '정보 수정' })).not.toBeInTheDocument()
  })

  // 정보 수정 대화상자는 현재 값을 채워 연다
  // 테스트 코드: US-092
  it('opens a dialog filled with the current values', async () => {
    // given: local 모드
    const { user } = await openUsers(true)

    // when: kim의 정보 수정을 연다
    await user.click(within(rowOf('kim')).getByRole('button', { name: '정보 수정' }))

    // then: 이름·이메일·전화번호에 현재 값이 채워진다
    const d = await dialog('정보 수정')
    expect(d.getByLabelText('이름')).toHaveValue('김영업')
    expect(d.getByLabelText('이메일')).toHaveValue('kim@neoine.test')
    expect(d.getByLabelText('전화번호')).toHaveValue('')
    expect(d.getByLabelText('이름')).toBeEnabled()
  })

  // 정보 수정은 바뀐 칸만 저장하고 대화상자를 닫는다
  // 테스트 코드: US-092
  it('saves only the changed fields, closes the dialog and refreshes the row', async () => {
    // given: kim의 정보 수정 대화상자
    const { user } = await openUsers(true)
    const update = vi.spyOn(gateway.users, 'update')
    await user.click(within(rowOf('kim')).getByRole('button', { name: '정보 수정' }))
    const d = await dialog('정보 수정')
    await replace(user, d, '이름', '김새이름')
    await user.type(d.getByLabelText('전화번호'), '02-123-4567')

    // when: 이름·전화를 고쳐 저장한다
    await user.click(d.getByRole('button', { name: '저장' }))

    // then: 바뀐 칸만 게이트웨이로 가고 대화상자가 닫히며 행이 갱신된다
    expect(await screen.findByRole('cell', { name: '김새이름' })).toBeInTheDocument()
    expect(update).toHaveBeenCalledTimes(1)
    expect(update).toHaveBeenCalledWith(USER_ID.kim, { name: '김새이름', phone: '02-123-4567' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(within(rowOf('kim')).getByText('02-123-4567')).toBeInTheDocument()
  })

  // 바뀐 게 없으면 저장 버튼이 비활성이다
  // 테스트 코드: US-092
  it('keeps the save button disabled until something changes', async () => {
    // given: local 모드
    const { user } = await openUsers(true)
    // when: 정보 수정을 연다
    await user.click(within(rowOf('kim')).getByRole('button', { name: '정보 수정' }))

    const d = await dialog('정보 수정')

    // then: 저장 버튼이 비활성이다
    expect(d.getByRole('button', { name: '저장' })).toBeDisabled()
  })

  // 정보 수정이 거절되면 서버 문구를 보이고 대화상자를 열어 둔다
  // 테스트 코드: US-093
  it('shows the server message and keeps the dialog open for an invalid email', async () => {
    // given: 이메일을 잘못 고친 정보 수정 대화상자
    const { user } = await openUsers(true)
    await user.click(within(rowOf('kim')).getByRole('button', { name: '정보 수정' }))
    const d = await dialog('정보 수정')
    await replace(user, d, '이메일', 'not-an-email')

    // when: 저장을 누른다
    await user.click(d.getByRole('button', { name: '저장' }))

    // then: 서버 문구가 대화상자 안에 보이고 입력이 유지된다
    expect(await d.findByRole('alert')).toHaveTextContent('이메일 형식이 올바르지 않습니다.')
    expect(d.getByLabelText('이메일')).toHaveValue('not-an-email')
  })

  // 정보 수정 취소는 요청하지 않는다
  // 테스트 코드: US-094
  it('cancels without calling the server', async () => {
    // given: 정보 수정 대화상자와 update 감시
    const { user } = await openUsers(true)
    const update = vi.spyOn(gateway.users, 'update')
    await user.click(within(rowOf('kim')).getByRole('button', { name: '정보 수정' }))

    // when: 취소를 누른다
    await user.click((await dialog('정보 수정')).getByRole('button', { name: '취소' }))

    // then: 대화상자가 닫히고 update가 호출되지 않는다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(update).not.toHaveBeenCalled()
  })

  // AD 모드 정보 수정은 이름·이메일을 막고 전화만 보낸다
  // 테스트 코드: US-095
  it('lets the admin edit only the phone in AD mode', async () => {
    // given: AD 모드의 정보 수정 대화상자
    const { user } = await openUsers(false)
    const update = vi.spyOn(gateway.users, 'update')
    await user.click(within(rowOf('kim')).getByRole('button', { name: '정보 수정' }))
    const d = await dialog('정보 수정')

    expect(d.getByLabelText('이름')).toBeDisabled()
    expect(d.getByLabelText('이메일')).toBeDisabled()
    expect(d.getByLabelText('전화번호')).toBeEnabled()
    expect(d.getByText(/이름·이메일은 AD에서 관리합니다/)).toBeInTheDocument()
    await user.type(d.getByLabelText('전화번호'), '02-123-4567')
    // when: 전화를 입력해 저장한다
    await user.click(d.getByRole('button', { name: '저장' }))

    // then: 이름·이메일 칸은 비활성이고 전화만 게이트웨이로 간다
    await screen.findByText('02-123-4567')
    expect(update).toHaveBeenCalledWith(USER_ID.kim, { phone: '02-123-4567' })
  })

  // 퇴사 행에는 정보 수정 버튼이 없다
  // 테스트 코드: US-080
  it('does not offer 정보 수정 on a resigned user', async () => {
    // given: local 모드
    const { user } = await openUsers(true)

    // when: 상태를 전체로 고른다
    await user.selectOptions(screen.getByLabelText('상태'), '전체')

    // then: old 행에 정보 수정 버튼이 없다
    expect(within(await screen.findByRole('row', { name: /^old\b/ })).queryByRole('button', { name: '정보 수정' })).not.toBeInTheDocument()
  })
})

describe('비밀번호 재설정', () => {
  // local 모드는 다른 재직 행에 비밀번호 재설정 버튼을 둔다
  // 테스트 코드: US-085
  it('offers 비밀번호 재설정 on other users in local mode but not on the admin row', async () => {
    // when: 사용자 관리 화면을 연다 (전제: local 모드)
    await openUsers(true)

    // then: kim 행에는 버튼이 있고 root 행에는 없다
    expect(within(rowOf('kim')).getByRole('button', { name: '비밀번호 재설정' })).toBeInTheDocument()
    expect(within(rowOf('root')).queryByRole('button', { name: '비밀번호 재설정' })).not.toBeInTheDocument()
  })

  // AD 모드에는 비밀번호 재설정 버튼이 없다
  // 테스트 코드: US-084
  it('is not offered in AD mode', async () => {
    // when: 사용자 관리 화면을 연다 (전제: AD 모드)
    await openUsers(false)

    // then: 버튼이 없다
    expect(screen.queryByRole('button', { name: '비밀번호 재설정' })).not.toBeInTheDocument()
  })

  // 비밀번호를 재설정하면 대화상자가 닫히고 로그인 종료 안내가 보인다
  // 테스트 코드: US-096
  it('resets the password, closes the dialog and says the sessions of that user ended', async () => {
    // given: kim의 재설정 대화상자에 새 비밀번호와 확인을 입력한 상태
    const { user } = await openUsers(true)
    const reset = vi.spyOn(gateway.users, 'resetPassword')
    await user.click(within(rowOf('kim')).getByRole('button', { name: '비밀번호 재설정' }))
    const d = await dialog('비밀번호 재설정')
    await user.type(d.getByLabelText('새 비밀번호'), 'Fresh-passw0rd')
    await user.type(d.getByLabelText('새 비밀번호 확인'), 'Fresh-passw0rd')

    // when: 재설정을 누른다
    await user.click(d.getByRole('button', { name: '재설정' }))

    // then: 안내가 보이고 게이트웨이가 한 번 호출되며 대화상자가 닫힌다
    expect(await screen.findByText(/kim 사용자의 비밀번호가 재설정되었습니다/)).toBeInTheDocument()
    expect(screen.getByText(/로그인은 모두 종료됩니다/)).toBeInTheDocument()
    expect(reset).toHaveBeenCalledTimes(1)
    expect(reset).toHaveBeenCalledWith(USER_ID.kim, 'Fresh-passw0rd')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 새 비밀번호 확인이 다르면 요청하지 않는다
  // 테스트 코드: US-097
  it('does not submit when the confirmation differs', async () => {
    // given: 확인이 다른 비밀번호를 입력한 재설정 대화상자
    const { user } = await openUsers(true)
    const reset = vi.spyOn(gateway.users, 'resetPassword')
    await user.click(within(rowOf('kim')).getByRole('button', { name: '비밀번호 재설정' }))
    const d = await dialog('비밀번호 재설정')
    await user.type(d.getByLabelText('새 비밀번호'), 'Fresh-passw0rd')
    await user.type(d.getByLabelText('새 비밀번호 확인'), 'Fresh-passw0rX')

    // when: 재설정을 누른다
    await user.click(d.getByRole('button', { name: '재설정' }))

    // then: 확인 불일치 문구가 보이고 요청이 없다
    expect(await d.findByRole('alert')).toHaveTextContent('새 비밀번호 확인이 일치하지 않습니다.')
    expect(reset).not.toHaveBeenCalled()
  })

  // 재설정이 거절되면 서버 문구를 보이고 대화상자를 열어 둔다
  // 테스트 코드: US-098
  it('shows the server message for a weak password and keeps the dialog open', async () => {
    // given: 약한 비밀번호를 입력한 재설정 대화상자
    const { user } = await openUsers(true)
    await user.click(within(rowOf('kim')).getByRole('button', { name: '비밀번호 재설정' }))
    const d = await dialog('비밀번호 재설정')
    await user.type(d.getByLabelText('새 비밀번호'), 'short7!')
    await user.type(d.getByLabelText('새 비밀번호 확인'), 'short7!')

    // when: 재설정을 누른다
    await user.click(d.getByRole('button', { name: '재설정' }))

    // then: 서버 문구가 보이고 대화상자가 열려 있다
    expect(await d.findByRole('alert')).toHaveTextContent('비밀번호는 8자 이상이어야 합니다')
    expect(screen.getByRole('dialog', { name: '비밀번호 재설정' })).toBeInTheDocument()
  })

  // 사용자 목록에는 비밀번호가 보이지 않는다
  it('never shows a password in the user list', async () => {
    // when: 사용자 관리 화면을 연다 (전제: local 모드)
    await openUsers(true)

    // then: 표에 비밀번호라는 글자가 없다
    expect(within(screen.getByRole('table')).queryByText(/비밀번호|password/i)).not.toBeInTheDocument()
  })
})
