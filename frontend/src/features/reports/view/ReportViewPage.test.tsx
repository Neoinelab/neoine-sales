// 보기 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportViewPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockControl } from '../../../test/fake/default'
import { REPORT_TIMEOUT_MESSAGE, reportTimeout } from '../../../test/fake/errors'
import { renderAt } from '../../../test/mockApp'
import { openList, openView, saveDialog, setupReportClock, typeName } from '../../../test/reportScreen'
import { BROKEN_DEFINITION, MINE_PRIVATE, MINE_PUBLIC, OLD_PUBLIC, PARK_PRIVATE, PARK_PUBLIC, SAVED_SAMPLES, savedReport } from '../../../test/savedReports'

setupReportClock()

const NOT_FOUND_TEXT = '리포트를 찾을 수 없습니다. 삭제되었거나 볼 권한이 없습니다.'
const heading = (name: string) => screen.findByRole('heading', { level: 1, name })
/** "편집": 편집 화면으로 가는 링크(링크 모양 버튼이면 버튼). 없으면 null. */
const editControl = (): HTMLElement | null => screen.queryByRole('link', { name: '편집' }) ?? screen.queryByRole('button', { name: '편집' })
const resultReady = () => screen.findByRole('table', { name: '조회 결과' })

describe('보기 화면 앞 N자 (AC19)', () => {
  it('cuts the data cells of a column saved with a prefix length and keeps the whole value in the title', async () => {
    const prefixed = savedReport({
      id: 16,
      name: '앞 N자 리포트',
      definition: { columns: [{ field: 'deal.name', prefixLength: 4, group: false }], conditions: [], combine: 'and', rowLimit: 100 },
    })
    await openView(prefixed.id, { savedReports: [...SAVED_SAMPLES, prefixed] })

    const table = await resultReady()
    const [cell] = within(table).getAllByRole('cell')

    expect(cell).toHaveTextContent('Deal…')
    expect(cell).toHaveAttribute('title', 'Deal 이름 1')
  })
})

describe('보기 화면 (AC16, S16)', () => {
  it('runs the saved report and shows meta result and sql', async () => {
    await openView(MINE_PUBLIC.id)

    expect(await heading(MINE_PUBLIC.name)).toBeVisible()
    expect(screen.getByText(MINE_PUBLIC.description)).toBeVisible()
    expect(screen.queryByText('비공개')).not.toBeInTheDocument()
    const meta = screen.getByText(/2026-10-24 17:20/)
    expect(meta).toHaveTextContent('김영업')
    expect(meta).not.toHaveTextContent('수정:')
    const table = await resultReady()
    expect(within(table).getByRole('columnheader', { name: 'Vendor' })).toBeVisible()
    expect(within(table).getByRole('columnheader', { name: /^금액 합계\s?\(천원\)$/ })).toBeVisible()
    expect(screen.getByText('생성 SQL 보기(읽기 전용)')).toBeVisible()
    expect(screen.getByText('SELECT … /* fake */')).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests()).toEqual([{ op: 'run', id: 11 }])
    expect(mockControl.reportQueries()).toEqual([])
  })

  it('shows the private tag, the editor name and the resigned owner', async () => {
    await openView(PARK_PUBLIC.id)
    expect(await heading(PARK_PUBLIC.name)).toBeVisible()
    const meta = screen.getByText(/2026-10-25 09:00/)
    expect(meta).toHaveTextContent('박영업')
    expect(meta).toHaveTextContent('수정: 김영업')
  })

  it('tags a private report', async () => {
    await openView(MINE_PRIVATE.id)

    expect(await heading(MINE_PRIVATE.name)).toBeVisible()
    expect(screen.getByText('비공개')).toBeVisible()
  })

  it('names a resigned owner with the resigned mark', async () => {
    await openView(OLD_PUBLIC.id)

    expect(await heading(OLD_PUBLIC.name)).toBeVisible()
    expect(screen.getByText(/2026-10-22 09:00/)).toHaveTextContent('강퇴사(퇴사)')
  })

  it('lets an admin open the private report of someone else', async () => {
    await openView(PARK_PRIVATE.id, { role: 'admin' })

    expect(await heading(PARK_PRIVATE.name)).toBeVisible()
    expect(screen.getByText('비공개')).toBeVisible()
    await resultReady()
  })

  it('runs again with the refresh button', async () => {
    const { user } = await openView(MINE_PUBLIC.id)
    await resultReady()

    await user.click(screen.getByRole('button', { name: '다시 조회' }))

    await waitFor(() => expect(mockControl.savedReportRequests().filter((r) => r.op === 'run')).toHaveLength(2))
  })

  it('shows the Action columns of a report that uses them', async () => {
    await openView(PARK_PUBLIC.id)

    const table = await resultReady()

    expect(within(table).getByRole('columnheader', { name: 'Deal code' })).toBeVisible()
    expect(within(table).getByRole('columnheader', { name: '진행사항' })).toBeVisible()
  })
})

