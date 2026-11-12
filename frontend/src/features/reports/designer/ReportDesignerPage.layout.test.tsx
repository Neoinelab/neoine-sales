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

describe('보기 방식', () => {
  // 테스트 코드: RS-085
  it('보기 방식은 라디오 셋이고 처음에는 표+차트로 시작한다', async () => {
    // when: 조회를 마친 디자이너(결과 탭, 기본 배치)를 연다
    await ready()

    // then: "보기" 그룹에 라디오 셋이 켜져 있고 표+차트가 선택되어 표 → 차트 순서다
    expect(within(screen.getByRole('radiogroup', { name: '보기' })).getAllByRole('radio')).toHaveLength(3)
    for (const label of VIEW_LABELS) expect(viewRadio(label)).toBeEnabled()
    expect(viewRadio('표+차트')).toBeChecked()
    expect(tileOrder()).toEqual(['표', '차트'])
  })

  // 테스트 코드: RS-085
  it('차트만을 고르면 차트 타일만 보인다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    const { user } = await ready()

    // when: 차트만을 고른다
    await chooseView(user, '차트만')

    // then: 차트 타일만 보인다
    expect(viewRadio('차트만')).toBeChecked()
    expect(queryTile('표')).toBeNull()
    expect(await screen.findByRole('region', { name: '차트 타일' })).toBeVisible()
  })

  // 테스트 코드: RS-085
  it('표만을 고르면 표 타일만 보인다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    const { user } = await ready()

    // when: 표만을 고른다
    await chooseView(user, '표만')

    // then: 표 타일만 보인다
    expect(viewRadio('표만')).toBeChecked()
    expect(queryTile('차트')).toBeNull()
    expect(within(tile('표')).getByRole('table', { name: '조회 결과' })).toBeVisible()
  })

  // 테스트 코드: RS-085
  it('표+차트를 다시 고르면 두 타일이 저장된 순서대로 보인다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    const { user } = await ready()
    // when: 배치를 바꾸고 표만을 거쳐 표+차트를 고른다
    dragTile('표', '차트', 'right')
    await chooseView(user, '표만')

    // when: 표+차트를 고른다
    await chooseView(user, '표+차트')

    // then: 바꾼 순서와 한 줄 배치가 유지된다
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
  })

  // 테스트 코드: RS-085
  it('다시 조회해도 고른 보기가 남는다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    const { user } = await ready()
    // when: 차트만을 고르고 작성 탭에서 다시 조회한다
    await chooseView(user, '차트만')
    await showTab(user, 'design')

    await user.click(screen.getByRole('button', { name: '조회' }))

    // then: 차트만이 그대로 선택되어 있다
    await screen.findByRole('radiogroup', { name: '보기' })
    expect(viewRadio('차트만')).toBeChecked()
  })
})

describe('차트가 없을 때의 차트 타일', () => {
  it('차트만 보기는 그룹핑 안내와 함께 차트 만들기 빈 상태를 보인다', async () => {
    // given: 그룹핑 없이 조회를 마친 디자이너
    const { user } = await ready()

    // when: 보기 방식을 차트만으로 바꾼다
    await chooseView(user, '차트만')
    const chart = tile('차트')

    // then: 차트 만들기 버튼은 꺼져 있고 그룹핑 안내가 보인다
    expect(await within(chart).findByRole('button', { name: '차트 만들기' })).toBeDisabled()
    expect(within(chart).getByText(NEEDS_GROUPING)).toBeVisible()
  })

  it('표+차트 보기는 표 옆에 같은 빈 상태를 보인다', async () => {
    // when: 그룹핑 없이 조회를 마친 디자이너를 연다
    await ready()

    // then: 차트 타일에 차트 만들기 버튼이 보인다
    expect(await within(tile('차트')).findByRole('button', { name: '차트 만들기' })).toBeVisible()
  })
})

