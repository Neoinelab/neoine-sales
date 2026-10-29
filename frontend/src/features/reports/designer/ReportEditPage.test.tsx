// 편집 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportEditPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { mockControl } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'
import { showTab } from '../../../test/reportLayout'
import { addCountedColumn, chipButton, chipItems, chipTexts, lastQuery, openEditor, runQuery, saveButton, saveDialog, settingsOf, setupReportClock, typeName, UNSAVED_MARK, waitForHiddenResult } from '../../../test/reportScreen'
import {
  BROKEN_DEFINITION,
  MINE_PUBLIC,
  NO_REPORT_ID,
  PARK_PUBLIC,
  SAVED_SAMPLES,
  VENDOR_DEFINITION,
  reportInput,
  savedReport,
} from '../../../test/savedReports'

setupReportClock()

const NOT_FOUND_TEXT = '리포트를 찾을 수 없습니다. 삭제되었거나 볼 권한이 없습니다.'
const COPY_NAME = `${MINE_PUBLIC.name} 복사본`
const dialogOf = async () => within(await saveDialog())
const unsavedMark = () => screen.queryByText(UNSAVED_MARK)

describe('저장된 설계 불러오기 (AC15, S10)', () => {
  it('loads the saved design and runs it once', async () => {
    await openEditor(MINE_PUBLIC.id)

    expect(screen.getByRole('heading', { level: 1, name: MINE_PUBLIC.name })).toBeVisible()
    expect(chipItems()).toHaveLength(2)
    expect(chipTexts()[1]).toContain('금액 합계')
    expect(chipTexts()[1]).toContain('▼ 내림')
    expect(screen.queryByRole('combobox', { name: '정렬 방향' })).not.toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: '최대 행' })).toHaveDisplayValue('1,000')
    expect(screen.getByRole('combobox', { name: '조건 1 필드' })).toBeVisible()
    expect(mockControl.reportQueries()).toEqual([VENDOR_DEFINITION])
    expect(mockControl.savedReportRequests()).toEqual([])
    expect(unsavedMark()).not.toBeInTheDocument()
    for (const name of ['저장', '다른 이름으로 저장', '되돌리기']) expect(screen.getByRole('button', { name })).toBeVisible()
    expect(screen.queryByRole('button', { name: '초기화' })).not.toBeInTheDocument()
  })

  it('shows the saved column sort in the settings of that column', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)

    await user.click(chipButton(1))

    expect(within(settingsOf('금액 합계')).getByRole('combobox', { name: '정렬' })).toHaveDisplayValue('내림차순')
  })

  it('does not run again by itself after the first result', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)

    await addCountedColumn(user, 'Deal code')

    expect(mockControl.reportQueries()).toHaveLength(1)
  })

  it('opens a public report of someone else for a user role', async () => {
    await openEditor(PARK_PUBLIC.id, { role: 'user' })

    expect(screen.getByRole('heading', { level: 1, name: PARK_PUBLIC.name })).toBeVisible()
    expect(chipItems()).toHaveLength(2)
  })

  it('shows the not found guide for a hidden or missing report with a link to the list', async () => {
    await renderAt('/reports/14/edit', { savedReports: SAVED_SAMPLES })

    expect(await screen.findByText(NOT_FOUND_TEXT)).toBeVisible()
    expect(screen.getByRole('link', { name: '리포트 목록' })).toHaveAttribute('href', '/reports')
    expect(mockControl.reportQueries()).toEqual([])
  })

  it.each([String(NO_REPORT_ID), 'abc', '0', '1.5'])('shows the not found guide for the id %s', async (id) => {
    await renderAt(`/reports/${id}/edit`, { savedReports: SAVED_SAMPLES })

    expect(await screen.findByText(NOT_FOUND_TEXT)).toBeVisible()
  })

  it('keeps a field the catalog no longer has and shows the server violation after the first run', async () => {
    const broken = savedReport({ id: 20, name: '깨진 정의', definition: BROKEN_DEFINITION })
    await renderAt('/reports/20/edit', { savedReports: [broken] })

    expect(await screen.findByRole('heading', { level: 1, name: '깨진 정의' })).toBeVisible()
    expect((await screen.findAllByText(/허용되지 않은 필드입니다: deal\.nope/)).length).toBeGreaterThan(0)
    expect(chipItems()).toHaveLength(1)
    expect(chipTexts()[0]).toContain('deal.nope')
    expect(saveButton()).toBeDisabled()
  })
})

