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

describe('편집 화면의 탭 (작성/결과 탭 분리 AC7)', () => {
  it('opens on the design tab and fills the result tab with the automatic run without moving there', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)

    expectTab('design')
    expect(mockControl.reportQueries()).toHaveLength(1)
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()
    await showTab(user, 'result')
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()
  })
})

describe('저장된 배치로 열기 (AC18)', () => {
  it('shows the tiles in the saved order and arrangement', async () => {
    const { user } = await openSaved()
    await showTab(user, 'result')

    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
    expect(viewRadio('표+차트')).toBeChecked()
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  it('opens a report without a stored layout like the default: table then chart in two rows', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    await showTab(user, 'result')

    expect(tileOrder()).toEqual(['표', '차트'])
    expect(arrangement()).toBe('stacked')
    expect(viewRadio('표+차트')).toBeChecked()
  })
})

describe('배치만 바꿨을 때 (AC19)', () => {
  it('shows the unsaved mark for a layout change and hides it when the layout is put back', async () => {
    const { user } = await openSaved()
    await showTab(user, 'result')
    expect(unsavedMark()).not.toBeInTheDocument()

    dragTile('표', '차트', 'bottom')

    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    expect(screen.getByText(UNSAVED_MARK)).toHaveAttribute('role', 'status')

    dragTile('표', '차트', 'right')

    expect(unsavedMark()).not.toBeInTheDocument()
  })

  it('shows the unsaved mark for a view change too', async () => {
    const { user } = await openSaved()
    await showTab(user, 'result')

    await chooseView(user, '표만')

    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    await chooseView(user, '표+차트')
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  it('asks before leaving with a layout change only', async () => {
    const { user, location } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')

    await user.click(menuLink('Deals'))

    const dialog = await screen.findByRole('dialog', { name: '저장하지 않은 변경이 있습니다' })
    await user.click(within(dialog).getByRole('button', { name: '머물기' }))
    expect(location()).toBe(`/reports/${SAVED_LAYOUT.id}/edit`)
  })

  it('does not ask after the layout was put back', async () => {
    const { user, location } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')
    dragTile('표', '차트', 'right')

    await user.click(menuLink('Deals'))

    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('keeps the result fresh and does not ask for a new run after a layout change', async () => {
    const { user } = await openSaved()
    await showTab(user, 'result')

    dragTile('표', '차트', 'bottom')

    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()
    expect(saveButton()).toBeEnabled()
    expect(mockControl.reportQueries()).toHaveLength(1)
  })

  it('does not save by itself: the edit page waits for the save button', async () => {
    const { user } = await openSaved()
    await showTab(user, 'result')

    dragTile('표', '차트', 'bottom')
    await chooseView(user, '차트만')

    expect(mockControl.savedReportRequests()).toEqual([])
    expect(await gateway.reports.get(SAVED_LAYOUT.id)).toMatchObject({ revision: 1, layout: SIDE_CHART_FIRST })
  })

  it('overwrites a layout change without running again and sends the layout', async () => {
    const { user } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')
    await chooseView(user, '차트만')

    await overwrite(user)

    const [update] = mockControl.savedReportRequests()
    expect(update).toMatchObject({ op: 'update', id: SAVED_LAYOUT.id, body: { revision: 1, layout: { view: 'chart', order: ['chart', 'table'], arrange: 'stacked' } } })
    expect(mockControl.reportQueries()).toHaveLength(1)
    expect(await gateway.reports.get(SAVED_LAYOUT.id)).toMatchObject({
      revision: 2,
      layout: { view: 'chart', order: ['chart', 'table'], arrange: 'stacked' },
    })
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  it('treats the layout saved by the last overwrite as the new baseline', async () => {
    const { user } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')
    await overwrite(user)
    expect(unsavedMark()).not.toBeInTheDocument()

    dragTile('차트', '표', 'bottom') // 표 → 차트 순서의 두 줄로 되돌리면 방금 저장한 값(차트 → 표, 두 줄)과 다르다
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    dragTile('표', '차트', 'bottom')

    expect(unsavedMark()).not.toBeInTheDocument()
  })
})

describe('되돌리기와 배치 (AC19)', () => {
  async function revert(user: Awaited<ReturnType<typeof openEditor>>['user']): Promise<void> {
    await user.click(screen.getByRole('button', { name: '되돌리기' }))
    await user.click(within(await screen.findByRole('dialog', { name: '저장된 설계로 되돌릴까요?' })).getByRole('button', { name: '되돌리기' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  }

  it('restores the saved layout, not the default one', async () => {
    const { user } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')
    await chooseView(user, '표만')
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()

    await revert(user)

    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
    expect(viewRadio('표+차트')).toBeChecked()
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  it('asks for the confirmation even when only the layout changed', async () => {
    const { user } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')

    await user.click(screen.getByRole('button', { name: '되돌리기' }))

    expect(await screen.findByRole('dialog', { name: '저장된 설계로 되돌릴까요?' })).toBeVisible()
  })

  it('keeps the result when only the layout is reverted', async () => {
    const { user } = await openSaved()
    await showTab(user, 'result')
    dragTile('표', '차트', 'bottom')

    await revert(user)

    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(mockControl.reportQueries()).toHaveLength(1)
  })
})