describe('타일 머리', () => {
  it('표 타일 머리에 행 수 줄과 합계 행 체크박스를 둔다', async () => {
    // when: 합계가 있는 그룹핑 결과를 조회한다
    await openAndRun(groupedAmountResult([['A', 1_000_000]], [null, 1_000_000]), 'Vendor')
    const table = within(tile('표'))

    // then: 총 행 수·조회 시간 줄이 보이고 합계 행 체크박스는 꺼져 있다
    expect(table.getByText(/총 1행 · 조회 0\.21초|총 1행 · 조회 0\.\d\d초/)).toBeVisible()
    expect(table.getByRole('checkbox', { name: '합계 행' })).not.toBeChecked()
  })

  it('합계가 없는 결과의 표 타일에는 합계 행 체크박스가 없다', async () => {
    // when: 합계가 없는 결과를 조회한다
    await ready()

    // then: 표 타일에 합계 행 체크박스가 없다
    expect(within(tile('표')).queryByRole('checkbox', { name: '합계 행' })).not.toBeInTheDocument()
  })

  it('Deal 숫자를 한 번만 센 결과는 합계 행을 켜면 표 아래에 Deal 건수 안내를 둔다', async () => {
    // given: Action 행 범위에서 Deal 숫자를 한 번씩만 센 그룹핑 결과
    const { user } = await openAndRun(
      { ...groupedAmountResult([['A', 1000]], [null, 1000]), rowScope: 'action', actionFilter: 'join', dealNumbersOnce: true },
      'Vendor',
    )

    // when: 합계 행을 켠다
    await user.click(screen.getByRole('checkbox', { name: '합계 행' }))

    // then: 표 타일에 그룹마다 한 번씩 더한다는 안내가 보인다
    expect(within(tile('표')).getByText(/한 Deal이 여러 그룹에 나오면 그룹마다 한 번씩 더하므로/)).toBeVisible()
  })

  // 테스트 코드: RS-086
  it('타일 머리가 끄는 손잡이다', async () => {
    // when: 조회를 마친 디자이너(결과 탭, 기본 배치)를 연다
    await ready()

    // then: 두 타일 모두 머리에 draggable 손잡이가 있다
    for (const name of ['표', '차트'] as const) {
      const handles = tile(name).querySelectorAll('[draggable="true"]')
      expect(handles.length).toBeGreaterThan(0)
    }
  })
})

