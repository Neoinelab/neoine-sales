import { defaultMock } from '../../../test/fake/default'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import type { DealAction, DealDetail, NextActionStatus, Risk } from '../../../shared/model/types'
import { ActionTable } from './ActionTable'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { USER_ID } from '../../../test/fake/seed/ids'

const NOW = '2026-11-18T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => resetMock({ now: null }))

interface RowSpec {
  label: string
  status: NextActionStatus | null
  due: string | null
}

/** 시드 Deal 3의 Action 하나를 본떠 라벨(진행사항)·상태·Due만 다른 행들을 만든다. */
async function renderTable(risk: Risk, specs: RowSpec[], clockNow = NOW) {
  const code = await dealCodeOf(3)
  await defaultMock.signInAs(USER_ID.root)
  const deal: DealDetail = { ...(await gateway.deals.get(code)), risk }
  const [template] = await gateway.actions.list(code, {})
  if (!template) throw new Error('템플릿 Action이 없습니다.')
  const actions: DealAction[] = specs.map((s, i) => ({
    ...template,
    id: 9000 + i,
    progress: s.label,
    nextAction: s.status === null ? null : `${s.label} 할 일`,
    dueDate: s.due,
    nextActionStatus: s.status,
    nextActionClosedOn: s.status === 'done' || s.status === 'notDone' ? '2026-11-17' : null,
  }))
  resetMock({ now: clockNow })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ActionTable actions={actions} deal={deal} canEdit={false} me={null} onOpen={() => {}} sort={{ sort: 'actedAt', order: 'desc' }} onSort={() => {}} />
    </QueryClientProvider>,
  )
}

const rowOf = (label: string): HTMLElement => {
  const row = screen.getByText(label).closest('tr')
  if (!row) throw new Error(`${label} 행이 없습니다.`)
  return row
}

const OVERDUE_OPEN: RowSpec[] = [
  { label: 'A', status: 'open', due: '2026-11-10' },
  { label: 'B', status: 'open', due: '2026-11-12' },
  { label: 'C', status: 'done', due: '2026-11-05' },
  { label: 'D', status: 'notDone', due: '2026-11-06' },
  { label: 'E', status: 'open', due: '2026-11-18' },
  { label: 'F', status: null, due: null },
]

describe('Action 행 기한초과 배지는 서버 risk와 앱 시계를 따른다', () => {
  // 서버 risk가 null이면 Open이고 Due가 지나 보여도 배지가 없다.
  // 테스트 코드: RK-058
  it('shows no row badge when the server risk is null even though an open due date is past the clock', async () => {
    // given: 앱 시계 2026-11-18, Open이고 Due가 2026-11-10인 행이 있고 서버 risk가 null이다
    // when: Actions 탭 표를 그린다
    await renderTable(null, OVERDUE_OPEN)
    // then: 어떤 행에도 '기한초과' 배지가 없다
    expect(screen.getByText('A')).toBeVisible()
    expect(screen.queryByText('기한초과')).not.toBeInTheDocument()
  })

  // 서버 risk가 stale뿐이면 배지가 없다.
  // 테스트 코드: RK-058
  it('shows no row badge when the server risk is only stale', async () => {
    // given: 서버 risk가 stale이다
    // when: Actions 탭 표를 그린다
    await renderTable('stale', OVERDUE_OPEN)
    // then: 어떤 행에도 '기한초과' 배지가 없다
    expect(screen.getByText('A')).toBeVisible()
    expect(screen.queryByText('기한초과')).not.toBeInTheDocument()
  })

  // 서버 risk가 overdue·overdue_stale이면 Open이고 Due가 지난 행에 배지가 보인다.
  // 테스트 코드: RK-058
  it.each(['overdue', 'overdue_stale'] as const)('shows the badge on an open past-due row when the server risk is %s', async (risk) => {
    // given: 서버 risk가 기한초과 계열이다
    // when: Actions 탭 표를 그린다
    await renderTable(risk, OVERDUE_OPEN)
    // then: Open이고 Due가 지난 A 행 Due 칸에 배지가 보인다
    await waitFor(() => expect(within(rowOf('A')).getByText('기한초과')).toBeVisible())
  })

  // Open이고 Due가 지난 모든 행에 배지가 붙고, 종료·Due 오늘·Next Action 없는 행에는 붙지 않는다.
  // 테스트 코드: RK-076
  it('badges every open past-due row and no closed, due-today or action-less row', async () => {
    // given: 앱 시계 2026-11-18, 서버 risk overdue, A·B(Open 지남)·C(done)·D(notDone)·E(Open 오늘)·F(Next Action 없음)
    // when: Actions 탭을 연다
    await renderTable('overdue', OVERDUE_OPEN)
    // then: A·B 행에만 배지가 있다
    await waitFor(() => expect(within(rowOf('A')).getByText('기한초과')).toBeVisible())
    expect(within(rowOf('B')).getByText('기한초과')).toBeVisible()
    for (const label of ['C', 'D', 'E', 'F']) expect(within(rowOf(label)).queryByText('기한초과')).not.toBeInTheDocument()
    expect(screen.getAllByText('기한초과')).toHaveLength(2)
  })

  // 배지는 앱 시계로 판정한다: 앱 시계가 Due 이전이면 브라우저 시계가 지났어도 배지가 없다.
  // 테스트 코드: RK-076
  it('judges the badge by the app clock, not the browser clock', async () => {
    // given: 서버 risk overdue, 앱 시계 2020-01-01(브라우저 시계는 그 뒤), Open이고 Due가 2025-01-01인 행과 Due가 2019-12-31인 행
    // when: Actions 탭을 연다
    await renderTable(
      'overdue',
      [
        { label: 'X', status: 'open', due: '2025-01-01' },
        { label: 'Y', status: 'open', due: '2019-12-31' },
      ],
      '2020-01-01T09:00:00+09:00',
    )
    // then: 앱 시계 기준으로 지난 Y 행에만 배지가 있다
    await waitFor(() => expect(within(rowOf('Y')).getByText('기한초과')).toBeVisible())
    expect(within(rowOf('X')).queryByText('기한초과')).not.toBeInTheDocument()
  })
})
