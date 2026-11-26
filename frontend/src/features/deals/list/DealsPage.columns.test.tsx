import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { USER_ID } from '../../../test/fake/seed/ids'
import { dealInput } from '../../../test/fake/testing'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, rowOf } from './testHelpers'

afterEach(() => {
  vi.restoreAllMocks()
})

const HEADERS = [
  'Deal',
  '담당자',
  'Vendor',
  'Forecast',
  '금액(단위:원)',
  'Expected Close',
  '최종 업데이트',
  'Next Action',
  'Due Date',
  'Next Action 상태',
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
  // 테스트 코드: DL-058
  it('shows the ten remaining headers in order with their percentage widths', async () => {
    // given: 시드 목록
    await renderAt(ALL_DEALS)

    // when: 목록을 연다
    await rowOf(/한빛은행 ITDR 도입/)

    expect(screen.getAllByRole('columnheader').map((h) => h.textContent?.trim())).toEqual(HEADERS)
    expect(Array.from(screen.getByRole('table').querySelectorAll('col'), (col) => col.style.width))
      .toEqual(['26%', '6%', '6%', '6%', '6%', '6%', '6%', '26%', '6%', '6%'])
    expect(screen.queryByRole('columnheader', { name: 'BANT' })).not.toBeInTheDocument()
  })

  // 행의 칸도 머리글과 같은 순서이고 최종 업데이트 칸 바로 오른쪽이 Next Action 칸이다
  // 테스트 코드: DL-058
  it('places the last update cell right before the Next Action cell in each row', async () => {
    // given: Next Action이 있는 Deal 행
    await renderAt('/deals?year=all&q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)

    // when: 행의 칸 위치를 머리글 위치와 대조한다
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent?.trim())
    const cells = within(row).getAllByRole('cell')

    // then: 최종 업데이트 칸은 Expected Close 다음, 그 오른쪽이 Next Action 링크 칸이다
    const updated = headers.indexOf('최종 업데이트')
    expect(updated).toBe(headers.indexOf('Expected Close') + 1)
    expect(cells[updated]?.textContent?.trim()).toMatch(/^(오늘|어제|\d+일 전)$/)
    expect(within(cells[updated + 1] as HTMLElement).getByRole('link', { name: '계약서 초안 검토' })).toBeVisible()
  })

  // Next Action 세 열은 정렬 버튼이 아니다
  // 테스트 코드: DL-089
  it('new Next Action columns are not sortable', async () => {
    // given: 목록 머리글
    await renderAt(ALL_DEALS)

    // when: 머리글을 확인한다
    await rowOf(/한빛은행 ITDR 도입/)

    // then: Next Action·Due·Next Action 상태 머리글에 정렬 버튼이 없다
    for (const name of ['Next Action', 'Due Date', 'Next Action 상태']) {
      const header = screen.getByRole('columnheader', { name })
      expect(within(header).queryByRole('button')).not.toBeInTheDocument()
      expect(header).not.toHaveAttribute('aria-sort')
    }
  })

  // 테스트 코드: DL-091
  it('quick view row spans all displayed columns', async () => {
    // given: 빠른 보기가 닫힌 행
    const { user } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)

    // when: 빠른 보기를 연다
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    const view = screen.getByRole('region', { name: /빠른 보기/ })

    expect(view.closest('td')).toHaveAttribute('colspan', String(HEADERS.length))
  })
})