describe('끌어서 놓기', () => {
  // 테스트 코드: RS-085
  it('처음에는 표가 먼저인 두 줄이다', async () => {
    // when: 조회를 마친 디자이너(결과 탭, 기본 배치)를 연다
    await ready()

    // then: 표 → 차트, 두 줄이다
    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
    expect(tilesBox()).toHaveClass('report-tiles')
  })

  // 테스트 코드: RS-086
  it('표를 차트 오른쪽에 놓으면 차트 → 표 한 줄이다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    await ready()

    // when: 표를 차트 오른쪽에 놓는다
    dragTile('표', '차트', 'right')

    // then: 차트 → 표, 한 줄이다
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
  })

  // 테스트 코드: RS-086
  it('표를 차트 아래에 놓으면 차트 → 표 두 줄이다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    await ready()

    // when: 표를 차트 아래에 놓는다
    dragTile('표', '차트', 'bottom')

    // then: 차트 → 표, 두 줄이다
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('stacked')
  })

  // 테스트 코드: RS-086
  it('표를 차트 왼쪽에 놓으면 표 → 차트 한 줄이다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    await ready()

    // when: 표를 차트 왼쪽에 놓는다
    dragTile('표', '차트', 'left')

    // then: 표 → 차트, 한 줄이다
    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('side')
  })

  // 테스트 코드: RS-086
  it('표를 차트 위에 놓으면 표 → 차트 두 줄이다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치), 표를 차트 아래에 놓아 차트 → 표가 된 상태
    await ready()
    dragTile('표', '차트', 'bottom') // 차트 → 표

    // when: 표를 차트 위에 놓는다
    dragTile('표', '차트', 'top')

    // then: 표 → 차트, 두 줄이다
    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
  })

  // 테스트 코드: RS-086
  it.each([
    ['right', ['표', '차트'], 'side'],
    ['left', ['차트', '표'], 'side'],
    ['bottom', ['표', '차트'], 'stacked'],
    ['top', ['차트', '표'], 'stacked'],
  ] as const)('차트를 표의 %s 가장자리에 놓으면 순서와 줄이 정해진다', async (edge, order, arranged) => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    await ready()

    // when: 차트를 표의 해당 가장자리에 놓는다
    dragTile('차트', '표', edge)

    // then: 순서와 한 줄/두 줄이 가장자리에 맞다
    expect(tileOrder()).toEqual(order)
    expect(arrangement()).toBe(arranged)
  })

  // 테스트 코드: RS-086
  it('가로 바깥 20% 띠는 위쪽 절반이어도 오른쪽으로 판정한다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    await ready()

    // when: 타일 오른쪽 20% 띠의 위쪽 절반에 놓는다
    dragTile('표', '차트', { x: 290, y: 60 }) // 가로 200·세로 100 타일에서 가로 바깥 20% 안(정규화 0.95)이면 세로 위치와 무관하게 오른쪽

    // then: 오른쪽에 놓은 것으로 차트 → 표 한 줄이다
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
  })

  // 테스트 코드: RS-087
  it('자기 위에 놓으면 아무것도 바뀌지 않는다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    await ready()
    // when: 표를 끌어 자기 위에 놓는다
    const transfer = startDrag('표')

    dragOverTile(transfer, '표', EDGE_POINT.right)
    dropOnTile(transfer, '표', EDGE_POINT.right)
    endDrag(transfer, '표')

    // then: 배치가 그대로이고 놓일 가장자리 표시가 없다
    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
    expect(tile('표').className).not.toMatch(/is-drop-/)
  })

  // 테스트 코드: RS-087
  it('타일 밖에서 끝나면 아무것도 바뀌지 않는다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    await ready()
    // when: 표를 끌어 차트 위를 지나 타일 밖에서 끝낸다
    const transfer = startDrag('표')

    dragOverTile(transfer, '차트', EDGE_POINT.right)
    endDrag(transfer, '표')

    // then: 배치가 그대로이고 표시가 지워진다
    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
    expect(tile('차트').className).not.toMatch(/is-drop-/)
  })

  // 테스트 코드: RS-087
  it.each([
    ['right', 'is-drop-right'],
    ['left', 'is-drop-left'],
    ['top', 'is-drop-top'],
    ['bottom', 'is-drop-bottom'],
  ] as const)('끄는 동안 대상 타일의 %s 가장자리에 놓일 표시가 붙는다', async (edge, className) => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    await ready()
    // when: 표를 끌어 차트의 해당 가장자리 위로 지나간다
    const transfer = startDrag('표')

    dragOverTile(transfer, '차트', EDGE_POINT[edge])

    // then: 표시가 붙고 놓기 전에는 배치가 안 바뀌며 끝나면 표시가 지워진다
    expect(tile('차트')).toHaveClass(className)
    expect(tileOrder()).toEqual(['표', '차트']) // 놓기 전에는 배치가 바뀌지 않는다

    // when: 놓지 않고 끌기를 끝낸다
    endDrag(transfer, '표')

    // then: 표시가 지워진다
    expect(tile('차트')).not.toHaveClass(className)
  })

  // 테스트 코드: RS-087
  it('포인터를 다른 가장자리로 옮기면 표시도 따라 옮겨지고 놓으면 지워진다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    await ready()
    // when: 오른쪽 가장자리에서 아래쪽 가장자리로 옮긴다
    const transfer = startDrag('표')

    dragOverTile(transfer, '차트', EDGE_POINT.right)
    dragOverTile(transfer, '차트', EDGE_POINT.bottom)

    // then: 표시가 아래쪽으로 옮겨진다
    expect(tile('차트')).toHaveClass('is-drop-bottom')
    expect(tile('차트')).not.toHaveClass('is-drop-right')
    // when: 놓는다
    dropOnTile(transfer, '차트', EDGE_POINT.bottom)
    endDrag(transfer, '표')
    // then: 모든 표시가 지워진다
    expect(screen.getAllByRole('region', { name: /타일$/ }).every((r) => !/is-drop-/.test(r.className))).toBe(true)
  })

  // 테스트 코드: RS-084
  it('결과가 없어도 타일을 놓을 수 있다', async () => {
    // given: 조회 전 새 리포트 화면의 결과 탭
    const { user } = await openDesigner()
    await showTab(user, 'result')

    // when: 타일을 옮긴다
    dragTile('표', '차트', 'right')

    // then: 순서가 바뀐다
    expect(tileOrder()).toEqual(['차트', '표'])
  })

  // 테스트 코드: RS-089
  it('디자이너의 배치 변경은 저장 요청을 보내지 않는다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    const { user } = await ready()

    // when: 배치와 보기를 바꾼다
    dragTile('표', '차트', 'right')
    await chooseView(user, '표만')

    // then: 저장 요청이 없다
    expect(mockControl.savedReportRequests()).toEqual([])
  })
})

