import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import type { DirectoryTestResult } from '../../../gateway/types'
import { ApiError } from '../../../shared/api/problem'
import { setField } from '../../../test/directoryForm'
import { DIRECTORY_SAVED } from '../../../test/directoryFixtures'
import { SEED_PASSWORD } from '../../../test/fake/seed/users'
import { renderAt } from '../../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

const problem = (status: number, kind: string, detail: string) =>
  new ApiError(status, { type: `https://neoine-sales.example/problems/${kind}`, title: kind, status, detail })

async function openIntegrations() {
  const view = await renderAt('/admin/integrations', { role: 'admin' })
  await screen.findByRole('heading', { name: 'AD(LDAP) 서버 설정' })
  await screen.findByLabelText(/^호스트/)
  return view
}

function directory() {
  return within(screen.getByRole('region', { name: 'AD(LDAP) 서버 설정' }))
}

function storage() {
  return within(screen.getByRole('region', { name: '파일 저장 위치' }))
}

const adminPassword = () => directory().getByLabelText(/현재 관리자 비밀번호/)

describe('외부연동 AD 설정 조회', () => {
  // 테스트 코드: IN-059
  it('AD 모드에서 저장된 설정을 폼에 보이고 Base DN은 읽기 전용 텍스트, 비밀번호는 마스크로 보인다', async () => {
    // when: admin이 외부연동 화면을 연다 (전제: AD 모드이고 예시 AD 설정이 저장되어 있다)
    await openIntegrations()

    // then: 7칸에 저장 값이 보이고 바인드 비밀번호는 마스크이며 Base DN은 입력 칸이 아닌 텍스트다
    expect(screen.getByLabelText(/^호스트/)).toHaveValue('dc1.corp.test')
    expect(screen.getByLabelText(/^포트/)).toHaveValue(636)
    expect(screen.getByLabelText(/^보안 연결/)).toHaveValue('ssl')
    expect(screen.getByLabelText(/^바인드 비밀번호/)).toHaveValue('********')
    expect(screen.getByLabelText(/연결 제한 시간/)).toHaveValue(5)
    expect(directory().getByText(/^Base DN\(AD에서 자동 확인\):/)).toHaveTextContent('Base DN(AD에서 자동 확인): dc=corp,dc=test')
    expect(screen.queryByLabelText(/^Base DN/)).not.toBeInTheDocument()
  })

  // 테스트 코드: IN-060
  it('마지막 수정자·시각과 설정 버전을 보인다', async () => {
    // given: 최관리가 revision 3으로 저장한 AD 설정
    vi.spyOn(gateway.settings, 'getDirectory').mockResolvedValue({
      ...DIRECTORY_SAVED,
      revision: 3,
      updatedBy: { id: 1, name: '최관리', role: 'admin', status: 'active' },
    })

    // when: 외부연동 화면을 연다
    await openIntegrations()

    // then: 마지막 수정 표시와 설정 버전 3이 보인다
    expect(directory().getByText(/마지막 수정: 최관리 · .+/)).toBeInTheDocument()
    expect(directory().getByText('설정 버전 3')).toBeInTheDocument()
  })

  // 테스트 코드: IN-061
  it('AD 설정을 불러오지 못하면 서버 문구의 오류 배너를 보이고 AD 폼은 없다', async () => {
    // given: AD 설정 조회가 500 Problem으로 실패한다
    vi.spyOn(gateway.settings, 'getDirectory').mockRejectedValue(problem(500, 'internal', '설정을 불러오지 못했습니다'))

    // when: 외부연동 화면을 연다
    await renderAt('/admin/integrations', { role: 'admin' })

    // then: 그 문구의 오류 배너가 보이고 호스트 칸이 없다
    expect(await screen.findByRole('alert')).toHaveTextContent('설정을 불러오지 못했습니다')
    expect(screen.queryByLabelText(/^호스트/)).not.toBeInTheDocument()
  })
})