describe('보기 화면의 단추 (AC16, AC17, S17)', () => {
  it.each([
    ['sales', MINE_PUBLIC.id, true, true],
    ['sales', PARK_PUBLIC.id, true, false],
    ['user', MINE_PUBLIC.id, true, false],
    ['admin', PARK_PUBLIC.id, true, true],
    ['admin', PARK_PRIVATE.id, true, true],
  ] as const)('%s on report %s: edit %s, delete %s', async (role, id, edit, remove) => {
    await openView(id, { role })
    await resultReady()

    expect(screen.getByRole('button', { name: '다시 조회' })).toBeVisible()
    expect(screen.getByRole('button', { name: '복제' })).toBeVisible()
    expect(editControl() !== null).toBe(edit)
    expect(screen.queryByRole('button', { name: '삭제' }) !== null).toBe(remove)
    if (edit && editControl()?.tagName === 'A') expect(editControl()).toHaveAttribute('href', `/reports/${id}/edit`)
  })

  it('shows buttons by permission and deletes to the list', async () => {
    const { user, location } = await openView(MINE_PUBLIC.id)
    await resultReady()

    await user.click(screen.getByRole('button', { name: '삭제' }))
    const dialog = await screen.findByRole('dialog', { name: '리포트 삭제' })
    expect(dialog).toHaveTextContent(`‘${MINE_PUBLIC.name}’ 리포트를 삭제할까요? 되돌릴 수 없습니다.`)
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(location()).toBe('/reports'))
    expect(await screen.findByRole('table', { name: '리포트 목록' })).toBeVisible()
    expect(screen.queryByRole('link', { name: MINE_PUBLIC.name })).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'remove')).toEqual([{ op: 'remove', id: 11 }])
  })

  it('stays on the report when the delete is cancelled', async () => {
    const { user, location } = await openView(MINE_PUBLIC.id)
    await resultReady()
    await user.click(screen.getByRole('button', { name: '삭제' }))

    await user.click(within(await screen.findByRole('dialog', { name: '리포트 삭제' })).getByRole('button', { name: '취소' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(location()).toBe('/reports/11')
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'remove')).toEqual([])
  })

  it('copies from the view page and opens the copy in the editor', async () => {
    const { user, location } = await openView(PARK_PUBLIC.id)
    await resultReady()
    await user.click(screen.getByRole('button', { name: '복제' }))
    const dialog = await saveDialog()
    expect(within(dialog).getByRole('textbox', { name: '이름' })).toHaveValue(`${PARK_PUBLIC.name} 복사본`)
    await typeName(user, dialog, '내 복제본')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'copy')).toMatchObject([{ id: 13, body: { name: '내 복제본', visibility: 'public' } }])
  })

  it('shows the server violation inside the copy dialog when the stored definition no longer fits the catalog', async () => {
    const { user, location } = await renderAt('/reports/20', { savedReports: [savedReport({ id: 20, name: '깨진 정의', definition: BROKEN_DEFINITION })] })
    await screen.findByText(/저장된 설계가 지금 규칙과 맞지 않습니다/)
    await user.click(screen.getByRole('button', { name: '복제' }))
    const dialog = await saveDialog()

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(/허용되지 않은 필드입니다: deal\.nope/)
    expect(screen.getByRole('dialog', { name: '리포트 저장' })).toBeVisible()
    expect(location()).toBe('/reports/20')
  })

  it('goes to the editor from the edit link', async () => {
    const { user, location } = await openView(MINE_PUBLIC.id)
    await resultReady()

    await user.click(editControl() as HTMLElement)

    expect(location()).toBe('/reports/11/edit')
  })
})

describe('보기 화면의 실패 (AC16, S18)', () => {
  it('shows a stored definition problem and a not found page', async () => {
    await renderAt('/reports/20', { savedReports: [savedReport({ id: 20, name: '깨진 정의', definition: BROKEN_DEFINITION })] })

    expect(await heading('깨진 정의')).toBeVisible()
    expect(await screen.findByText(/저장된 설계가 지금 규칙과 맞지 않습니다\. 편집에서 고치세요/)).toBeVisible()
    expect(screen.getByText(/허용되지 않은 필드입니다: deal\.nope/)).toBeVisible()
    expect(editControl()).not.toBeNull()
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()
  })

  it('shows the not found guide for a hidden report and links back to the list', async () => {
    const { user, location } = await openView(PARK_PRIVATE.id)

    expect(await screen.findByText(NOT_FOUND_TEXT)).toBeVisible()
    expect(screen.queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'run')).toHaveLength(0)

    await user.click(screen.getByRole('link', { name: '리포트 목록' }))

    expect(location()).toBe('/reports')
  })

  it.each(['abc', '0', '9007199254740991'])('shows the not found guide for the id %s', async (id) => {
    await renderAt(`/reports/${id}`, { savedReports: SAVED_SAMPLES })

    expect(await screen.findByText(NOT_FOUND_TEXT)).toBeVisible()
  })

  it('shows the timeout message and lets the user run again', async () => {
    const { user } = await openList()
    mockControl.setReportQueryHandler(() => {
      throw reportTimeout()
    })

    await user.click(screen.getByRole('link', { name: MINE_PUBLIC.name }))

    expect(await screen.findByText(REPORT_TIMEOUT_MESSAGE)).toBeVisible()
    expect(screen.getByRole('button', { name: '다시 조회' })).toBeEnabled()
  })
})