describe('키보드로 옮기기', () => {
  // 테스트 코드: RS-088
  it('두 타일이 보이면 둘 다 옮기기 버튼이 있다', async () => {
    // when: 조회를 마친 디자이너(결과 탭, 기본 배치)를 연다
    await ready()

    // then: 표·차트 모두 옮기기 버튼이 보인다
    expect(moveButton('표')).toBeVisible()
    expect(moveButton('차트')).toBeVisible()
  })

  // 테스트 코드: RS-088
  it('Alt+→로 표를 차트 오른쪽에 옮기고 포커스를 두며 안내한다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    const { user } = await ready()

    // when: 표 옮기기 버튼에서 Alt+→를 누른다
    await moveByKey(user, '표', 'ArrowRight')

    // then: 차트 → 표 한 줄이고 포커스가 같은 버튼에 남으며 안내가 알려진다
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
    expect(moveButton('표')).toHaveFocus()
    const note = screen.getByText('표를 차트 오른쪽에 놓았습니다(한 줄)')
    expect(note.closest('[aria-live="polite"]')).not.toBeNull()
  })

  // 테스트 코드: RS-088
  it('Alt+↓로 표를 차트 아래에 옮긴다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    const { user } = await ready()

    // when: 표 옮기기 버튼에서 Alt+↓를 누른다
    await moveByKey(user, '표', 'ArrowDown')

    // then: 차트 → 표 두 줄이고 안내가 나온다
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('stacked')
    expect(screen.getByText('표를 차트 아래에 놓았습니다(두 줄)')).toBeInTheDocument()
  })

  // 테스트 코드: RS-088
  it('Alt+←로 표를 차트 왼쪽에 옮긴다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    const { user } = await ready()

    // when: 표 옮기기 버튼에서 Alt+←를 누른다
    await moveByKey(user, '표', 'ArrowLeft')

    // then: 표 → 차트 한 줄이고 안내가 나온다
    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('side')
    expect(screen.getByText('표를 차트 왼쪽에 놓았습니다(한 줄)')).toBeInTheDocument()
  })

  // 테스트 코드: RS-088
  it('차트 버튼의 Alt+↑로 차트를 표 위에 옮긴다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    const { user } = await ready()

    // when: 차트 옮기기 버튼에서 Alt+↑를 누른다
    await moveByKey(user, '차트', 'ArrowUp')

    // then: 차트 → 표 두 줄이고 포커스가 차트 버튼에 남으며 안내가 나온다
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('stacked')
    expect(moveButton('차트')).toHaveFocus()
    expect(screen.getByText('차트를 표 위에 놓았습니다(두 줄)')).toBeInTheDocument()
  })

  // 테스트 코드: RS-088
  it('Alt 없는 화살표는 아무것도 바꾸지 않는다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    const { user } = await ready()
    // when: 옮기기 버튼에서 Alt 없이 →를 누른다
    moveButton('표').focus()

    await user.keyboard('{ArrowRight}')

    // then: 배치가 그대로다
    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
  })

  // 테스트 코드: RS-088
  it.each(['표만', '차트만'] as const)('타일이 하나만 보이면(%s) 옮기기 버튼이 없다', async (view) => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    const { user } = await ready()

    // when: 한 타일만 보이는 보기를 고른다
    await chooseView(user, view)

    // then: 옮기기 버튼이 없다
    expect(queryMoveButton('표')).toBeNull()
    expect(queryMoveButton('차트')).toBeNull()
  })
})