describe('외부연동 AD 설정 저장·연결 테스트', () => {
  // 테스트 코드: IN-062
  it('저장하면 저장했습니다와 함께 설정 버전·마지막 수정이 바뀐다', async () => {
    // given: 예시 AD 설정이 보이고 연결 제한 시간을 9로 바꿨다
    const { user } = await openIntegrations()
    const before = Number(/설정 버전 (\d+)/.exec(directory().getByText(/설정 버전 \d+/).textContent ?? '')?.[1])
    setField(/연결 제한 시간/, '9')
    await user.type(adminPassword(), SEED_PASSWORD)

    // when: 현재 admin 비밀번호를 넣고 저장을 누른다
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: 저장했습니다, 설정 버전 +1, 새 마지막 수정이 보인다
    expect(await directory().findByText('저장했습니다')).toBeInTheDocument()
    expect(directory().getByText(`설정 버전 ${before + 1}`)).toBeInTheDocument()
    expect(directory().getByText(/마지막 수정: 최관리 · /)).toBeInTheDocument()
    expect(screen.getByLabelText(/연결 제한 시간/)).toHaveValue(9)
  })

  // 테스트 코드: IN-065
  it('연결 테스트는 저장하지 않고 찾은 Base DN을 보인다', async () => {
    // given: 예시 AD 설정이 보이고 호스트를 바꾸고 새 바인드 비밀번호·admin 비밀번호를 넣었다
    const { user } = await openIntegrations()
    const save = vi.spyOn(gateway.settings, 'saveDirectory')
    setField(/^호스트/, 'dc2.corp.test')
    await user.type(screen.getByLabelText(/^바인드 비밀번호/), 'New-bind-pw-1!')
    await user.type(adminPassword(), SEED_PASSWORD)

    // when: 연결 테스트를 누른다
    await user.click(directory().getByRole('button', { name: '연결 테스트' }))

    // then: Base DN이 든 성공 알림이 보이고 설정 버전은 그대로이며 저장 요청은 없었다
    expect(await directory().findByRole('status')).toHaveTextContent('연결 테스트에 성공했습니다. Base DN: dc=corp,dc=test')
    expect(directory().getByText('설정 버전 3')).toBeInTheDocument()
    expect(save).not.toHaveBeenCalled()
  })

  // 테스트 코드: IN-066
  it('연결 테스트가 실패하면 실패 단계 안내를 오류 알림으로 보인다', async () => {
    // given: 연결 테스트 결과가 connect 단계 실패다(호스트에 fail이 들어가면 Fake가 그렇게 답한다)
    const { user } = await openIntegrations()
    setField(/^호스트/, 'fail.corp.test')
    await user.type(screen.getByLabelText(/^바인드 비밀번호/), 'Typed-pw-1!')
    await user.type(adminPassword(), SEED_PASSWORD)

    // when: 연결 테스트를 누른다
    await user.click(directory().getByRole('button', { name: '연결 테스트' }))

    // then: connect 단계 안내가 오류 알림으로 보인다
    expect(await directory().findByRole('alert')).toHaveTextContent('AD 서버에 연결하지 못했습니다. 호스트·포트·방화벽을 확인하세요.')
  })

  // 테스트 코드: IN-067
  it('다음 동작을 시작하면 새 요청이 끝나기 전에 이전 결과 알림이 사라진다', async () => {
    // given: 이전 연결 테스트의 실패 알림이 보인다
    const { user } = await openIntegrations()
    vi.spyOn(gateway.settings, 'testDirectory').mockRejectedValueOnce(problem(422, 'invalid-value', 'port은(는) 1~65535 사이여야 합니다'))
    await user.click(directory().getByRole('button', { name: '연결 테스트' }))
    expect(await directory().findByRole('alert')).toBeInTheDocument()
    let finish: (result: DirectoryTestResult) => void = () => undefined
    vi.spyOn(gateway.settings, 'testDirectory').mockReturnValueOnce(new Promise<DirectoryTestResult>((resolve) => (finish = resolve)))

    // when: 다시 연결 테스트를 누른다(응답은 아직 없다)
    await user.click(directory().getByRole('button', { name: '연결 테스트' }))

    // then: 이전 알림이 먼저 사라지고, 응답이 오면 새 결과가 보인다
    await waitFor(() => expect(directory().queryByRole('alert')).not.toBeInTheDocument())
    finish({ baseDn: 'dc=corp,dc=test' })
    expect(await directory().findByRole('status')).toHaveTextContent('연결 테스트에 성공했습니다.')
  })

  // 테스트 코드: IN-068
  it('서버의 값 오류 문구를 화면이 미리 막지 않고 그대로 보인다', async () => {
    // given: 저장 요청이 422 invalid-value로 실패한다
    const { user } = await openIntegrations()
    vi.spyOn(gateway.settings, 'saveDirectory').mockRejectedValue(
      problem(422, 'invalid-value', 'user_filter은(는) 괄호로 감싸야 하고 괄호 짝이 맞아야 합니다'),
    )

    // when: 저장을 누른다
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: 서버 문구가 오류 알림으로 보인다
    expect(await directory().findByRole('alert')).toHaveTextContent('user_filter은(는) 괄호로 감싸야 하고 괄호 짝이 맞아야 합니다')
  })

  // 테스트 코드: IN-068
  it('현재 admin 비밀번호 없이 저장하면 서버의 비밀번호 필요 문구를 보인다', async () => {
    // given: 예시 AD 설정이 보이고 현재 admin 비밀번호 칸이 비어 있다
    const { user } = await openIntegrations()

    // when: 저장을 누른다
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: 서버의 422 문구가 오류 알림으로 보이고 설정 버전은 그대로다
    expect(await directory().findByRole('alert')).toHaveTextContent('AD 설정을 확인하려면 현재 관리자의 비밀번호가 필요합니다')
    expect(directory().getByText('설정 버전 3')).toBeInTheDocument()
  })
})

