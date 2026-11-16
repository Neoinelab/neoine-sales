import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { defaultMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import { detailPath } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

describe('Actions 탭: 빈 목록', () => {
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
})
