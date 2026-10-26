import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { USER_ID } from '../../../test/fake/seed/ids'
import { dealInput } from '../../../test/fake/testing'
import { renderAt } from '../../../test/mockApp'
import { rowOf } from './testHelpers'

afterEach(() => {
  vi.restoreAllMocks()
})

const HEADERS = [
  'Deal',
  '담당자',
  '고객사',
  '파트너사',
  'Vendor',
  'Status',
  'Forecast',
  '금액(단위:천원)',
  'Expected Close',
  'Next Action',
  'Due',
  'Next Action 상태',
  '최종 업데이트',
]

/** 머리글 이름으로 같은 위치의 칸(td)을 찾는다. 열이 없으면 오류로 실패한다. */
function cellOf(row: HTMLElement, header: string): HTMLElement {
  const index = screen.getAllByRole('columnheader').findIndex((h) => h.textContent?.trim() === header)
  if (index < 0) throw new Error(`${header} 열이 없습니다.`)
  const cell = within(row).getAllByRole('cell')[index]
  if (!cell) throw new Error(`${header} 칸이 없습니다.`)
  return cell
}

const isOverdueMarked = (cell: HTMLElement) => cell.matches('.overdue') || cell.querySelector('.overdue') !== null

async function nextActionOf(name: string) {
  const page = await gateway.deals.list({ keyword: name })
  const found = page.items.find((d) => d.name === name)
  if (!found) throw new Error(`Deal ${name} 없음`)
  return found
}

describe('목록 열 정리: 헤더 (AC1·AC2)', () => {
  it('shows the 13 headers in order without BANT', async () => {
    await renderAt('/deals')
    await rowOf(/한빛은행 ITDR 도입/)

    expect(screen.getAllByRole('columnheader').map((h) => h.textContent?.trim())).toEqual(HEADERS)
    expect(screen.queryByRole('columnheader', { name: 'BANT' })).not.toBeInTheDocument()
  })

  it('new Next Action columns are not sortable', async () => {
    await renderAt('/deals')
    await rowOf(/한빛은행 ITDR 도입/)

    for (const name of ['Next Action', 'Due', 'Next Action 상태']) {
      const header = screen.getByRole('columnheader', { name })
      expect(within(header).queryByRole('button')).not.toBeInTheDocument()
      expect(header).not.toHaveAttribute('aria-sort')
    }
  })

  it('quick view row spans all 13 columns', async () => {
    const { user } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))

    const view = screen.getByRole('region', { name: /빠른 보기/ })
    expect(view.closest('td')).toHaveAttribute('colspan', '13')
  })
})

describe('목록 열 정리: BANT 없음 (AC1)', () => {
  it('shows no BANT cell or label name in the row', async () => {
    await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)

    expect(within(row).getAllByRole('cell')).toHaveLength(13)
    expect(within(row).queryByLabelText(/^(Budget|Authority|Need|Timeline): /)).not.toBeInTheDocument()
    expect(row).not.toHaveTextContent('단독 예산 확보')
    expect(row).not.toHaveTextContent('CISO 보고 완료')
  })

  it('does not read the BANT labels for the list', async () => {
    const spy = vi.spyOn(gateway.labels, 'list')
    await renderAt('/deals?q=한빛은행 ITDR')
    await rowOf(/한빛은행 ITDR 도입/)

    expect(spy).not.toHaveBeenCalled()
  })

  it('shows no label failure notice even when reading labels would fail', async () => {
    vi.spyOn(gateway.labels, 'list').mockRejectedValue(new Error('Label 조회 실패'))
    await renderAt('/deals?q=한빛은행 ITDR')
    await rowOf(/한빛은행 ITDR 도입/)

    expect(screen.queryByText('불러오지 못함')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('목록 열 정리: Next Action 세 칸 (AC3)', () => {
  it('puts the link, the plain date and the status label in separate cells', async () => {
    const code = await dealCodeOf(1)
    const basis = (await nextActionOf('한빛은행 ITDR 도입')).nextAction
    if (!basis) throw new Error('시드 Deal 1의 Next Action이 필요합니다.')
    await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)

    const action = cellOf(row, 'Next Action')
    const due = cellOf(row, 'Due')
    const status = cellOf(row, 'Next Action 상태')

    expect(within(action).getByRole('link', { name: basis.text })).toHaveAttribute('href', `/deals/${code}?tab=actions`)
    expect(action).toHaveTextContent(/^계약서 초안 검토$/)
    expect(due).toHaveTextContent(new RegExp(`^${basis.dueDate}$`))
    expect(within(due).queryByRole('link')).not.toBeInTheDocument()
    expect(status).toHaveTextContent(/^Open$/)
    expect(within(status).queryByRole('link')).not.toBeInTheDocument()
  })

  it('marks an overdue Next Action date and not a normal one', async () => {
    const overdueDeal = await nextActionOf('미래전자 EDR 교체')
    expect(overdueDeal.risk === 'overdue' || overdueDeal.risk === 'overdue_stale').toBe(true)
    if (!overdueDeal.nextAction) throw new Error('기한초과 시드 Deal에 Next Action이 필요합니다.')
    await renderAt('/deals')
    const overdueRow = await rowOf(/미래전자 EDR 교체/)
    const normalRow = await rowOf(/한빛은행 ITDR 도입/)

    const overdueDue = cellOf(overdueRow, 'Due')
    expect(overdueDue).toHaveTextContent(overdueDeal.nextAction.dueDate)
    expect(isOverdueMarked(overdueDue)).toBe(true)
    expect(isOverdueMarked(cellOf(normalRow, 'Due'))).toBe(false)
    expect(isOverdueMarked(cellOf(overdueRow, 'Next Action'))).toBe(false)
  })

  it.each([
    ['done', '종료(수행)'],
    ['notDone', '종료(미수행)'],
  ] as const)('shows the %s status label in the status cell only', async (status, label) => {
    const code = await dealCodeOf(1)
    const { client } = await renderAt('/deals?q=한빛은행 ITDR')
    await rowOf(/한빛은행 ITDR 도입/)
    const basis = (await gateway.actions.list(code, {})).find((a) => a.nextAction === '계약서 초안 검토')
    if (!basis) throw new Error('기준 Action이 없습니다.')
    await gateway.actions.changeNextActionStatus(basis.id, { status, memo: '' })
    await client.invalidateQueries()

    await waitFor(() => expect(cellOf(screen.getByRole('row', { name: /한빛은행 ITDR 도입/ }), 'Next Action 상태')).toHaveTextContent(new RegExp(`^${label.replace(/[()]/g, '\\$&')}$`)))
    const row = screen.getByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(cellOf(row, 'Due')).not.toHaveTextContent(label)
    expect(cellOf(row, 'Next Action')).not.toHaveTextContent(label)
  })
})

describe('목록 열 정리: Next Action 없음 (AC4)', () => {
  it('shows a dash in all three cells', async () => {
    const { client } = await renderAt('/deals?q=액션 없는 Deal')
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '액션 없는 Deal' }))
    await client.invalidateQueries()
    const row = await rowOf(/액션 없는 Deal/)

    for (const header of ['Next Action', 'Due', 'Next Action 상태']) {
      expect(cellOf(row, header)).toHaveTextContent(/^—$/)
    }
    expect(isOverdueMarked(cellOf(row, 'Due'))).toBe(false)
    expect(within(row).queryAllByRole('link').filter((a) => a.getAttribute('href')?.includes('tab=actions'))).toEqual([])
  })
})
