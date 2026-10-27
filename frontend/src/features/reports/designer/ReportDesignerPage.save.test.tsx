// 저장 뒤 이동하는 편집 화면은 React.lazy 청크이므로 미리 읽어 둔다.
import './ReportEditPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockControl } from '../../../test/fake/default'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import { addColumn, lastQuery, openAndRun, openDesigner, runQuery, saveButton, saveDialog, setupReportClock, typeName, UNSAVED_MARK } from '../../../test/reportScreen'
import { MINE_PUBLIC, SAVED_SAMPLES } from '../../../test/savedReports'

setupReportClock()

const GUIDE = '저장 내용: 컬럼·조건·정렬·행 수와 생성 SQL. 결과 데이터는 저장하지 않고 열 때마다 다시 조회합니다.'
const CREATED = '/reports/16/edit'

/** 새 리포트에서 컬럼 하나를 넣고 조회해 저장할 수 있는 상태로 만든다. */
async function openReady(role: 'admin' | 'sales' | 'user' = 'sales') {
  const rendered = await openDesigner({ role, savedReports: SAVED_SAMPLES })
  await addColumn(rendered.user, 'Deal code')
  await runQuery(rendered.user)
  await screen.findByRole('table', { name: '조회 결과' })
  return rendered
}

describe('저장 단추 활성 조건 (AC14, S6)', () => {
  it('enables save only with a fresh result', async () => {
    const { user } = await openDesigner({ savedReports: SAVED_SAMPLES })
    expect(saveButton()).toBeDisabled()
    expect(saveButton()).toHaveAttribute('title', '먼저 조회하세요')

    await addColumn(user, 'Deal code')
    expect(saveButton()).toBeDisabled()
    expect(saveButton()).toHaveAttribute('title', '먼저 조회하세요')

    await runQuery(user)
    await screen.findByRole('table', { name: '조회 결과' })
    expect(saveButton()).toBeEnabled()
    expect(saveButton().getAttribute('title') ?? '').not.toMatch(/조회/)

    await addColumn(user, 'Deal 이름')
    expect(saveButton()).toBeDisabled()
    expect(saveButton()).toHaveAttribute('title', '바뀐 설계를 다시 조회한 뒤 저장하세요')

    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
  })

  it('keeps save off when the run failed', async () => {
    const { user } = await openDesigner({ savedReports: SAVED_SAMPLES })
    await addColumn(user, 'Action 건수')

    await runQuery(user)

    expect(await screen.findByRole('alert')).toBeVisible()
    expect(saveButton()).toBeDisabled()
    expect(saveButton()).toHaveAttribute('title', '먼저 조회하세요')
  })

  it('does not show the other-name button on a new report', async () => {
    await openReady()

    expect(screen.queryByRole('button', { name: '다른 이름으로 저장' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '되돌리기' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '초기화' })).toBeVisible()
  })

  it('shows the unsaved mark as soon as the design differs from an empty one', async () => {
    const { user } = await openDesigner({ savedReports: SAVED_SAMPLES })
    expect(screen.queryByText(UNSAVED_MARK)).not.toBeInTheDocument()

    await addColumn(user, 'Deal code')

    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    expect(screen.getByText(UNSAVED_MARK)).toHaveAttribute('role', 'status')
  })
})