describe('외부연동 파일 저장 위치', () => {
  // 테스트 코드: IN-083
  it('저장 위치 섹션은 현재 위치·마지막 수정·수동 이동 안내·예시를 보인다', async () => {
    // given: 최초 설정으로 저장된 위치 /data/a(저장자 없음)
    vi.spyOn(gateway.settings, 'getStorage').mockResolvedValue({ path: '/data/a', updatedAt: '2026-10-15T09:00:00+09:00', updatedBy: null })

    // when: 외부연동 화면을 연다
    await openIntegrations()

    // then: 현재 위치, 마지막 수정(저장자 -), 수동 이동 안내, 경로 칸 값, 예시가 보인다
    expect(await storage().findByText('현재 위치: /data/a')).toBeInTheDocument()
    expect(storage().getByText(/^마지막 수정: - · /)).toBeInTheDocument()
    expect(storage().getByText(/위치를 바꿔도 기존 파일 이동은 관리자가 수작업으로 처리합니다. 기존 파일은 자동으로 옮겨지지 않습니다./)).toBeInTheDocument()
    expect(storage().getByLabelText('저장 경로')).toHaveValue('/data/a')
    expect(storage().getByText(/예: \/var\/lib\/neoine-sales\/files/)).toBeInTheDocument()
  })

  // 테스트 코드: IN-083
  it('저장 위치가 없으면 설정되지 않았다는 안내와 빈 경로 칸을 보인다', async () => {
    // given: 저장 위치가 없다
    vi.spyOn(gateway.settings, 'getStorage').mockResolvedValue(null)

    // when: 외부연동 화면을 연다
    await openIntegrations()

    // then: 안내 문구와 빈 경로 칸이 보인다
    expect(await storage().findByText('아직 저장 위치가 설정되지 않았습니다.')).toBeInTheDocument()
    expect(storage().getByLabelText('저장 경로')).toHaveValue('')
  })

  // 테스트 코드: IN-084
  it('저장 위치를 저장하면 서버가 정규화한 경로가 현재 위치가 된다', async () => {
    // given: 저장 위치 섹션이 보인다
    const { user } = await openIntegrations()
    const input = await storage().findByLabelText('저장 경로')
    await user.clear(input)
    await user.type(input, ' /data//files/ ')

    // when: 저장을 누른다
    await user.click(storage().getByRole('button', { name: '저장' }))

    // then: 저장했습니다와 정규화된 현재 위치가 보인다
    expect(await storage().findByRole('status')).toHaveTextContent('저장했습니다')
    expect(storage().getByText('현재 위치: /data/files')).toBeInTheDocument()
  })

  // 테스트 코드: IN-085
  it('상대 경로를 저장하면 서버의 절대 경로 문구가 보이고 현재 위치는 그대로다', async () => {
    // given: 저장 위치 섹션에 상대 경로를 넣었다
    const { user } = await openIntegrations()
    const input = await storage().findByLabelText('저장 경로')
    await user.clear(input)
    await user.type(input, 'data/files')

    // when: 저장을 누른다
    await user.click(storage().getByRole('button', { name: '저장' }))

    // then: 서버 문구가 오류 알림으로 보이고 현재 위치는 바뀌지 않는다
    expect(await storage().findByRole('alert')).toHaveTextContent('절대 경로를 입력하세요.')
    expect(storage().getByText('현재 위치: /data/neoine-sales/files')).toBeInTheDocument()
  })

  // 테스트 코드: IN-086
  it('쓰기 테스트는 저장하지 않고 성공을 알린다', async () => {
    // given: 저장 위치 섹션이 보인다
    const { user } = await openIntegrations()
    const save = vi.spyOn(gateway.settings, 'saveStorage')
    const input = await storage().findByLabelText('저장 경로')
    await user.clear(input)
    await user.type(input, '/data/b')

    // when: 쓰기 테스트를 누른다
    await user.click(storage().getByRole('button', { name: '쓰기 테스트' }))

    // then: 성공 문구가 보이고 현재 위치는 그대로이며 저장 요청은 없었다
    expect(await storage().findByRole('status')).toHaveTextContent('쓰기 테스트에 성공했습니다.')
    expect(storage().getByText('현재 위치: /data/neoine-sales/files')).toBeInTheDocument()
    expect(save).not.toHaveBeenCalled()
  })

  // 테스트 코드: IN-086
  it('쓸 수 없는 경로의 쓰기 테스트는 저장하지 않고 서버 문구를 보인다', async () => {
    // given: 쓸 수 없는 경로를 넣었다
    const { user } = await openIntegrations()
    const save = vi.spyOn(gateway.settings, 'saveStorage')
    const input = await storage().findByLabelText('저장 경로')
    await user.clear(input)
    await user.type(input, '/readonly/files')

    // when: 쓰기 테스트를 누른다
    await user.click(storage().getByRole('button', { name: '쓰기 테스트' }))

    // then: 서버 문구가 오류 알림으로 보이고 저장 요청은 없었다
    expect(await storage().findByRole('alert')).toHaveTextContent('해당 위치에 쓸 수 없습니다.')
    expect(save).not.toHaveBeenCalled()
  })
})

