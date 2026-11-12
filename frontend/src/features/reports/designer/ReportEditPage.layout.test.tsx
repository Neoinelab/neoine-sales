// 편집 화면은 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportEditPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { mockControl } from '../../../test/fake/default'
import { arrangement, chooseView, dragTile, expectTab, showTab, tileOrder, viewRadio } from '../../../test/reportLayout'
import { openEditor, saveButton, saveDialog, setupReportClock, UNSAVED_MARK } from '../../../test/reportScreen'
import { MINE_PUBLIC, SAVED_SAMPLES, VENDOR_CHART, savedReport } from '../../../test/savedReports'

setupReportClock()

const SIDE_CHART_FIRST = { view: 'both', order: ['chart', 'table'], arrange: 'side_by_side' } as const
const SAVED_LAYOUT = savedReport({ id: 31, name: '배치가 있는 리포트', chart: VENDOR_CHART, layout: SIDE_CHART_FIRST })
const menuLink = (name: string): HTMLElement => within(screen.getByRole('navigation', { name: '주 메뉴' })).getByRole('link', { name })
const unsavedMark = () => screen.queryByText(UNSAVED_MARK)
const openSaved = () => openEditor(SAVED_LAYOUT.id, { savedReports: [...SAVED_SAMPLES, SAVED_LAYOUT] })

