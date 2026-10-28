import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockControl } from '../../../test/fake/default'
import { groupedAmountResult, resultOf } from '../../../test/reportDesigner'
import {
  arrangement,
  chooseView,
  dragOverTile,
  dragTile,
  dropOnTile,
  EDGE_POINT,
  endDrag,
  moveButton,
  moveByKey,
  queryMoveButton,
  queryTile,
  showTab,
  startDrag,
  tile,
  tilesBox,
  tileOrder,
  viewRadio,
  VIEW_LABELS,
} from '../../../test/reportLayout'
import { addColumn, openAndRun, openDesigner, setupReportClock, UNSAVED_MARK } from '../../../test/reportScreen'

setupReportClock()

const NEEDS_GROUPING = '그룹핑한 결과로 차트를 만들 수 있습니다'

/** 결과를 만든 디자이너(결과 탭, 표+차트, 표 → 차트 두 줄 기본 배치). */
const ready = () => openAndRun(resultOf({ rows: [['A'], ['B'], ['C']], elapsedMs: 210 }), 'Deal code')

describe('보기 방식 (AC9)', () => {
  it('offers three radios in a group named view and starts with table and chart', async () => {
    await ready()

    expect(within(screen.getByRole('radiogroup', { name: '보기' })).getAllByRole('radio')).toHaveLength(3)
    for (const label of VIEW_LABELS) expect(viewRadio(label)).toBeEnabled()
    expect(viewRadio('표+차트')).toBeChecked()
    expect(tileOrder()).toEqual(['표', '차트'])
  })

  it('shows only the chart tile for chart only', async () => {
    const { user } = await ready()

    await chooseView(user, '차트만')

    expect(viewRadio('차트만')).toBeChecked()
    expect(queryTile('표')).toBeNull()
    expect(await screen.findByRole('region', { name: '차트 타일' })).toBeVisible()
  })

  it('shows only the table tile for table only', async () => {
    const { user } = await ready()

    await chooseView(user, '표만')

    expect(viewRadio('표만')).toBeChecked()
    expect(queryTile('차트')).toBeNull()
    expect(within(tile('표')).getByRole('table', { name: '조회 결과' })).toBeVisible()
  })

  it('shows both tiles again for table and chart and keeps the order', async () => {
    const { user } = await ready()
    dragTile('표', '차트', 'right')
    await chooseView(user, '표만')

    await chooseView(user, '표+차트')

    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
  })

  it('keeps the chosen view after running again', async () => {
    const { user } = await ready()
    await chooseView(user, '차트만')
    await showTab(user, 'design')

    await user.click(screen.getByRole('button', { name: '조회' }))

    await screen.findByRole('radiogroup', { name: '보기' })
    expect(viewRadio('차트만')).toBeChecked()
  })
})

describe('차트가 없을 때의 차트 타일 (AC10)', () => {
  it('shows the make-chart empty state with the grouping guide for chart only', async () => {
    const { user } = await ready()

    await chooseView(user, '차트만')

    const chart = tile('차트')
    expect(await within(chart).findByRole('button', { name: '차트 만들기' })).toBeDisabled()
    expect(within(chart).getByText(NEEDS_GROUPING)).toBeVisible()
  })

  it('shows the same empty state next to the table for table and chart', async () => {
    await ready()

    expect(await within(tile('차트')).findByRole('button', { name: '차트 만들기' })).toBeVisible()
  })
})

describe('타일 머리 (AC15)', () => {
  it('puts the row count line and the totals checkbox in the table tile head', async () => {
    await openAndRun(groupedAmountResult([['A', 1_000_000]], [null, 1_000_000]), 'Vendor')
    const table = within(tile('표'))

    expect(table.getByText(/총 1행 · 조회 0\.21초|총 1행 · 조회 0\.\d\d초/)).toBeVisible()
    expect(table.getByRole('checkbox', { name: '합계 행' })).not.toBeChecked()
  })

  it('has no totals checkbox in the table tile without totals', async () => {
    await ready()

    expect(within(tile('표')).queryByRole('checkbox', { name: '합계 행' })).not.toBeInTheDocument()
  })

  it('keeps the Deal count note under the table when Deal numbers are counted once', async () => {
    const { user } = await openAndRun(
      { ...groupedAmountResult([['A', 1000]], [null, 1000]), rowScope: 'action', actionFilter: 'join', dealNumbersOnce: true },
      'Vendor',
    )

    await user.click(screen.getByRole('checkbox', { name: '합계 행' }))

    expect(within(tile('표')).getByText(/한 Deal이 여러 그룹에 나오면 그룹마다 한 번씩 더하므로/)).toBeVisible()
  })

  it('makes the tile head the drag handle', async () => {
    await ready()

    for (const name of ['표', '차트'] as const) {
      const handles = tile(name).querySelectorAll('[draggable="true"]')
      expect(handles.length).toBeGreaterThan(0)
    }
  })
})