describe('외부연동 AD 설정: 브라우저 자동 채움', () => {
  // 테스트 코드: IN-078
  it('현재 관리자 비밀번호 칸은 current-password, 바인드 비밀번호 칸은 new-password, 나머지 AD 칸은 off다', async () => {
    // when: AD 폼을 본다 (전제: AD 모드의 외부연동 화면)
    await openIntegrations()

    // then: 자동 완성 속성이 각각 current-password·new-password·off다
    expect(adminPassword()).toHaveAttribute('autocomplete', 'current-password')
    expect(screen.getByLabelText(/^바인드 비밀번호/)).toHaveAttribute('type', 'password')
    expect(screen.getByLabelText(/^바인드 비밀번호/)).toHaveAttribute('autocomplete', 'new-password')
    for (const label of [/^호스트/, /^포트/, /^바인드 계정/, /사용자 검색 필터/, /연결 제한 시간/]) {
      expect(screen.getByLabelText(label)).toHaveAttribute('autocomplete', 'off')
    }
  })
})

describe('외부연동 AD 설정이 아직 없을 때', () => {
  async function openEmpty() {
    vi.spyOn(gateway.settings, 'getDirectory').mockResolvedValue(null)
    const view = await renderAt('/admin/integrations', { role: 'admin' })
    await screen.findByRole('heading', { name: 'AD(LDAP) 서버 설정' })
    await screen.findByLabelText(/^호스트/)
    return view
  }

  // 테스트 코드: IN-076
  it('설정이 없으면 안내 문구와 등록 폼을 보이고 최초 설정 링크는 없다', async () => {
    // when: 외부연동 화면을 연다 (전제: AD 모드이고 AD 설정이 없다(GET 404 -> null))
    await openEmpty()

    // then: 등록 안내와 빈 비밀번호 칸의 폼이 보이고 최초 설정 링크는 없다
    expect(directory().getByText('AD 서버가 아직 설정되지 않았습니다. 아래에서 등록하세요.')).toBeInTheDocument()
    expect(directory().queryByRole('link', { name: /최초 설정/ })).not.toBeInTheDocument()
    expect(directory().getByRole('button', { name: '저장' })).toBeInTheDocument()
    expect(directory().getByRole('button', { name: '연결 테스트' })).toBeInTheDocument()
    expect(screen.getByLabelText(/^바인드 비밀번호/)).toHaveValue('')
  })

  // 테스트 코드: IN-076
  it('바인드 비밀번호 없이는 요청을 보내지 않고 입력을 요구한다', async () => {
    // given: 등록 폼에 호스트와 바인드 계정만 넣었다
    const save = vi.spyOn(gateway.settings, 'saveDirectory')
    const { user } = await openEmpty()
    setField(/^호스트/, 'dc1.corp.test')
    setField(/^바인드 계정/, 'CORP\\svc-sales')

    // when: 저장을 누른다
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: 바인드 비밀번호를 입력하라는 안내가 보이고 저장 요청은 가지 않았다
    expect(await directory().findByRole('alert')).toHaveTextContent('바인드 비밀번호를 입력하세요')
    expect(save).not.toHaveBeenCalled()
  })

  // 테스트 코드: IN-076
  it('바인드 비밀번호와 현재 admin 비밀번호를 넣으면 null revision으로 만들어 설정 버전 1을 보인다', async () => {
    // given: 등록 폼에 7칸과 현재 admin 비밀번호를 넣었다(서버는 revision 1로 만든다)
    const save = vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue({ ...DIRECTORY_SAVED, revision: 1 })
    const { user } = await openEmpty()
    setField(/^호스트/, 'dc1.corp.test')
    setField(/^바인드 계정/, 'CORP\\svc-sales')
    await user.type(screen.getByLabelText(/^바인드 비밀번호/), 'Typed-pw-1!')
    await user.type(adminPassword(), 'pw-root')
    vi.spyOn(gateway.settings, 'getDirectory').mockResolvedValue({ ...DIRECTORY_SAVED, revision: 1 }) // 저장 뒤 다시 읽은 결과

    // when: 저장을 누른다
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: null revision과 password로 요청했고 저장했습니다와 설정 버전 1이 보인다
    await directory().findByText('저장했습니다')
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({ host: 'dc1.corp.test', bindAccount: 'CORP\\svc-sales', bindPassword: 'Typed-pw-1!' }),
      { password: 'pw-root', expectedRevision: null },
    )
    expect(directory().getByText('설정 버전 1')).toBeInTheDocument()
  })
})