async function overwrite(user: Awaited<ReturnType<typeof openEditor>>['user']): Promise<void> {
  await waitFor(() => expect(saveButton()).toBeEnabled())
  await user.click(saveButton())
  await user.click(within(await saveDialog()).getByRole('button', { name: '저장' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
}

describe('편집 화면의 탭', () => {
  // 테스트 코드: RS-073
  it('편집 화면은 작성 탭으로 열고 자동 조회 결과를 결과 탭에 채우되 탭은 옮기지 않는다', async () => {
    // when: 편집 화면을 연다
    const { user } = await openEditor(MINE_PUBLIC.id)

    // then: 작성 탭이고 조회가 한 번이며 결과 표는 숨어 있다
    expectTab('design')
    expect(mockControl.reportQueries()).toHaveLength(1)
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()
    // when: 결과 탭을 연다
    await showTab(user, 'result')
    // then: 자동 조회 결과가 채워져 있다
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()
  })
})

describe('저장된 배치로 열기', () => {
  // 테스트 코드: RS-091
  it('저장된 순서와 배치대로 타일을 보인다', async () => {
    // given: 배치(차트 → 표, 한 줄)가 저장된 리포트의 편집 화면
    const { user } = await openSaved()
    // when: 결과 탭을 연다
    await showTab(user, 'result')

    // then: 저장된 순서·한 줄·표+차트이고 저장 안 됨이 없다
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
    expect(viewRadio('표+차트')).toBeChecked()
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-091
  it('저장된 배치가 없던 리포트는 기본 배치(표 → 차트, 두 줄)로 연다', async () => {
    // given: 배치가 저장되지 않은 리포트의 편집 화면
    const { user } = await openEditor(MINE_PUBLIC.id)
    // when: 결과 탭을 연다
    await showTab(user, 'result')

    // then: 기본 배치다
    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
    expect(viewRadio('표+차트')).toBeChecked()
  })
})

describe('배치만 바꿨을 때', () => {
  // 테스트 코드: RS-091
  it('배치를 바꾸면 저장 안 됨이 붙고 원래대로 돌리면 사라진다', async () => {
    // given: 저장된 배치의 편집 화면 결과 탭
    const { user } = await openSaved()
    await showTab(user, 'result')
    expect(unsavedMark()).not.toBeInTheDocument()

    // when: 타일을 옮긴다
    dragTile('표', '차트', 'bottom')

    // then: 저장 안 됨이 붙는다
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    expect(screen.getByText(UNSAVED_MARK)).toHaveAttribute('role', 'status')

    // when: 원래 배치로 돌린다
    dragTile('표', '차트', 'right')

    // then: 저장 안 됨이 사라진다
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-091
  it('보기 방식을 바꿔도 저장 안 됨이 붙는다', async () => {
    // given: 저장된 배치의 편집 화면 결과 탭
    const { user } = await openSaved()
    await showTab(user, 'result')

    // when: 표만을 고른다
    await chooseView(user, '표만')

    // then: 저장 안 됨이 붙고
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    // when: 원래 보기로 돌린다
    await chooseView(user, '표+차트')
    // then: 사라진다
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-091
  it('배치만 바꾼 채 떠나면 확인한다', async () => {
    // given: 배치만 바꾼 편집 화면
    const { user, location } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')

    // when: 상단 메뉴 링크를 누른다
    await user.click(menuLink('Deals'))

    // then: 떠날 때 확인 창이 뜨고
    const dialog = await screen.findByRole('dialog', { name: '저장하지 않은 변경이 있습니다' })
    // when: 머물기를 누른다
    await user.click(within(dialog).getByRole('button', { name: '머물기' }))
    // then: 화면에 머문다
    expect(location()).toBe(`/reports/${SAVED_LAYOUT.id}/edit`)
  })

  // 테스트 코드: RS-091
  it('배치를 원래대로 돌린 뒤에는 묻지 않는다', async () => {
    // given: 배치를 바꿨다가 되돌린 편집 화면
    const { user, location } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')
    dragTile('표', '차트', 'right')

    // when: 상단 메뉴 링크를 누른다
    await user.click(menuLink('Deals'))

    // then: 묻지 않고 이동한다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-091
  it('배치를 바꿔도 다시 조회를 요구하지 않는다', async () => {
    // given: 편집 화면 결과 탭
    const { user } = await openSaved()
    await showTab(user, 'result')

    // when: 타일을 옮긴다
    dragTile('표', '차트', 'bottom')

    // then: 안내가 없고 저장이 켜져 있으며 조회는 한 번뿐이다
    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()
    expect(saveButton()).toBeEnabled()
    expect(mockControl.reportQueries()).toHaveLength(1)
  })

  // 테스트 코드: RS-092
  it('편집 화면의 배치는 스스로 저장되지 않는다', async () => {
    // given: 편집 화면 결과 탭
    const { user } = await openSaved()
    await showTab(user, 'result')

    // when: 배치와 보기를 바꾸고 기다린다
    dragTile('표', '차트', 'bottom')
    await chooseView(user, '차트만')

    // then: 요청이 없고 서버 배치는 그대로다
    expect(mockControl.savedReportRequests()).toEqual([])
    expect(await gateway.reports.get(SAVED_LAYOUT.id)).toMatchObject({ revision: 1, layout: SIDE_CHART_FIRST })
  })

  // 테스트 코드: RS-092
  it('배치 변경은 다시 조회 없이 덮어쓰기로 저장된다', async () => {
    // given: 배치를 바꾼 편집 화면
    const { user } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')
    await chooseView(user, '차트만')

    // when: 저장한다
    await overwrite(user)

    // then: 덮어쓰기 요청에 배치가 실리고 조회는 더 가지 않으며 서버에 반영되고 저장 안 됨이 없다
    const [update] = mockControl.savedReportRequests()
    expect(update).toMatchObject({ op: 'update', id: SAVED_LAYOUT.id, body: { revision: 1, layout: { view: 'chart', order: ['chart', 'table'], arrange: 'stacked' } } })
    expect(mockControl.reportQueries()).toHaveLength(1)
    expect(await gateway.reports.get(SAVED_LAYOUT.id)).toMatchObject({
      revision: 2,
      layout: { view: 'chart', order: ['chart', 'table'], arrange: 'stacked' },
    })
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-092
  it('마지막 덮어쓰기의 배치가 새 기준선이 된다', async () => {
    // given: 배치를 바꿔 덮어쓴 편집 화면
    const { user } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')
    await overwrite(user)
    expect(unsavedMark()).not.toBeInTheDocument()

    // when: 저장한 배치와 다른 배치로 옮긴다
    dragTile('차트', '표', 'bottom') // 표 → 차트 순서의 두 줄로 되돌리면 방금 저장한 값(차트 → 표, 두 줄)과 다르다
    // then: 저장 안 됨이 붙는다
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    // when: 저장한 배치로 돌린다
    dragTile('표', '차트', 'bottom')

    // then: 사라진다
    expect(unsavedMark()).not.toBeInTheDocument()
  })
})

describe('되돌리기와 배치', () => {
  async function revert(user: Awaited<ReturnType<typeof openEditor>>['user']): Promise<void> {
    await user.click(screen.getByRole('button', { name: '되돌리기' }))
    await user.click(within(await screen.findByRole('dialog', { name: '저장된 설계로 되돌릴까요?' })).getByRole('button', { name: '되돌리기' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  }

  // 테스트 코드: RS-092
  it('되돌리기는 기본 배치가 아니라 저장된 배치로 돌아간다', async () => {
    // given: 배치와 보기를 바꾼 편집 화면
    const { user } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')
    await chooseView(user, '표만')
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()

    // when: 되돌리기를 확인한다
    await revert(user)

    // then: 저장된 배치로 돌아가고 저장 안 됨이 없다
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
    expect(viewRadio('표+차트')).toBeChecked()
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-092
  it('배치만 바꿔도 되돌리기는 확인을 거친다', async () => {
    // given: 배치만 바꾼 편집 화면
    const { user } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')

    // when: 되돌리기를 누른다
    await user.click(screen.getByRole('button', { name: '되돌리기' }))

    // then: 확인 창이 뜬다
    expect(await screen.findByRole('dialog', { name: '저장된 설계로 되돌릴까요?' })).toBeVisible()
  })

  // 테스트 코드: RS-092
  it('배치만 되돌리면 결과는 남는다', async () => {
    // given: 배치만 바꾼 편집 화면
    const { user } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')

    // when: 되돌리기를 확인한다
    await revert(user)

    // then: 결과 표가 남고 조회는 한 번뿐이다
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(mockControl.reportQueries()).toHaveLength(1)
  })
})