describe('새 리포트의 초기화와 배치', () => {
  // 테스트 코드: RS-089
  it('배치만 바꿔서는 저장 안 됨이 붙지 않는다', async () => {
    // given: 새 리포트 화면의 결과 탭
    const { user } = await openDesigner()
    await showTab(user, 'result')

    // when: 배치와 보기를 바꾼다
    dragTile('표', '차트', 'right')
    await chooseView(user, '표만')

    // then: 저장 안 됨이 없다
    expect(screen.queryByText(UNSAVED_MARK)).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-089
  it('배치만 바꾼 채 떠나도 묻지 않는다', async () => {
    // given: 배치만 바꾼 새 리포트 화면
    const { user, location } = await openDesigner()
    await showTab(user, 'result')
    dragTile('표', '차트', 'right')

    // when: 상단 메뉴 링크를 누른다
    await user.click(within(screen.getByRole('navigation', { name: '주 메뉴' })).getByRole('link', { name: 'Deals' }))

    // then: 묻지 않고 이동한다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(location()).toMatch(/^\/deals/)
  })

  // 테스트 코드: RS-089
  it('다른 변경이 없으면 초기화는 확인 없이 배치를 기본으로 돌린다', async () => {
    // given: 배치만 바꾼 새 리포트 화면
    const { user } = await openDesigner()
    await showTab(user, 'result')
    dragTile('표', '차트', 'right')
    await chooseView(user, '차트만')

    // when: 초기화를 누른다
    await user.click(screen.getByRole('button', { name: '초기화' }))

    // then: 확인 창 없이 기본 배치다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(viewRadio('표+차트')).toBeChecked()
    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
  })

  // 테스트 코드: RS-089
  it('설계도 바꿨다면 확인 뒤 초기화가 설계와 배치를 함께 되돌린다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    const { user } = await ready()
    dragTile('표', '차트', 'right')
    await chooseView(user, '표만')
    await showTab(user, 'design')

    // when: 초기화를 누르고 확인한다
    await user.click(screen.getByRole('button', { name: '초기화' }))
    await user.click(within(await screen.findByRole('dialog', { name: '설계를 모두 지울까요?' })).getByRole('button', { name: '초기화' }))
    await showTab(user, 'result')

    // then: 설계와 함께 배치가 기본이 된다
    expect(viewRadio('표+차트')).toBeChecked()
    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
  })
})

describe('추가 확인', () => {
  // 테스트 코드: RS-089
  it('작성 탭에서 컬럼을 넣어도 배치는 그대로다', async () => {
    // given: 조회를 마친 디자이너(결과 탭, 기본 배치)
    const { user } = await ready()
    dragTile('표', '차트', 'right')
    await showTab(user, 'design')

    // when: 배치를 바꾼 뒤 작성 탭에서 컬럼을 넣는다
    await addColumn(user, 'Deal 이름')
    await showTab(user, 'result')

    // then: 바꾼 배치가 그대로다
    expect(tileOrder()).toEqual(['차트', '표'])
  })
})