describe('저장 안 됨 표시와 덮어쓰기 (AC15, S11)', () => {
  it('shows the unsaved mark after a change and hides it after overwrite', async () => {
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    expect(unsavedMark()).not.toBeInTheDocument()

    await addCountedColumn(user, 'Deal code')

    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    expect(screen.getByText(UNSAVED_MARK)).toHaveAttribute('role', 'status')

    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await user.click(saveButton())
    const dialog = await dialogOf()
    expect(dialog.getByRole('textbox', { name: '이름' })).toHaveValue(MINE_PUBLIC.name)
    expect(dialog.getByRole('textbox', { name: '설명' })).toHaveValue(MINE_PUBLIC.description)
    expect(dialog.getByRole('combobox', { name: '공개 범위' })).toHaveDisplayValue('모든 사용자에게 보임')

    await user.click(dialog.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(unsavedMark()).not.toBeInTheDocument()
    expect(location()).toBe('/reports/11/edit')
    expect(screen.getByRole('heading', { level: 1, name: MINE_PUBLIC.name })).toBeVisible()
    const [update] = mockControl.savedReportRequests()
    expect(update).toMatchObject({ op: 'update', id: 11, body: { revision: 1, name: MINE_PUBLIC.name, visibility: 'public' } })
    expect((update?.body as { definition: typeof VENDOR_DEFINITION }).definition.columns).toHaveLength(3)
    expect(await gateway.reports.get(11)).toMatchObject({ revision: 2 })
  })

  it('hides the mark again when the change is undone', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)

    await addCountedColumn(user, 'Deal code')
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))

    expect(unsavedMark()).not.toBeInTheDocument()
  })

  it('overwrites again with the new revision after the first overwrite', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    for (const label of ['Deal code', 'Deal 이름']) {
      await showTab(user, 'design')
      await addCountedColumn(user, label)
      await runQuery(user)
      await waitFor(() => expect(saveButton()).toBeEnabled())
      await user.click(saveButton())
      await user.click((await dialogOf()).getByRole('button', { name: '저장' }))
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    }

    expect(mockControl.savedReportRequests().map((r) => (r.body as { revision: number }).revision)).toEqual([1, 2])
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  it('shows the mark again for a change made after the overwrite', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await user.click(saveButton())
    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(unsavedMark()).not.toBeInTheDocument())

    await showTab(user, 'design')
    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))

    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
  })

  it('renames the report with the title following the new name', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await user.click(saveButton())
    const dialog = await dialogOf()
    await typeName(user, await saveDialog(), '이름을 바꿈')

    await user.click(dialog.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('heading', { level: 1, name: '이름을 바꿈' })).toBeVisible()
  })
})

describe('충돌 (AC8, S12)', () => {
  /** 다른 사용자가 먼저 저장한 상황을 같은 계정의 순차 호출로 만든다(revision 1 → 2). */
  async function saveElsewhere(): Promise<void> {
    await gateway.reports.update(MINE_PUBLIC.id, { ...reportInput({ name: MINE_PUBLIC.name, description: MINE_PUBLIC.description }), revision: 1 })
  }

  it('shows the conflict and offers save as', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await saveElsewhere()
    await user.click(saveButton())
    const dialog = await dialogOf()

    await user.click(dialog.getByRole('button', { name: '저장' }))

    const alert = await dialog.findByRole('alert')
    expect(alert).toHaveTextContent('다른 사용자가 먼저 이 리포트를 저장했습니다')
    expect(within(alert).getByRole('button', { name: '다른 이름으로 저장' })).toBeVisible()
    expect(dialog.getByRole('button', { name: '닫기' })).toBeVisible()
    await showTab(user, 'design')
    expect(chipItems()).toHaveLength(3)
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 2 })
  })

  it('keeps the design when the conflict dialog is closed', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await saveElsewhere()
    await user.click(saveButton())
    const dialog = await dialogOf()
    await user.click(dialog.getByRole('button', { name: '저장' }))
    await dialog.findByRole('alert')

    await user.click(dialog.getByRole('button', { name: '닫기' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await showTab(user, 'design')
    expect(chipItems()).toHaveLength(3)
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
  })

  it('saves the design under another name from the conflict warning', async () => {
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await saveElsewhere()
    await user.click(saveButton())
    const dialog = await dialogOf()
    await user.click(dialog.getByRole('button', { name: '저장' }))
    const alert = await dialog.findByRole('alert')

    await user.click(within(alert).getByRole('button', { name: '다른 이름으로 저장' }))

    expect(dialog.getByRole('textbox', { name: '이름' })).toHaveValue(COPY_NAME)
    await user.click(dialog.getByRole('button', { name: '저장' }))
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    expect(mockControl.savedReportRequests().map((r) => r.op)).toEqual(['update', 'update', 'create'])
  })
})

