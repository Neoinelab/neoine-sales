import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { detailPath } from '../../../test/detailTestUtils'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'

/** Fake 서버 시계 2026-11-13T14:30+09:00(오늘 2026-11-13). 시드 Deal 1은 한참 전에 등록되었다. */
const NOW = '2026-11-13T14:30:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

describe('Actions 탭의 수행일 표시', () => {
  // 수행일 칸은 YYYY-MM-DD이고 시:분이 없으며 수정 팝업 안내도 같은 날짜다.
  // 테스트 코드: AC-116
  it('shows the acted day as YYYY-MM-DD without a time in the list and in the edit popup note', async () => {
    // given: 수행일이 2026-11-10인 김영업의 Action이 있다(가장 최근 행의 수행일을 그 날짜로 읽는다)
    const original = gateway.actions.list.bind(gateway.actions)
    vi.spyOn(gateway.actions, 'list').mockImplementation(async (code, query) =>
      (await original(code, query)).map((a, i) => (i === 0 ? { ...a, progress: '날짜 확인', actedOn: '2026-11-10' } : a)),
    )

    // when: Actions 탭을 열고 그 행의 "수정"을 누른다
    const view = await renderAt(await detailPath(1, '?tab=actions'), { role: 'sales' })
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    const row = within(table).getByText('날짜 확인').closest('tr') as HTMLElement
    await view.user.click(within(row).getByRole('button', { name: '수정' }))
    const dialog = await screen.findByRole('dialog', { name: 'Action 수정' })

    // then: 첫 열 머리글은 "수행일", 칸 값은 "2026-11-10", 팝업 안내는 "수행일: 2026-11-10 · 담당자: 김영업"이고 시:분은 어디에도 없다
    expect(within(table).getAllByRole('columnheader')[0]).toHaveTextContent('수행일')
    expect(within(table).queryByRole('columnheader', { name: '수행일시' })).not.toBeInTheDocument()
    expect(within(row).getAllByRole('cell')[0]).toHaveTextContent(/^2026-11-10$/)
    expect(within(dialog).getByText('수행일: 2026-11-10 · 담당자: 김영업')).toBeVisible()
    expect(within(dialog).queryByText(/\d{1,2}:\d{2}/)).not.toBeInTheDocument()
    expect(within(table).queryByText(/\d{1,2}:\d{2}/)).not.toBeInTheDocument()
  })
})
