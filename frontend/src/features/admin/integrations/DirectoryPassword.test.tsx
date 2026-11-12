import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { SEED_PASSWORD } from '../../../test/fake/seed/users'
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

const loadedRevision = () => Number(/설정 버전 (\d+)/.exec(directory().getByText(/설정 버전 \d+/).textContent ?? '')?.[1])

describe('외부연동 AD 설정의 현재 관리자 비밀번호', () => {
  // 테스트 코드: IN-063
  it('현재 관리자 비밀번호를 password 형식의 빈 칸과 안내 문구로 요구하고 개발용 로그인 문구가 없다', async () => {
    // when: 외부연동 화면을 연다 (전제: 예시 AD 설정이 보인다)
    await openIntegrations()

    // then: 비밀번호 칸은 password 형식의 빈 칸이고 안내 문구가 있으며 개발용 로그인 언급은 없다
    const password = directory().getByLabelText(/현재 관리자 비밀번호/)
    expect(password).toHaveAttribute('type', 'password')
    expect(password).toHaveValue('')
    expect(directory().getByText('현재 관리자(본인) 비밀번호를 입력하세요.')).toBeVisible()
    expect(directory().queryByText(/개발용 로그인/)).not.toBeInTheDocument()
  })

  // 테스트 코드: IN-063
  it('저장하면 입력한 현재 관리자 비밀번호와 읽은 설정 버전을 보낸다', async () => {
    // given: 예시 AD 설정(읽은 설정 버전)이 보이고 현재 관리자 비밀번호를 넣었다
    const save = vi.spyOn(gateway.settings, 'saveDirectory')
    const { user } = await openIntegrations()
    const revision = loadedRevision()
    await user.type(directory().getByLabelText(/현재 관리자 비밀번호/), SEED_PASSWORD)

    // when: 저장을 누른다
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: 저장되고 요청에는 그 비밀번호와 읽은 설정 버전이 실렸다
    await directory().findByText('저장했습니다')
    expect(save).toHaveBeenCalledWith(expect.anything(), { password: SEED_PASSWORD, expectedRevision: revision })
  })

  // 테스트 코드: IN-063
  it('연결 테스트도 현재 관리자 비밀번호를 보내고 저장하지 않는다', async () => {
    // given: 현재 관리자 비밀번호를 넣었다
    const test = vi.spyOn(gateway.settings, 'testDirectory')
    const save = vi.spyOn(gateway.settings, 'saveDirectory')
    const { user } = await openIntegrations()
    await user.type(directory().getByLabelText(/현재 관리자 비밀번호/), SEED_PASSWORD)

    // when: 연결 테스트를 누른다
    await user.click(directory().getByRole('button', { name: '연결 테스트' }))

    // then: 성공하고 테스트 요청에 비밀번호가 실렸으며 저장 요청은 없었다
    await directory().findByText('연결 테스트에 성공했습니다.')
    expect(test).toHaveBeenCalledWith(expect.anything(), SEED_PASSWORD)
    expect(save).not.toHaveBeenCalled()
  })

  // 테스트 코드: IN-063
  it('비밀번호 칸을 비운 채 누르면 null을 보내고 서버의 비밀번호 필요 문구를 보인다', async () => {
    // given: 현재 관리자 비밀번호 칸이 비어 있다
    const save = vi.spyOn(gateway.settings, 'saveDirectory')
    const test = vi.spyOn(gateway.settings, 'testDirectory')
    const { user } = await openIntegrations()
    const revision = loadedRevision()

    // when: 연결 테스트를 누르고 이어서 저장을 누른다
    await user.click(directory().getByRole('button', { name: '연결 테스트' }))
    await directory().findByRole('alert')
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: 두 요청 모두 비밀번호 null이고 서버 문구가 보이며 설정 버전은 그대로다
    expect(test).toHaveBeenCalledWith(expect.anything(), null)
    expect(save).toHaveBeenCalledWith(expect.anything(), { password: null, expectedRevision: revision })
    expect(await directory().findByRole('alert')).toHaveTextContent('AD 설정을 확인하려면 현재 관리자의 비밀번호가 필요합니다')
    expect(directory().getByText(`설정 버전 ${revision}`)).toBeInTheDocument()
  })

  // 테스트 코드: IN-064
  it('요청이 끝나면 성공이든 실패든 현재 관리자 비밀번호 칸을 비운다', async () => {
    // given: 현재 관리자 비밀번호를 넣었다
    const { user } = await openIntegrations()
    const field = directory().getByLabelText(/현재 관리자 비밀번호/)
    await user.type(field, SEED_PASSWORD)

    // when: 저장이 성공한다
    await user.click(directory().getByRole('button', { name: '저장' }))
    await directory().findByText('저장했습니다')

    // then: 칸이 비었다
    expect(field).toHaveValue('')

    // given: 다시 비밀번호를 넣고 연결 테스트가 실패하도록 정했다
    const failure = new ApiError(422, { type: 'https://x/problems/validation', title: 't', status: 422, detail: '비밀번호가 올바르지 않습니다.' })
    vi.spyOn(gateway.settings, 'testDirectory').mockRejectedValue(failure)
    await user.type(field, 'wrong-pw')

    // when: 연결 테스트가 실패한다
    await user.click(directory().getByRole('button', { name: '연결 테스트' }))
    await directory().findByRole('alert')

    // then: 칸이 다시 비었다
    expect(field).toHaveValue('')
  })
})