describe('다른 이름으로 저장 (AC15, S13)', () => {
  it('save as creates a new report with the copy name', async () => {
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))
    const dialog = await dialogOf()
    expect(dialog.getByRole('textbox', { name: '이름' })).toHaveValue(COPY_NAME)
    expect(dialog.getByRole('combobox', { name: '공개 범위' })).toHaveDisplayValue('모든 사용자에게 보임')

    await user.click(dialog.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    expect(await screen.findByRole('heading', { level: 1, name: COPY_NAME })).toBeVisible()
    expect(unsavedMark()).not.toBeInTheDocument()
    const [create] = mockControl.savedReportRequests()
    expect(create).toMatchObject({ op: 'create', id: null, body: { name: COPY_NAME, visibility: 'public', definition: lastQuery() } })
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 1, definition: VENDOR_DEFINITION })
  })

  it('cuts the copy name to 100 characters', async () => {
    const longName = 'x'.repeat(98)
    const { user } = await renderAt('/reports/30/edit', { savedReports: [savedReport({ id: 30, name: longName })] })
    await waitForHiddenResult()

    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))

    const name = (await dialogOf()).getByRole('textbox', { name: '이름' })
    expect(name).toHaveValue(`${longName} 복사본`.slice(0, 100))
    expect((name as HTMLInputElement).value).toHaveLength(100)
  })

  it('keeps the visibility choice free for the copy of a report of someone else', async () => {
    const { user } = await openEditor(PARK_PUBLIC.id)

    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))

    expect((await dialogOf()).getByRole('combobox', { name: '공개 범위' })).toBeEnabled()
  })

  it('shows a duplicate name of the viewer next to the field', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))
    const dialog = await dialogOf()
    await typeName(user, await saveDialog(), MINE_PUBLIC.name)

    await user.click(dialog.getByRole('button', { name: '저장' }))

    expect(await dialog.findByText('같은 이름의 리포트가 이미 있습니다.')).toBeVisible()
  })
})

describe('공개 범위 (AC15, S14)', () => {
  it.each([
    ['sales', MINE_PUBLIC.id, true],
    ['admin', PARK_PUBLIC.id, true],
    ['sales', PARK_PUBLIC.id, false],
    ['user', MINE_PUBLIC.id, false],
  ] as const)('%s editing report %s: the visibility choice is enabled %s', async (role, id, enabled) => {
    const { user } = await openEditor(id, { role })
    await user.click(saveButton())
    const dialog = await dialogOf()

    const select = dialog.getByRole('combobox', { name: '공개 범위' })
    if (enabled) {
      expect(select).toBeEnabled()
      expect(dialog.queryByText('공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다')).not.toBeInTheDocument()
    } else {
      expect(select).toBeDisabled()
      expect(dialog.getByText('공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다')).toBeVisible()
    }
  })

  it('disables visibility for a non owner editor and still saves with the current visibility', async () => {
    const { user, location } = await openEditor(PARK_PUBLIC.id)
    await addCountedColumn(user, 'Deal 이름')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await user.click(saveButton())
    const dialog = await dialogOf()
    expect(dialog.getByRole('combobox', { name: '공개 범위' })).toBeDisabled()

    await user.click(dialog.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(location()).toBe('/reports/13/edit')
    expect(mockControl.savedReportRequests()[0]).toMatchObject({ op: 'update', id: 13, body: { visibility: 'public', revision: 1 } })
    expect(await gateway.reports.get(PARK_PUBLIC.id)).toMatchObject({ owner: { id: PARK_PUBLIC.owner.id }, updatedBy: { id: MINE_PUBLIC.owner.id } })
  })
})

describe('되돌리기 (AC15, S15)', () => {
  it('revert restores the saved design after confirmation', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await addCountedColumn(user, 'Deal 이름')
    expect(chipItems()).toHaveLength(4)

    await user.click(screen.getByRole('button', { name: '되돌리기' }))

    const dialog = await screen.findByRole('dialog', { name: '저장된 설계로 되돌릴까요?' })
    expect(dialog).toHaveTextContent('저장하지 않은 변경이 사라집니다.')
    await user.click(within(dialog).getByRole('button', { name: '되돌리기' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(chipItems()).toHaveLength(2)
    expect(chipTexts()[1]).toContain('금액 합계')
    expect(unsavedMark()).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests()).toEqual([])
  })

  it('keeps the changes when the revert is cancelled', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')

    await user.click(screen.getByRole('button', { name: '되돌리기' }))
    await user.click(within(await screen.findByRole('dialog', { name: '저장된 설계로 되돌릴까요?' })).getByRole('button', { name: '취소' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(chipItems()).toHaveLength(3)
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
  })

  it('reverts to the design as saved by the last overwrite, not the one loaded first', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await user.click(saveButton())
    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(unsavedMark()).not.toBeInTheDocument())
    await showTab(user, 'design')
    await addCountedColumn(user, 'Deal 이름')

    await user.click(screen.getByRole('button', { name: '되돌리기' }))
    await user.click(within(await screen.findByRole('dialog', { name: '저장된 설계로 되돌릴까요?' })).getByRole('button', { name: '되돌리기' }))

    expect(chipItems()).toHaveLength(3)
    expect(unsavedMark()).not.toBeInTheDocument()
  })
})
