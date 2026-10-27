// 3단계 코드 리뷰(artifacts/final/review-report.md)의 프런트엔드 지적을 고정하는 편집 화면 테스트.
// 편집 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportEditPage'
import { act, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { keys } from '../../../data/queryKeys'
import { gateway } from '../../../gateway'
import { mockControl } from '../../../test/fake/default'
import { addCountedColumn, openEditor, runQuery, saveButton, saveDialog, setupReportClock, UNSAVED_MARK } from '../../../test/reportScreen'
import { MINE_PUBLIC, reportInput } from '../../../test/savedReports'

setupReportClock()

const COPY_NAME = `${MINE_PUBLIC.name} 복사본`
const dialogOf = async () => within(await saveDialog())
type Editor = Awaited<ReturnType<typeof openEditor>>

/** 다른 사용자가 먼저 저장한 상황을 같은 계정의 순차 호출로 만든다(현재 revision → +1). */
async function saveElsewhere(revision: number): Promise<void> {
  await gateway.reports.update(MINE_PUBLIC.id, { ...reportInput({ name: MINE_PUBLIC.name, description: MINE_PUBLIC.description }), revision })
}

/** 재연결 등으로 상세 쿼리가 다시 조회되는 상황. */
async function refetchDetail(client: Editor['client']): Promise<void> {
  await act(async () => {
    await client.invalidateQueries({ queryKey: keys.savedReport(MINE_PUBLIC.id) })
  })
}

async function changeAndRun(user: Editor['user'], label: string): Promise<void> {
  await addCountedColumn(user, label)
  await runQuery(user)
  await waitFor(() => expect(saveButton()).toBeEnabled())
}

describe('덮어쓰기 revision은 편집을 시작한 값을 따른다 (리뷰 Major 1)', () => {
  it('shows the conflict when the detail is fetched again after someone else saved', async () => {
    const { user, client } = await openEditor(MINE_PUBLIC.id)
    await changeAndRun(user, 'Deal code')
    await saveElsewhere(1)
    await refetchDetail(client)
    await user.click(saveButton())
    const dialog = await dialogOf()

    await user.click(dialog.getByRole('button', { name: '저장' }))

    expect(await dialog.findByRole('alert')).toHaveTextContent('다른 사용자가 먼저 이 리포트를 저장했습니다')
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'update')).toMatchObject([{ body: { revision: 1 } }, { body: { revision: 1 } }])
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 2 })
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
  })

  it('keeps the dialog defaults from the loaded report after the detail is fetched again', async () => {
    const { user, client } = await openEditor(MINE_PUBLIC.id)
    await changeAndRun(user, 'Deal code')
    await gateway.reports.update(MINE_PUBLIC.id, { ...reportInput({ name: '남이 바꾼 이름' }), revision: 1 })
    await refetchDetail(client)

    await user.click(saveButton())

    expect((await dialogOf()).getByRole('textbox', { name: '이름' })).toHaveValue(MINE_PUBLIC.name)
  })

  it('uses the revision of the own overwrite for the next save even when the detail is fetched again in between', async () => {
    const { user, client } = await openEditor(MINE_PUBLIC.id)
    await changeAndRun(user, 'Deal code')
    await user.click(saveButton())
    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await refetchDetail(client)
    await changeAndRun(user, 'Deal 이름')

    await user.click(saveButton())
    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(mockControl.savedReportRequests().map((r) => (r.body as { revision: number }).revision)).toEqual([1, 2])
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 3 })
    expect(screen.queryByText(UNSAVED_MARK)).not.toBeInTheDocument()
  })

  it('shows the conflict for the save after the own overwrite when someone else saved and the detail was fetched again', async () => {
    const { user, client } = await openEditor(MINE_PUBLIC.id)
    await changeAndRun(user, 'Deal code')
    await user.click(saveButton())
    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await saveElsewhere(2)
    await refetchDetail(client)
    await changeAndRun(user, 'Deal 이름')
    await user.click(saveButton())
    const dialog = await dialogOf()

    await user.click(dialog.getByRole('button', { name: '저장' }))

    expect(await dialog.findByRole('alert')).toHaveTextContent('다른 사용자가 먼저 이 리포트를 저장했습니다')
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 3 })
  })
})

describe('다른 이름으로 저장은 지난 결과를 새 설계의 결과로 넘기지 않는다 (리뷰 Major 2)', () => {
  const headers = () => within(screen.getByRole('table', { name: '조회 결과' })).getAllByRole('columnheader')

  it('runs again in the new editor when the design changed after the last run', async () => {
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    expect(mockControl.reportQueries()).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))
    const dialog = await dialogOf()

    await user.click(dialog.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    await waitFor(() => expect(mockControl.reportQueries()).toHaveLength(2))
    expect(mockControl.reportQueries()[1]?.columns).toHaveLength(3)
    await waitFor(() => expect(headers()).toHaveLength(3))
    expect(screen.queryByText(UNSAVED_MARK)).not.toBeInTheDocument()
  })

  it('hands the result over without running again when it was run for the current design', async () => {
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await changeAndRun(user, 'Deal code')
    expect(mockControl.reportQueries()).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))

    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    expect(await screen.findByRole('heading', { level: 1, name: COPY_NAME })).toBeVisible()
    expect(headers()).toHaveLength(3)
    expect(mockControl.reportQueries()).toHaveLength(2)
  })
})

describe('다른 이름으로 저장의 입력 문제 (리뷰 Minor)', () => {
  it('tells the user about an input problem of the design instead of ending silently', async () => {
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    const amount = screen.getByDisplayValue(/^1,?500$/)
    await user.clear(amount)
    await user.type(amount, 'abc')
    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))

    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))

    expect((await screen.findAllByText(/천원 단위 정수로 입력하세요/)).length).toBeGreaterThan(0)
    expect(location()).toBe(`/reports/${MINE_PUBLIC.id}/edit`)
    expect(mockControl.savedReportRequests()).toEqual([])
  })
})

describe('변경이 없을 때의 되돌리기 (리뷰 Nit, 계획 4.8: 변경이 있을 때만 확인 후 되돌림)', () => {
  it('does nothing without changes and keeps the result and the save button', async () => {
    const { user } = await openEditor(MINE_PUBLIC.id)
    await waitFor(() => expect(saveButton()).toBeEnabled())

    await user.click(screen.getByRole('button', { name: '되돌리기' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(saveButton()).toBeEnabled()
    expect(mockControl.reportQueries()).toHaveLength(1)
  })
})