describe('끌어서 놓기 (AC12)', () => {
  it('starts with the table first in two rows', async () => {
    await ready()

    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
    expect(tilesBox()).toHaveClass('report-tiles')
  })

  it('puts the table right of the chart: chart then table in one row', async () => {
    await ready()

    dragTile('표', '차트', 'right')

    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
  })

  it('puts the table below the chart: chart then table in two rows', async () => {
    await ready()

    dragTile('표', '차트', 'bottom')

    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('stacked')
  })

  it('puts the table left of the chart: table then chart in one row', async () => {
    await ready()

    dragTile('표', '차트', 'left')

    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('side')
  })

  it('puts the table above the chart: table then chart in two rows', async () => {
    await ready()
    dragTile('표', '차트', 'bottom') // 차트 → 표

    dragTile('표', '차트', 'top')

    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
  })

  it.each([
    ['right', ['표', '차트'], 'side'],
    ['left', ['차트', '표'], 'side'],
    ['bottom', ['표', '차트'], 'stacked'],
    ['top', ['차트', '표'], 'stacked'],
  ] as const)('puts the chart %s of the table', async (edge, order, arranged) => {
    await ready()

    dragTile('차트', '표', edge)

    expect(tileOrder()).toEqual(order)
    expect(arrangement()).toBe(arranged)
  })

  it('decides by the nearest edge of the tile: a drop near the right edge of the upper half is a right drop', async () => {
    await ready()

    dragTile('표', '차트', { x: 290, y: 60 }) // 가로 200·세로 100 타일에서 오른쪽 가장자리 10px, 위 가장자리 10px(정규화 0.05와 0.1)

    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
  })

  it('does nothing when a tile is dropped on itself', async () => {
    await ready()
    const transfer = startDrag('표')

    dragOverTile(transfer, '표', EDGE_POINT.right)
    dropOnTile(transfer, '표', EDGE_POINT.right)
    endDrag(transfer, '표')

    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
    expect(tile('표').className).not.toMatch(/is-drop-/)
  })

  it('does nothing when the drag ends outside any tile', async () => {
    await ready()
    const transfer = startDrag('표')

    dragOverTile(transfer, '차트', EDGE_POINT.right)
    endDrag(transfer, '표')

    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
    expect(tile('차트').className).not.toMatch(/is-drop-/)
  })

  it.each([
    ['right', 'is-drop-right'],
    ['left', 'is-drop-left'],
    ['top', 'is-drop-top'],
    ['bottom', 'is-drop-bottom'],
  ] as const)('marks the %s edge of the target tile while dragging over it', async (edge, className) => {
    await ready()
    const transfer = startDrag('표')

    dragOverTile(transfer, '차트', EDGE_POINT[edge])

    expect(tile('차트')).toHaveClass(className)
    expect(tileOrder()).toEqual(['표', '차트']) // 놓기 전에는 배치가 바뀌지 않는다
    endDrag(transfer, '표')
    expect(tile('차트')).not.toHaveClass(className)
  })

  it('moves the mark when the pointer moves to another edge and clears it after the drop', async () => {
    await ready()
    const transfer = startDrag('표')

    dragOverTile(transfer, '차트', EDGE_POINT.right)
    dragOverTile(transfer, '차트', EDGE_POINT.bottom)

    expect(tile('차트')).toHaveClass('is-drop-bottom')
    expect(tile('차트')).not.toHaveClass('is-drop-right')
    dropOnTile(transfer, '차트', EDGE_POINT.bottom)
    endDrag(transfer, '표')
    expect(screen.getAllByRole('region', { name: /타일$/ }).every((r) => !/is-drop-/.test(r.className))).toBe(true)
  })

  it('drops into the empty-result layout too', async () => {
    const { user } = await openDesigner()
    await showTab(user, 'result')

    dragTile('표', '차트', 'right')

    expect(tileOrder()).toEqual(['차트', '표'])
  })

  it('does not send any save request for a layout change in the designer', async () => {
    const { user } = await ready()

    dragTile('표', '차트', 'right')
    await chooseView(user, '표만')

    expect(mockControl.savedReportRequests()).toEqual([])
  })
})

