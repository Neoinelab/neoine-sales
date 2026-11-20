import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { detailPath } from '../../../test/detailTestUtils'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'

const NOW = '2026-11-18T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => resetMock({ now: null }))

describe('상세 요약 바 Next Action 줄의 기준 행 (RK-R17, RK-R1)', () => {
  // 기한초과 배지가 보이면 Next Action 줄은 지난 Open Next Action 중 Due가 가장 이른 행이다.
  // 테스트 코드: RK-087
  it('shows the earliest past open next action next to the overdue badge', async () => {
    // given: Deal 1에 Due가 지난 Open Next Action 둘(Due 이른 쪽이 먼저 수행)과 더 최근의 미래 Due 행이 있다
    const path = await detailPath(1)
    const code = path.slice('/deals/'.length)
    const { client } = await renderAt(path, { role: 'sales' })
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
    const base = { type: { name: '미팅' }, comment: '' }
    await gateway.actions.create(code, { ...base, progress: '약속1', nextAction: '이른 약속', dueDate: '2000-01-01', actedOn: '2026-11-01' })
    await gateway.actions.create(code, { ...base, progress: '약속2', nextAction: '늦은 약속', dueDate: '2000-02-01', actedOn: '2026-11-17' })

    // when: 상세를 다시 읽는다
    await client.invalidateQueries()

    // then: 요약 바는 Due가 가장 이른 지난 Open 행과 기한초과 배지를 보인다
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    await waitFor(() => expect(within(bar).getByText('이른 약속')).toBeVisible())
    expect(within(bar).getByText('Due 2000-01-01')).toBeVisible()
    expect(within(bar).getByText('Open')).toBeVisible()
    expect(within(bar).queryByText('늦은 약속')).not.toBeInTheDocument()
    expect(within(bar).getByText('기한초과')).toBeVisible()
  })
})