describe('목록 열 정리: BANT 없음 (AC1)', () => {
  // 행에는 BANT 칸도 Label 이름도 없다
  // 테스트 코드: DL-058
  it('shows no BANT cell or label name in the row', async () => {
    // given: 시드 목록
    await renderAt('/deals?q=한빛은행 ITDR')

    // when: 행을 확인한다
    const row = await rowOf(/한빛은행 ITDR 도입/)

    // then: BANT 칸과 Label 이름이 보이지 않는다
    expect(within(row).getAllByRole('cell')).toHaveLength(HEADERS.length)
    expect(within(row).queryByLabelText(/^(Budget|Authority|Need|Timeline): /)).not.toBeInTheDocument()
    expect(row).not.toHaveTextContent('단독 예산 확보')
    expect(row).not.toHaveTextContent('CISO 보고 완료')
  })

  // 목록은 BANT Label 목록을 읽지 않는다
  // 테스트 코드: DL-092
  it('does not read the BANT labels for the list', async () => {
    // given: Label 조회를 관찰한다
    const spy = vi.spyOn(gateway.labels, 'list')
    await renderAt('/deals?q=한빛은행 ITDR')

    // when: 빠른 보기를 열지 않고 목록을 연다
    await rowOf(/한빛은행 ITDR 도입/)

    // then: Label 조회 요청이 없다
    expect(spy).not.toHaveBeenCalled()
  })

  // Label 조회가 실패해도 목록에는 실패 안내가 없다
  // 테스트 코드: DL-092
  it('shows no label failure notice even when reading labels would fail', async () => {
    // given: Label 조회가 실패하도록 한 Fake
    vi.spyOn(gateway.labels, 'list').mockRejectedValue(new Error('Label 조회 실패'))
    await renderAt('/deals?q=한빛은행 ITDR')

    // when: 목록을 연다
    await rowOf(/한빛은행 ITDR 도입/)

    // then: 실패 안내가 보이지 않는다
    expect(screen.queryByText('불러오지 못함')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('목록 열 정리: Next Action 세 칸 (AC3)', () => {
  // Next Action 링크·Due·상태 라벨은 서로 다른 칸에 있다
  // 테스트 코드: DL-059
  it('puts the link, the plain date and the status label in separate cells', async () => {
    // given: Next Action이 있는 Deal
    const code = await dealCodeOf(1)
    const basis = (await nextActionOf('한빛은행 ITDR 도입')).nextAction
    if (!basis) throw new Error('시드 Deal 1의 Next Action이 필요합니다.')
    await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)

    const action = cellOf(row, 'Next Action')
    const due = cellOf(row, 'Due Date')

    // when: 목록을 연다
    const status = cellOf(row, 'Next Action 상태')

    // then: 링크·날짜·상태 라벨이 각자 칸에 있다
    expect(within(action).getByRole('link', { name: basis.text })).toHaveAttribute('href', `/deals/${code}?tab=actions`)
    expect(action).toHaveTextContent(/^계약서 초안 검토$/)
    expect(due).toHaveTextContent(new RegExp(`^${basis.dueDate}$`))
    expect(within(due).queryByRole('link')).not.toBeInTheDocument()
    expect(status).toHaveTextContent(/^Open$/)
    expect(within(status).queryByRole('link')).not.toBeInTheDocument()
  })

  // 기한초과 행은 Due 칸만 강조하고 Next Action 칸과 정상 행 Due 칸은 강조하지 않는다.
  // 테스트 코드: RK-055, RK-077
  // 기한초과 Due만 강조한다
  // 테스트 코드: DL-059
  it('marks an overdue Next Action date and not a normal one', async () => {
    // given: 기한초과 Deal(미래전자 EDR 교체)과 정상 Deal이 있다
    const overdueDeal = await nextActionOf('미래전자 EDR 교체')
    expect(overdueDeal.risk === 'overdue' || overdueDeal.risk === 'overdue_stale').toBe(true)
    if (!overdueDeal.nextAction) throw new Error('기한초과 시드 Deal에 Next Action이 필요합니다.')
    // when: Deals 목록을 연다
    await renderAt(ALL_DEALS)
    const overdueRow = await rowOf(/미래전자 EDR 교체/)
    const normalRow = await rowOf(/한빛은행 ITDR 도입/)

    // then: 기한초과 행의 Due 칸에만 기한초과 표시가 있다
    const overdueDue = cellOf(overdueRow, 'Due Date')
    expect(overdueDue).toHaveTextContent(overdueDeal.nextAction.dueDate)
    expect(isOverdueMarked(overdueDue)).toBe(true)
    expect(isOverdueMarked(cellOf(normalRow, 'Due Date'))).toBe(false)
    expect(isOverdueMarked(cellOf(overdueRow, 'Next Action'))).toBe(false)
  })

  // 기한초과 Deal은 더 최근의 종료 Next Action이 있어도 지난 Open Next Action을 보이고 Due 칸을 강조한다.
  // 테스트 코드: RK-077
  it('shows the past open next action and marks its Due cell even when a later one is closed', async () => {
    // given: Deal 1에 Due가 지난 Open Next Action과, 그 뒤에 Due 미래인 종료(수행) Next Action이 있다
    const code = await dealCodeOf(1)
    const { client } = await renderAt('/deals?q=한빛은행 ITDR')
    await rowOf(/한빛은행 ITDR 도입/)
    const past = await gateway.actions.create(code, { type: { name: '미팅' }, progress: '예전 약속', nextAction: '예전 할 일', dueDate: '2000-01-01', comment: '' })
    const later = await gateway.actions.create(code, { type: { name: '미팅' }, progress: '최근', nextAction: '다음 할 일', dueDate: '2999-12-31', comment: '' })
    await gateway.actions.changeNextActionStatus(later.id, { status: 'done', comment: '' })
    expect(past.id).not.toBe(later.id)

    // when: 목록을 다시 읽는다
    await client.invalidateQueries()

    // then: 행은 지난 Open 행의 Next Action·Due(강조)·Open을 보이고 기한초과 배지·행 클래스가 있다
    await waitFor(async () => expect(await rowOf(/한빛은행 ITDR 도입/)).toHaveClass('risk-overdue'))
    const row = await rowOf(/한빛은행 ITDR 도입/)
    expect(within(row).getByText('기한초과')).toBeVisible()
    expect(cellOf(row, 'Next Action')).toHaveTextContent(/^예전 할 일$/)
    expect(cellOf(row, 'Due Date')).toHaveTextContent('2000-01-01')
    expect(isOverdueMarked(cellOf(row, 'Due Date'))).toBe(true)
    expect(cellOf(row, 'Next Action 상태')).toHaveTextContent(/^Open$/)
  })

  // 종결(Won) Deal은 지난 Open Next Action을 보여도 Due 강조·경고 배지·행 클래스가 없다.
  // 테스트 코드: RK-077
  it('shows the past open next action of a closed deal without marking or a risk badge', async () => {
    // given: Won Deal(청명대학교 SSO/MFA)에 Due가 지난 Open Next Action을 등록한다
    const code = await dealCodeOf(11)
    const { client } = await renderAt('/deals?q=청명대학교 SSO')
    await rowOf(/청명대학교 SSO\/MFA/)
    await gateway.actions.create(code, { type: { name: '미팅' }, progress: '후속', nextAction: '후속 연락', dueDate: '2000-01-01', comment: '' })

    // when: 목록을 다시 읽는다
    await client.invalidateQueries()

    // then: 지난 Open 행을 보이지만 Due 강조·기한초과 배지·risk-overdue 클래스는 없다
    await waitFor(async () => expect(cellOf(await rowOf(/청명대학교 SSO\/MFA/), 'Next Action')).toHaveTextContent(/^후속 연락$/))
    const row = await rowOf(/청명대학교 SSO\/MFA/)
    expect(cellOf(row, 'Due Date')).toHaveTextContent('2000-01-01')
    expect(cellOf(row, 'Next Action 상태')).toHaveTextContent(/^Open$/)
    expect(isOverdueMarked(cellOf(row, 'Due Date'))).toBe(false)
    expect(within(row).queryByText('기한초과')).not.toBeInTheDocument()
    expect(row).not.toHaveClass('risk-overdue')
  })

  // 종료 상태 라벨은 상태 칸에만 보인다
  // 테스트 코드: DL-059
  it.each([
    ['done', '종료(수행)'],
    ['notDone', '종료(미수행)'],
  ] as const)('shows the %s status label in the status cell only', async (status, label) => {
    // given: 기준 행을 종료(수행/미수행)로 바꾼 Deal
    const code = await dealCodeOf(1)
    const { client } = await renderAt('/deals?q=한빛은행 ITDR')
    await rowOf(/한빛은행 ITDR 도입/)
    const basis = (await gateway.actions.list(code, {})).find((a) => a.nextAction === '계약서 초안 검토')
    if (!basis) throw new Error('기준 Action이 없습니다.')
    await gateway.actions.changeNextActionStatus(basis.id, { status, comment: '' })

    // when: 목록을 다시 읽는다
    await client.invalidateQueries()

    // then: 그 라벨이 Next Action 상태 칸에만 보인다
    await waitFor(() => expect(cellOf(screen.getByRole('row', { name: /한빛은행 ITDR 도입/ }), 'Next Action 상태')).toHaveTextContent(new RegExp(`^${label.replace(/[()]/g, '\\$&')}$`)))
    const row = screen.getByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(cellOf(row, 'Due Date')).not.toHaveTextContent(label)
    expect(cellOf(row, 'Next Action')).not.toHaveTextContent(label)
  })
})

describe('목록 열 정리: Next Action 없음 (AC4)', () => {
  // Next Action이 없으면 세 칸 모두 '—'다
  // 테스트 코드: DL-059
  it('shows a dash in all three cells', async () => {
    // given: Next Action이 없는 Deal
    const { client } = await renderAt('/deals?q=액션 없는 Deal')
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '액션 없는 Deal' }))
    await client.invalidateQueries()

    // when: 목록을 연다
    const row = await rowOf(/액션 없는 Deal/)

    // then: Next Action·Due·상태 칸이 모두 '—'다
    for (const header of ['Next Action', 'Due Date', 'Next Action 상태']) {
      expect(cellOf(row, header)).toHaveTextContent(/^—$/)
    }
    expect(isOverdueMarked(cellOf(row, 'Due Date'))).toBe(false)
    expect(within(row).queryAllByRole('link').filter((a) => a.getAttribute('href')?.includes('tab=actions'))).toEqual([])
  })
})
