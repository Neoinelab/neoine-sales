import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { defaultMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import { detailPath } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

const bodyRows = (table: HTMLElement) => within(table).getAllByRole('row').slice(1)

async function openActions() {
  const view = await renderAt(await detailPath(1, '?tab=actions'), { role: 'sales' })
  await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  return { ...view, table }
}

describe('Actions 탭: 빈 목록·삭제 실패', () => {
  // Action이 하나도 없는 Deal은 "등록된 Action이 없습니다."를 보인다.
  // 테스트 코드: AC-071
  it('says there are no registered actions when the deal has none', async () => {
    // given: Deal의 Action을 모두 지운 뒤(admin) sales가 Actions 탭을 연다
    const view = await renderAt(await detailPath(1, '?tab=actions'), { role: 'sales' })
    await screen.findByRole('table', { name: 'Action 목록' })
    const code = (await gateway.deals.list({ keyword: '한빛은행 ITDR', limit: 1 })).items[0]?.code ?? ''
    await defaultMock.signInAs(USER_ID.root)
    for (const action of await gateway.actions.list(code, {})) await gateway.actions.remove(action.id)
    await defaultMock.signInAs(USER_ID.kim)
    // when: 목록을 다시 읽는다
    await view.client.invalidateQueries()
    // then: "등록된 Action이 없습니다."가 보이고 표는 없다
    expect(await screen.findByText('등록된 Action이 없습니다.')).toBeVisible()
    expect(screen.queryByRole('table', { name: 'Action 목록' })).not.toBeInTheDocument()
  })

  // 삭제가 서버에서 거절되면 대화상자가 닫히고 탭 위 오류 배너에 서버 문구가 보이며 행이 남는다.
  // 테스트 코드: AC-088
  it('closes the delete dialog and shows the server message in the tab banner when the delete is refused', async () => {
    // given: 삭제가 서버 오류로 거절되도록 한 sales와 행 수
    vi.spyOn(gateway.actions, 'remove').mockRejectedValue(
      new ApiError(403, {
        type: 'https://sales.neoine.test/problems/forbidden',
        title: 'x',
        status: 403,
        detail: '본인 Action 또는 admin만 삭제할 수 있습니다.',
      }),
    )
    const { user, table } = await openActions()
    const before = bodyRows(table).length
    // when: 첫 행의 삭제를 눌러 확인한다
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '삭제' }))
    await user.click(within(screen.getByRole('dialog', { name: 'Action 삭제' })).getByRole('button', { name: '삭제' }))
    // then: 대화상자가 닫히고 탭 오류 배너에 서버 문구가 보인다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 삭제' })).not.toBeInTheDocument())
    expect(await screen.findByRole('alert')).toHaveTextContent('본인 Action 또는 admin만 삭제할 수 있습니다.')
    // then: 행이 남고 삭제 알림은 없다
    expect(bodyRows(table)).toHaveLength(before)
    expect(screen.queryByText('Action이 삭제되었습니다.')).not.toBeInTheDocument()
  })
})
