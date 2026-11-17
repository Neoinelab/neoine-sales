import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { dealCodeOf, detailPath } from '../../../test/detailTestUtils'

async function openDialog(no: number, title: string, role: 'sales' | 'admin' = 'sales') {
  const view = await renderAt(await detailPath(no), { role })
  await screen.findByRole('heading', { level: 1, name: title })
  await view.user.click(screen.getByRole('button', { name: 'Deal 삭제' }))
  const dialog = await screen.findByRole('dialog', { name: 'Deal 삭제' })
  return { ...view, dialog }
}

describe('Deal 삭제 팝업 (T-DELETE-01~06)', () => {
  // 삭제 확인은 함께 지워지는 건수를 알리고(파트너 미팅은 언급 없음) Deal code 입력을 요구한다.
  // 테스트 코드: DD-109
  it('states what is deleted together, with the counts and without partner meetings, and asks for the deal code', async () => {
    // given: 이력·Action 4건·첨부 3개가 있는 Deal
    const code = await dealCodeOf(1)

    // when: 삭제 대화상자를 연다
    const { dialog } = await openDialog(1, '한빛은행 ITDR 도입')

    // then: Deal History·Action·첨부·계약·Comment 건수와 '복구할 수 없습니다', Deal code 안내가 보이고 '파트너 미팅'은 없다
    await waitFor(() => expect(dialog).toHaveTextContent(/Deal History \d+건, Action 4건, 첨부 파일 3개, 라이선스 계약 \d+건, Comment 0건과 파일 저장 디렉터리/))
    expect(dialog).not.toHaveTextContent('파트너 미팅')
    expect(dialog).toHaveTextContent('복구할 수 없습니다')
    expect(dialog).toHaveTextContent(`Deal code ${code}`)
  })

  // 건수를 읽는 동안에는 건수 없는 같은 안내에 Comment도 들어 있다.
  // 테스트 코드: DD-109
  it('names Comment in the text shown while the counts are loading', async () => {
    // given: 삭제 영향 응답을 늦춘다
    let release: () => void = () => undefined
    const slow = new Promise<void>((resolve) => {
      release = resolve
    })
    const original = gateway.deals.impact
    const spy = vi.spyOn(gateway.deals, 'impact').mockImplementation(async (code) => {
      await slow
      return original(code)
    })

    // when: 삭제 대화상자를 연다
    const { dialog } = await openDialog(1, '한빛은행 ITDR 도입')

    // then: 건수 없는 안내에 Deal History·Action·첨부 파일·라이선스 계약·Comment가 있다
    expect(dialog).toHaveTextContent('삭제하면 Deal History, Action, 첨부 파일, 라이선스 계약, Comment가 함께 삭제되며 복구할 수 없습니다.')
    release()
    spy.mockRestore()
  })

  // 정확한 code를 입력하기 전에는 삭제가 꺼져 있고 불일치 문구를 보인다.
  // 테스트 코드: DD-110
  it('keeps 삭제 disabled until the exact code is typed and explains a mismatch', async () => {
    // given: 삭제 대화상자
    const code = await dealCodeOf(2)
    const { user, dialog } = await openDialog(2, '대한제조 MFA 확대')

    const confirm = within(dialog).getByRole('button', { name: '삭제' })
    expect(confirm).toBeDisabled()
    expect(within(dialog).queryByRole('alert')).not.toBeInTheDocument()
    const input = within(dialog).getByLabelText('Deal code 확인')

    // when: code를 한 글자 모자라게 입력한다
    await user.type(input, code.slice(0, -1))
    // then: 삭제는 비활성이고 불일치 문구가 보인다
    expect(confirm).toBeDisabled()
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Deal code가 일치하지 않습니다.')

    // when: 나머지 한 글자를 입력한다
    await user.type(input, code.slice(-1))
    // then: 삭제가 활성이고 문구가 사라진다
    expect(confirm).toBeEnabled()
    expect(within(dialog).queryByRole('alert')).not.toBeInTheDocument()
  })

  // 소문자 code는 인정하지 않는다.
  // 테스트 코드: DD-110
  it('does not accept the code in lower case', async () => {
    // given: 삭제 대화상자
    const code = await dealCodeOf(2)
    const { user, dialog } = await openDialog(2, '대한제조 MFA 확대')

    // when: 소문자로 code를 입력한다
    await user.type(within(dialog).getByLabelText('Deal code 확인'), code.toLowerCase())

    // then: 삭제 버튼이 비활성이다
    expect(within(dialog).getByRole('button', { name: '삭제' })).toBeDisabled()
  })

  // 삭제하면 Deal과 이력·Action이 사라지고 목록 주소로 간다.
  // 테스트 코드: DD-111
  it('deletes the deal with its history, actions and attachments and goes back to the list', async () => {
    // given: Action·첨부가 있는 Deal
    const code = await dealCodeOf(1)
    const { user, dialog, location } = await openDialog(1, '한빛은행 ITDR 도입')

    // when: code를 입력하고 삭제한다
    await user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    // then: 주소가 /deals이고 Deal과 Action 조회가 404다
    await waitFor(() => expect(location()).toMatch(/^\/deals(\?|$)/))
    await expect(gateway.deals.get(code)).rejects.toMatchObject({ status: 404 })
    await expect(gateway.actions.list(code, {})).rejects.toMatchObject({ status: 404 })
  })

  // Deal을 지워도 파트너 미팅 기록은 남는다.
  // 테스트 코드: DD-113
  it('keeps the partner meetings when the deal is deleted', async () => {
    // given: 파트너 미팅 기록이 있는 상태에서 삭제 대화상자
    const code = await dealCodeOf(1)
    const { user, dialog } = await openDialog(1, '한빛은행 ITDR 도입')
    const before = await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc' }, 0, 50)

    // when: code를 입력하고 삭제한다
    await user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    // then: 미팅 건수와 id 목록이 삭제 전과 같다
    await waitFor(() => expect(gateway.deals.get(code)).rejects.toMatchObject({ status: 404 }))
    const after = await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc' }, 0, 50)
    expect(after.total).toBe(before.total)
    expect(after.items.map((m) => m.id)).toEqual(before.items.map((m) => m.id))
  })

  // 건수를 읽는 동안에도 파트너 미팅은 언급하지 않는다.
  // 테스트 코드: DD-109
  it('shows the same text without partner meetings while the counts are loading', async () => {
    // when: 대화상자를 본다 (전제: 건수를 아직 읽지 못한 삭제 대화상자)
    const { dialog } = await openDialog(2, '대한제조 MFA 확대')

    // then: '파트너 미팅' 글자가 없다
    expect(dialog).not.toHaveTextContent('파트너 미팅')
  })

  // 삭제하면 상세를 바로 떠나 지워진 Deal이 남아 보이지 않는다.
  // 테스트 코드: DD-111
  it('leaves the detail screen right after deleting so no stale deal is shown', async () => {
    // given: 삭제 대화상자
    const code = await dealCodeOf(2)
    const { user, dialog } = await openDialog(2, '대한제조 MFA 확대')

    // when: code를 입력하고 삭제한다
    await user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    // then: Deal 제목도 '찾을 수 없습니다' 오류도 보이지 않는다
    await waitFor(() => expect(screen.queryByRole('heading', { level: 1, name: '대한제조 MFA 확대' })).not.toBeInTheDocument())
    expect(screen.queryByText('Deal을 찾을 수 없습니다.')).not.toBeInTheDocument()
  })

  // 취소·Esc는 삭제하지 않고 닫는다.
  // 테스트 코드: DD-112
  it('closes with cancel or Escape without deleting', async () => {
    // given: code를 입력한 삭제 대화상자
    const code = await dealCodeOf(2)
    const { user, dialog } = await openDialog(2, '대한제조 MFA 확대')

    await user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    // when: '취소'를 누른다
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    // then: 대화상자가 닫힌다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    // when: 다시 열어 Esc를 누른다
    await user.click(screen.getByRole('button', { name: 'Deal 삭제' }))
    await user.keyboard('{Escape}')
    // then: 대화상자가 닫히고 Deal이 그대로 있다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await expect(gateway.deals.get(code)).resolves.toMatchObject({ code })
  })

  // admin은 남의 Deal도 삭제하고 목록으로 간다.
  // 테스트 코드: DD-072
  it('lets admin delete a deal owned by someone else', async () => {
    // given: 다른 영업의 Deal과 admin
    const code = await dealCodeOf(3)
    const { user, dialog, location } = await openDialog(3, '미래전자 EDR 교체', 'admin')

    // when: code를 입력하고 삭제한다
    await user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    // then: 주소가 /deals로 바뀐다
    await waitFor(() => expect(location()).toMatch(/^\/deals(\?|$)/))
  })

  // 남의 Deal을 게이트웨이로 직접 삭제하면 403이다.
  // 테스트 코드: DD-071
  it('rejects a sales user deleting someone else s deal directly through the gateway (403)', async () => {
    // given: 다른 영업의 Deal과 sales 사용자
    const code = await dealCodeOf(3)

    // when: 게이트웨이로 삭제를 요청한다
    await renderAt(await detailPath(3))

    // then: 403으로 거절된다
    await expect(gateway.deals.remove(code, code)).rejects.toMatchObject({ status: 403 })
  })
})