describe('저장 대화상자 (AC13, S7)', () => {
  it('opens with the title, the fields, the defaults and the guide', async () => {
    const { user } = await openReady()

    await user.click(saveButton())

    const dialog = await saveDialog()
    const name = within(dialog).getByRole('textbox', { name: '이름' })
    expect(name).toHaveValue('')
    expect(name).toBeRequired()
    expect(name).toHaveAttribute('maxlength', '100')
    expect(within(dialog).getByRole('textbox', { name: '설명' })).toHaveAttribute('maxlength', '1000')
    const visibility = within(dialog).getByRole('combobox', { name: '공개 범위' })
    expect(visibility).toHaveDisplayValue('모든 사용자에게 보임')
    expect(within(visibility).getAllByRole('option').map((o) => o.textContent)).toEqual(['모든 사용자에게 보임', '나만 보기'])
    expect(dialog).toHaveTextContent(GUIDE)
    expect(within(dialog).getByRole('button', { name: '저장' })).toBeEnabled()
  })

  it('validates the name and shows a duplicate name next to the field', async () => {
    const { user } = await openReady()
    await user.click(saveButton())
    const dialog = await saveDialog()

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(within(dialog).getByText('이름을 입력하세요')).toBeVisible()
    expect(mockControl.savedReportRequests()).toEqual([])

    await typeName(user, dialog, '   ')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(within(dialog).getByText('이름을 입력하세요')).toBeVisible()
    expect(mockControl.savedReportRequests()).toEqual([])

    await typeName(user, dialog, MINE_PUBLIC.name.toLowerCase())
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await within(dialog).findByText('같은 이름의 리포트가 이미 있습니다.')).toBeVisible()
    expect(within(dialog).queryByText('이름을 입력하세요')).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: '리포트 저장' })).toBeVisible()
    expect(mockControl.savedReportRequests().map((r) => r.op)).toEqual(['create'])
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
  })

  it('closes with the cancel button and sends nothing', async () => {
    const { user } = await openReady()
    await user.click(saveButton())

    await user.click(within(await saveDialog()).getByRole('button', { name: '취소' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests()).toEqual([])
  })

  it('closes the dialog and shows the violations in the designer when the server rejects the definition', async () => {
    const result = resultOf({ columns: [resultColumn({ field: 'action.count', label: 'Action 건수', type: 'number', valueType: 'integer' })], rows: [[3]] })
    const { user } = await openAndRun(result, 'Action 건수')
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '위반 리포트')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: '리포트 저장' })).not.toBeInTheDocument())
    expect((await screen.findAllByText(/이 컬럼은 그룹핑할 때만 쓸 수 있습니다/)).length).toBeGreaterThan(0)
    expect(mockControl.savedReportRequests().map((r) => r.op)).toEqual(['create'])
  })
})

describe('새 리포트 저장 (AC14, S8)', () => {
  it('saves a new report and moves to its editor without the unsaved mark', async () => {
    const { user, location } = await openReady()
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '  내가 만든 첫 리포트  ')
    await user.type(within(dialog).getByRole('textbox', { name: '설명' }), '설명입니다')
    await user.selectOptions(within(dialog).getByRole('combobox', { name: '공개 범위' }), '나만 보기')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(location()).toBe(CREATED))
    expect(await screen.findByRole('heading', { level: 1, name: '내가 만든 첫 리포트' })).toBeVisible()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByText(UNSAVED_MARK)).not.toBeInTheDocument()
    const requests = mockControl.savedReportRequests()
    expect(requests).toHaveLength(1)
    expect(requests[0]).toMatchObject({ op: 'create', id: null, body: { description: '설명입니다', visibility: 'private', definition: lastQuery() } })
    expect((requests[0]?.body as { name: string }).name.trim()).toBe('내가 만든 첫 리포트')
  })

  it('shows the editor buttons after the move and keeps the saved report editable', async () => {
    const { user, location } = await openReady()
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '편집으로 이동')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(location()).toBe(CREATED))

    expect(await screen.findByRole('button', { name: '다른 이름으로 저장' })).toBeVisible()
    expect(screen.getByRole('button', { name: '되돌리기' })).toBeVisible()
    expect(screen.queryByRole('button', { name: '초기화' })).not.toBeInTheDocument()
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()
  })
})

describe('user 역할 저장 (AC19, S9)', () => {
  it('user role can save a report', async () => {
    const { user, location } = await openReady('user')
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '조회 담당 리포트')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(location()).toBe(CREATED))
    expect(await screen.findByRole('heading', { level: 1, name: '조회 담당 리포트' })).toBeVisible()
    expect(mockControl.savedReportRequests()[0]).toMatchObject({ op: 'create', body: { name: '조회 담당 리포트', visibility: 'public' } })
  })

  it('rejects a name that another owner already uses and stays in the designer', async () => {
    const { user, location } = await openReady('user')
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, MINE_PUBLIC.name)

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await within(dialog).findByText('같은 이름의 리포트가 이미 있습니다.')).toBeVisible()
    expect(location()).toBe('/reports/new')
  })
})