describe('키보드로 옮기기 (AC13)', () => {
  it('has move buttons on both tiles while two tiles are shown', async () => {
    await ready()

    expect(moveButton('표')).toBeVisible()
    expect(moveButton('차트')).toBeVisible()
  })

  it('moves the table right of the chart with Alt+ArrowRight, keeps the focus and announces it', async () => {
    const { user } = await ready()

    await moveByKey(user, '표', 'ArrowRight')

    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
    expect(moveButton('표')).toHaveFocus()
    const note = screen.getByText('표를 차트 오른쪽에 놓았습니다(한 줄)')
    expect(note.closest('[aria-live="polite"]')).not.toBeNull()
  })

  it('moves the table below the chart with Alt+ArrowDown', async () => {
    const { user } = await ready()

    await moveByKey(user, '표', 'ArrowDown')

    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('stacked')
    expect(screen.getByText('표를 차트 아래에 놓았습니다(두 줄)')).toBeInTheDocument()
  })

  it('moves the table left of the chart with Alt+ArrowLeft', async () => {
    const { user } = await ready()

    await moveByKey(user, '표', 'ArrowLeft')

    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('side')
    expect(screen.getByText('표를 차트 왼쪽에 놓았습니다(한 줄)')).toBeInTheDocument()
  })

  it('moves the chart above the table with Alt+ArrowUp from the chart button', async () => {
    const { user } = await ready()

    await moveByKey(user, '차트', 'ArrowUp')

    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('stacked')
    expect(moveButton('차트')).toHaveFocus()
    expect(screen.getByText('차트를 표 위에 놓았습니다(두 줄)')).toBeInTheDocument()
  })

  it('does not move on an arrow key without Alt', async () => {
    const { user } = await ready()
    moveButton('표').focus()

    await user.keyboard('{ArrowRight}')

    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
  })

  it.each(['표만', '차트만'] as const)('has no move button when only one tile is shown (%s)', async (view) => {
    const { user } = await ready()

    await chooseView(user, view)

    expect(queryMoveButton('표')).toBeNull()
    expect(queryMoveButton('차트')).toBeNull()
  })
})

describe('새 리포트의 초기화와 배치 (AC20)', () => {
  it('does not show the unsaved mark for a layout change alone', async () => {
    const { user } = await openDesigner()
    await showTab(user, 'result')

    dragTile('표', '차트', 'right')
    await chooseView(user, '표만')

    expect(screen.queryByText(UNSAVED_MARK)).not.toBeInTheDocument()
  })

  it('leaves without asking after a layout change alone', async () => {
    const { user, location } = await openDesigner()
    await showTab(user, 'result')
    dragTile('표', '차트', 'right')

    await user.click(within(screen.getByRole('navigation', { name: '주 메뉴' })).getByRole('link', { name: 'Deals' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(location()).toMatch(/^\/deals/)
  })

  it('resets the layout to the default with the reset button without asking when nothing else changed', async () => {
    const { user } = await openDesigner()
    await showTab(user, 'result')
    dragTile('표', '차트', 'right')
    await chooseView(user, '차트만')

    await user.click(screen.getByRole('button', { name: '초기화' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(viewRadio('표+차트')).toBeChecked()
    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
  })

  it('resets the layout together with the design after the confirmation', async () => {
    const { user } = await ready()
    dragTile('표', '차트', 'right')
    await chooseView(user, '표만')
    await showTab(user, 'design')

    await user.click(screen.getByRole('button', { name: '초기화' }))
    await user.click(within(await screen.findByRole('dialog', { name: '설계를 모두 지울까요?' })).getByRole('button', { name: '초기화' }))
    await showTab(user, 'result')

    expect(viewRadio('표+차트')).toBeChecked()
    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
  })
})

describe('추가 확인', () => {
  it('adds a column on the design tab without touching the layout', async () => {
    const { user } = await ready()
    dragTile('표', '차트', 'right')
    await showTab(user, 'design')

    await addColumn(user, 'Deal 이름')
    await showTab(user, 'result')

    expect(tileOrder()).toEqual(['차트', '표'])
  })
})
