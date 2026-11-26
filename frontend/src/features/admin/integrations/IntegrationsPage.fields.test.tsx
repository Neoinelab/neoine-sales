import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import type { DirectorySettings } from '../../../shared/model/types'
import { selectSecurity, setField } from '../../../test/directoryForm'
import { renderAt } from '../../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

const REMOVED_LABELS = [/서버 URL/, /StartTLS 사용/, /CA 인증서/, /바인드 템플릿/, /^Base DN/, /표시 이름 속성/, /이메일 속성/, /응답 제한 시간/]

async function openSettings(saved: DirectorySettings | null) {
  vi.spyOn(gateway.settings, 'getDirectory').mockResolvedValue(saved)
  const view = await renderAt('/admin/integrations', { role: 'admin' })
  await screen.findByRole('heading', { name: 'AD(LDAP) 서버 설정' })
  await screen.findByLabelText(/^호스트/)
  return view
}

const directory = () => within(screen.getByRole('region', { name: 'AD(LDAP) 서버 설정' }))
const port = () => screen.getByLabelText(/^포트/)

describe('외부연동 AD 등록 폼의 입력 칸', () => {
  // 테스트 코드: IN-069
  it('입력 칸은 5개뿐이고 폐지된 칸이 없으며 새 폼 기본값을 보인다', async () => {
    // when: 외부연동 화면의 등록 폼을 본다 (전제: AD 설정이 없다)
    await openSettings(null)

    // then: 7칸+admin 비밀번호 8개 입력, 폐지된 칸 없음, 보안 연결 선택지와 기본값
    const form = screen.getByLabelText(/^호스트/).closest('form') as HTMLFormElement
    expect(form.querySelectorAll('input, select, textarea')).toHaveLength(5)
    for (const label of [/^호스트/, /^포트/, /^보안 연결/, /사용자 검색 필터/, /연결 제한 시간/]) {
      expect(within(form).getByLabelText(label)).toBeInTheDocument()
    }
    for (const label of REMOVED_LABELS) expect(screen.queryByLabelText(label)).not.toBeInTheDocument()
    const options = within(screen.getByLabelText(/^보안 연결/)).getAllByRole('option')
    expect(options.map((o) => [(o as HTMLOptionElement).value, o.textContent])).toEqual([
      ['none', '없음'],
      ['ssl', 'SSL'],
      ['starttls', 'StartTLS'],
    ])
    expect(screen.getByLabelText(/^보안 연결/)).toHaveValue('ssl')
    expect(port()).toHaveValue(636)
    expect(screen.getByLabelText(/사용자 검색 필터/)).toHaveValue('(&(objectClass=user)(sAMAccountName={login_id}))')
    expect(screen.getByLabelText(/연결 제한 시간/)).toHaveValue(5)
    expect(screen.queryByLabelText(/바인드/)).not.toBeInTheDocument()
  })

  // 테스트 코드: IN-070
  it('보안 연결을 바꾸면 기본 포트로 바꾸고 직접 쓴 포트는 둔다', async () => {
    // given: 등록 폼이 SSL 636으로 열려 있다
    const { user } = await openSettings(null)

    // when: StartTLS로 바꾼다
    await selectSecurity(user, 'starttls')
    // then: 포트는 389다
    expect(port()).toHaveValue(389)

    // when: SSL로 돌린 뒤 포트를 비우고 없음으로 바꾼다
    await selectSecurity(user, 'ssl')
    setField(/^포트/, '')
    await selectSecurity(user, 'none')
    // then: 포트는 389다
    expect(port()).toHaveValue(389)

    // when: 포트를 10636으로 쓰고 StartTLS로 바꾼다
    setField(/^포트/, '10636')
    await selectSecurity(user, 'starttls')
    // then: 직접 쓴 10636이 남는다
    expect(port()).toHaveValue(10636)
  })

  // 테스트 코드: IN-071
  it('보안 연결마다 암호화·인증서 경고를 보이고 평문 경고는 없음일 때만 보인다', async () => {
    // given: 등록 폼
    const { user } = await openSettings(null)

    // when: 없음을 고른다
    await selectSecurity(user, 'none')
    // then: 평문 경고만 보인다
    expect(directory().getByText('보안 연결 없음: 비밀번호가 암호화되지 않은 채 전송됩니다. 신뢰하는 내부망에서만 쓰세요.')).toBeInTheDocument()
    expect(directory().queryByText(/서버 인증서를 검증하지 않습니다/)).not.toBeInTheDocument()

    // when: SSL을 고른다
    await selectSecurity(user, 'ssl')
    // then: SSL 인증서 경고만 보인다
    expect(directory().getByText('SSL: 연결은 암호화되지만 서버 인증서를 검증하지 않습니다.')).toBeInTheDocument()
    expect(directory().queryByText(/암호화되지 않은 채 전송됩니다/)).not.toBeInTheDocument()

    // when: StartTLS를 고른다
    await selectSecurity(user, 'starttls')
    // then: StartTLS 인증서 경고가 보인다
    expect(directory().getByText('StartTLS: 연결은 암호화되지만 서버 인증서를 검증하지 않습니다.')).toBeInTheDocument()
  })
})
