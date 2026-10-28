// 보기 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportViewPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import type { ReportLayout } from '../../../shared/model/reportTypes'
import { mockControl } from '../../../test/fake/default'
import { forbidden, invalidReport, notFound } from '../../../test/fake/errors'
import {
  arrangement,
  chooseView,
  dragOverTile,
  dragTile,
  dropOnTile,
  EDGE_POINT,
  endDrag,
  moveByKey,
  startDrag,
  tileOrder,
  viewRadio,
} from '../../../test/reportLayout'
import { openView, saveDialog, setupReportClock, typeName } from '../../../test/reportScreen'
import { PARK, SAVED_SAMPLES, VENDOR_CHART, savedReport } from '../../../test/savedReports'

setupReportClock()

/** 보기 화면 배치 자동 저장(개정 1 AC22~AC22e): 바꿀 때마다 `PUT .../layout`, 요청 중에는 한 개씩. */

const SIDE: ReportLayout = { view: 'both', order: ['chart', 'table'], arrange: 'side_by_side' }
const OTHERS: ReportLayout = { view: 'both', order: ['table', 'chart'], arrange: 'stacked' }
/** 박영업이 만든 공개 리포트(차트·배치 있음). 김영업(sales)이 열어 고친다. */
const REPORT = savedReport({ id: 41, name: '박영업 배치 리포트', owner: PARK, updatedBy: PARK, chart: VENDOR_CHART, layout: SIDE })
const SAVING = '배치 저장 중…'
const SAVED = '배치를 저장했습니다'
const CONFLICT = '다른 사람이 이 리포트를 먼저 수정해 최신 내용을 다시 불러왔습니다. 내가 바꾼 배치는 저장되지 않았습니다. 필요하면 배치를 다시 바꾸세요.'
const FORBIDDEN = '이 리포트를 수정할 권한이 없어 배치를 저장하지 못했습니다. 바꾼 배치는 이 화면에서만 유지됩니다.'
const NOT_FOUND = '리포트를 찾을 수 없어 배치를 저장하지 못했습니다. 목록에서 다시 확인하세요.'
const FAILED = '배치를 저장하지 못했습니다. 잠시 뒤 다시 시도하세요.'
const BUSY_TITLE = '배치를 저장하는 중입니다'
const READ_ONLY_NOTE = '보기 방식과 배치는 이 화면에서만 바뀌고 저장되지 않습니다'

const layoutRequests = () => mockControl.savedReportRequests().filter((r) => r.op === 'layout')
const bodies = () => layoutRequests().map((r) => r.body as { layout: ReportLayout; revision: number })
const runCount = () => mockControl.savedReportRequests().filter((r) => r.op === 'run').length
const editControl = (): HTMLElement | null => screen.queryByRole('link', { name: '편집' }) ?? screen.queryByRole('button', { name: '편집' })

async function open() {
  const rendered = await openView(REPORT.id, { savedReports: [...SAVED_SAMPLES, REPORT] })
  await screen.findByRole('table', { name: '조회 결과' })
  return rendered
}

/** 배치 저장 요청을 붙잡아 두는 관문. release()가 가장 오래된 요청의 응답을 풀어 준다. */
function holdSaves() {
  const waiting: (() => void)[] = []
  mockControl.setLayoutSaveGate(() => new Promise<void>((resolve) => waiting.push(resolve)))
  return {
    /** 가장 오래된 요청이 관문에 닿을 때까지 기다린 뒤 풀어 준다. */
    release: async (): Promise<void> => {
      await waitFor(() => expect(waiting.length).toBeGreaterThan(0))
      waiting.shift()?.()
    },
    pending: () => waiting.length,
  }
}

/** n번째(1부터) 배치 저장 요청만 이 오류로 실패시킨다. */
function failAttempt(attempt: number, error: () => Error): void {
  mockControl.setLayoutSaveGate((call) => {
    if (call.attempt === attempt) throw error()
  })
}

const status = () => screen.getByRole('status')

describe('저장된 배치로 열기 (AC11, AC16, AC21)', () => {
  it('opens with the saved view, order and arrangement and sends nothing', async () => {
    await open()

    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
    expect(viewRadio('표+차트')).toBeChecked()
    expect(layoutRequests()).toEqual([])
  })

  it('opens the chart-only layout with only the chart tile', async () => {
    const chartOnly = savedReport({ id: 42, name: '차트만', owner: PARK, chart: VENDOR_CHART, layout: { view: 'chart', order: ['chart', 'table'], arrange: 'stacked' } })
    await openView(chartOnly.id, { savedReports: [...SAVED_SAMPLES, chartOnly] })

    expect(await screen.findByRole('region', { name: '차트 타일' })).toBeVisible()
    expect(viewRadio('차트만')).toBeChecked()
    expect(screen.queryByRole('region', { name: '표 타일' })).not.toBeInTheDocument()
  })

  it('has neither tabs nor the chart settings button, and no save button', async () => {
    await open()

    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '차트 설정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '차트 만들기' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '저장' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '차트 삭제' })).not.toBeInTheDocument()
  })

  it('disables the chart views and shows only the table when the report has no stored chart, leaving the stored layout alone', async () => {
    const stored = savedReport({ id: 43, name: '차트 없음', owner: PARK, layout: SIDE })
    await openView(stored.id, { savedReports: [...SAVED_SAMPLES, stored] })
    await screen.findByRole('table', { name: '조회 결과' })

    expect(viewRadio('표+차트')).toBeDisabled()
    expect(viewRadio('차트만')).toBeDisabled()
    expect(viewRadio('표+차트')).toHaveAttribute('title', '저장된 차트가 없습니다')
    expect(viewRadio('차트만')).toHaveAttribute('title', '저장된 차트가 없습니다')
    expect(viewRadio('표만')).toBeEnabled()
    expect(screen.queryByRole('region', { name: '차트 타일' })).not.toBeInTheDocument()
    expect(tileOrder()).toEqual(['표'])
    expect(layoutRequests()).toEqual([])
    expect(await gateway.reports.get(stored.id)).toMatchObject({ layout: SIDE })
  })

  it('shows the chart problem above the result area and treats the report as chartless', async () => {
    const PROBLEM = '저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요.'
    const broken = savedReport({ id: 44, name: '깨진 차트', owner: PARK, chartProblem: PROBLEM, layout: SIDE })
    await openView(broken.id, { savedReports: [...SAVED_SAMPLES, broken] })
    await screen.findByRole('table', { name: '조회 결과' })

    const message = screen.getByText(PROBLEM)

    expect(message).toBeVisible()
    expect(message.compareDocumentPosition(screen.getByRole('table', { name: '조회 결과' })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(viewRadio('차트만')).toBeDisabled()
  })

  it('shows the viewer-only note nowhere for someone who can edit', async () => {
    await open()

    expect(screen.queryByText(READ_ONLY_NOTE)).not.toBeInTheDocument()
  })
})

describe('바꿀 때마다 저장 (AC22, AC22b)', () => {
  it('saves a view choice at once with the revision it was opened with', async () => {
    const { user } = await open()

    await chooseView(user, '표만')

    await waitFor(() => expect(layoutRequests()).toHaveLength(1))
    expect(layoutRequests()[0]).toMatchObject({ op: 'layout', id: REPORT.id, body: { layout: { view: 'table', order: ['chart', 'table'], arrange: 'side_by_side' }, revision: 1 } })
    expect(await gateway.reports.get(REPORT.id)).toMatchObject({ revision: 2, layout: { view: 'table', order: ['chart', 'table'], arrange: 'side_by_side' } })
  })

  it('shows the saving state while the request runs and the saved state after it', async () => {
    const { user } = await open()
    const gate = holdSaves()

    await chooseView(user, '표만')

    expect(await screen.findByText(SAVING)).toBeVisible()
    expect(status()).toHaveTextContent(SAVING)
    expect(status()).toHaveAttribute('aria-live', 'polite')
    await gate.release()
    expect(await screen.findByText(SAVED)).toBeVisible()
    expect(status()).toHaveTextContent(SAVED)
    expect(screen.queryByText(SAVING)).not.toBeInTheDocument()
  })

  it('saves a drop once, only when the tile is dropped and not while it is dragged over', async () => {
    await open()
    const transfer = startDrag('표')

    dragOverTile(transfer, '차트', EDGE_POINT.bottom)
    dragOverTile(transfer, '차트', EDGE_POINT.left)
    expect(layoutRequests()).toHaveLength(0)
    dropOnTile(transfer, '차트', EDGE_POINT.bottom)
    endDrag(transfer, '표')

    await waitFor(() => expect(layoutRequests()).toHaveLength(1))
    expect(bodies()[0]).toEqual({ layout: { view: 'both', order: ['chart', 'table'], arrange: 'stacked' }, revision: 1 })
  })

  it('saves a keyboard move like a drop', async () => {
    const { user } = await open()

    await moveByKey(user, '표', 'ArrowLeft')

    await waitFor(() => expect(layoutRequests()).toHaveLength(1))
    expect(bodies()[0]?.layout).toEqual({ view: 'both', order: ['table', 'chart'], arrange: 'side_by_side' })
  })

  it('does not send a request when the choice does not change the layout', async () => {
    const { user } = await open()

    await chooseView(user, '표+차트') // 이미 고른 보기
    dragTile('표', '표', 'right') // 자기 자신 위에 놓기

    expect(layoutRequests()).toEqual([])
    expect(screen.queryByText(SAVING)).not.toBeInTheDocument()
  })

  it('does not send a request for choosing the view that is already saved', async () => {
    const { user } = await open()
    await chooseView(user, '표만')
    await screen.findByText(SAVED)

    await chooseView(user, '표만') // 이미 저장된 보기를 다시 고름

    expect(layoutRequests()).toHaveLength(1)
  })

  it('takes the editor and the time of the head from the response', async () => {
    const { user } = await open()
    expect(screen.getByText(/박영업 · /)).not.toHaveTextContent('수정:')

    await chooseView(user, '표만')

    expect(await screen.findByText(/\(수정: 김영업\)/)).toBeVisible()
    expect(await gateway.reports.get(REPORT.id)).toMatchObject({ updatedBy: { name: '김영업' }, revision: 2 })
  })

  it('removes the saved mark with the next change', async () => {
    const { user } = await open()
    const gate = holdSaves()
    await chooseView(user, '표만')
    await gate.release()
    await screen.findByText(SAVED)

    await chooseView(user, '차트만')

    expect(screen.queryByText(SAVED)).not.toBeInTheDocument()
    expect(await screen.findByText(SAVING)).toBeVisible()
    await gate.release()
    expect(await screen.findByText(SAVED)).toBeVisible()
  })
})

describe('연속 변경은 한 번에 하나씩 (AC22a)', () => {
  it('sends two requests for three changes during the first request: the second carries the last value and the new revision', async () => {
    const { user } = await open()
    const gate = holdSaves()

    await chooseView(user, '표만') // 요청 1
    await screen.findByText(SAVING)
    await chooseView(user, '차트만') // 대기 값(중간 값은 버려진다)
    await chooseView(user, '표+차트')
    dragTile('표', '차트', 'bottom') // 마지막 값: 표+차트, 차트 → 표, 두 줄

    expect(layoutRequests()).toHaveLength(1)
    await gate.release()
    await waitFor(() => expect(layoutRequests()).toHaveLength(2))
    expect(bodies()[1]).toEqual({ layout: { view: 'both', order: ['chart', 'table'], arrange: 'stacked' }, revision: 2 })
    expect(bodies()[0]?.layout.view).toBe('table')
    await gate.release()
    expect(await screen.findByText(SAVED)).toBeVisible()
    expect(layoutRequests()).toHaveLength(2)
    expect(await gateway.reports.get(REPORT.id)).toMatchObject({ revision: 3, layout: { view: 'both', order: ['chart', 'table'], arrange: 'stacked' } })
  })

  it('never has more than one request in flight', async () => {
    const { user } = await open()
    const gate = holdSaves()

    await chooseView(user, '표만')
    await screen.findByText(SAVING)
    await chooseView(user, '차트만')
    await chooseView(user, '표+차트')
    dragTile('표', '차트', 'bottom')

    await waitFor(() => expect(gate.pending()).toBe(1))
    expect(layoutRequests()).toHaveLength(1)
  })

  it('sends nothing more when the waiting value equals what the first response saved', async () => {
    const { user } = await open()
    const gate = holdSaves()

    await chooseView(user, '표만') // 요청 1: 표만
    await screen.findByText(SAVING)
    await chooseView(user, '차트만') // 대기 값
    await chooseView(user, '표만') // 대기 값이 요청 1과 같아진다

    await gate.release()
    expect(await screen.findByText(SAVED)).toBeVisible()
    expect(layoutRequests()).toHaveLength(1)
    expect(viewRadio('표만')).toBeChecked()
  })

  it('keeps the screen layout on the waiting value when the first response arrives', async () => {
    const { user } = await open()
    const gate = holdSaves()
    await chooseView(user, '표만')
    await screen.findByText(SAVING)
    await chooseView(user, '차트만')

    await gate.release()
    await waitFor(() => expect(layoutRequests()).toHaveLength(2))

    expect(viewRadio('차트만')).toBeChecked()
    expect(screen.queryByRole('region', { name: '표 타일' })).not.toBeInTheDocument()
    await gate.release()
    await screen.findByText(SAVED)
    expect(viewRadio('차트만')).toBeChecked()
  })
})

describe('편집·복제 단추 (AC21, AC22e)', () => {
  it('disables edit and copy while saving and enables them again afterwards, leaving the refresh button alone', async () => {
    const { user } = await open()
    const gate = holdSaves()

    await chooseView(user, '표만')
    await screen.findByText(SAVING)

    expect(screen.getByRole('button', { name: '복제' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '복제' })).toHaveAttribute('title', BUSY_TITLE)
    const edit = editControl() as HTMLElement
    expect(edit).toHaveAttribute('aria-disabled', 'true')
    expect(edit).toHaveAttribute('title', BUSY_TITLE)
    expect(screen.getByRole('button', { name: '다시 조회' })).toBeEnabled()

    await gate.release()
    await screen.findByText(SAVED)

    expect(screen.getByRole('button', { name: '복제' })).toBeEnabled()
    expect(editControl()).not.toHaveAttribute('aria-disabled', 'true')
  })

  it('does not follow the edit link while saving', async () => {
    const { user, location } = await open()
    holdSaves()
    await chooseView(user, '표만')
    await screen.findByText(SAVING)

    await user.click(editControl() as HTMLElement)

    expect(location()).toBe(`/reports/${REPORT.id}`)
  })

  it('stays disabled while a waiting value remains', async () => {
    const { user } = await open()
    const gate = holdSaves()
    await chooseView(user, '표만')
    await screen.findByText(SAVING)
    await chooseView(user, '차트만')
    await gate.release()
    await waitFor(() => expect(layoutRequests()).toHaveLength(2))

    expect(screen.getByRole('button', { name: '복제' })).toBeDisabled()
    await gate.release()
    await screen.findByText(SAVED)
    expect(screen.getByRole('button', { name: '복제' })).toBeEnabled()
  })

  it('copies the saved layout and sends no layout in the copy request', async () => {
    const { user, location } = await open()
    await chooseView(user, '표만')
    await screen.findByText(SAVED)

    await user.click(screen.getByRole('button', { name: '복제' }))
    const dialog = await saveDialog()
    await typeName(user, dialog, '배치 복제본')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(location()).toMatch(/^\/reports\/\d+\/edit$/))
    const [copy] = mockControl.savedReportRequests().filter((r) => r.op === 'copy')
    expect(copy?.body).not.toHaveProperty('layout')
    const copied = (await gateway.reports.list()).find((r) => r.name === '배치 복제본')
    expect(copied).toBeDefined()
    expect(await gateway.reports.get(copied?.id as number)).toMatchObject({ layout: { view: 'table', order: ['chart', 'table'], arrange: 'side_by_side' } })
  })
})

describe('409: 그 사이 다른 사람이 저장함 (AC22c)', () => {
  it('stops without retrying, reloads the latest saved layout and runs again, and tells why', async () => {
    const { user } = await open()
    mockControl.touchSavedReport(REPORT.id, { layout: OTHERS })
    const runsBefore = runCount()

    await chooseView(user, '표만')

    expect(await screen.findByRole('alert')).toHaveTextContent(CONFLICT)
    expect(layoutRequests()).toHaveLength(1)
    await waitFor(() => expect(tileOrder()).toEqual(['표', '차트']))
    expect(arrangement()).toBe('stacked')
    expect(viewRadio('표+차트')).toBeChecked()
    await waitFor(() => expect(runCount()).toBe(runsBefore + 1))
    expect(layoutRequests()).toHaveLength(1) // 재시도 없음
  })

  it('drops the waiting value and shows the latest saved layout instead of it', async () => {
    const { user } = await open()
    const gate = holdSaves()
    await chooseView(user, '표만')
    await screen.findByText(SAVING)
    await chooseView(user, '차트만') // 대기 값
    mockControl.touchSavedReport(REPORT.id, { layout: OTHERS })

    await gate.release()

    expect(await screen.findByRole('alert')).toHaveTextContent(CONFLICT)
    await waitFor(() => expect(tileOrder()).toEqual(['표', '차트']))
    expect(layoutRequests()).toHaveLength(1)
    expect(viewRadio('표+차트')).toBeChecked()
  })

  it('does not send a change made while the latest report is still being read, and saves later changes with the new revision', async () => {
    const { user } = await open()
    const original = gateway.reports.get.bind(gateway.reports)
    let release: () => void = () => undefined
    const held = new Promise<void>((resolve) => (release = resolve))
    vi.spyOn(gateway.reports, 'get').mockImplementation(async (id: number) => {
      await held
      return original(id)
    })
    mockControl.touchSavedReport(REPORT.id, { layout: OTHERS })

    await chooseView(user, '표만') // 409 -> 다시 읽기 시작(응답은 붙잡아 둔다)
    expect(await screen.findByRole('alert')).toHaveTextContent(CONFLICT)
    await chooseView(user, '차트만') // 다시 읽는 중의 변경: 낡은 revision으로 보내면 안 된다
    expect(layoutRequests()).toHaveLength(1)

    release()
    await waitFor(() => expect(tileOrder()).toEqual(['표', '차트']))
    expect(viewRadio('표+차트')).toBeChecked() // 최신 저장 값, 그 변경은 버려졌다
    expect(layoutRequests()).toHaveLength(1)
    await chooseView(user, '표만')
    await waitFor(() => expect(layoutRequests()).toHaveLength(2))
    expect(bodies()[1]?.revision).toBe(2)
  })

  it('saves again with the new revision once the user changes the layout after the reload', async () => {
    const { user } = await open()
    mockControl.touchSavedReport(REPORT.id, { layout: OTHERS })
    await chooseView(user, '표만')
    await screen.findByRole('alert')
    await waitFor(() => expect(tileOrder()).toEqual(['표', '차트']))

    await chooseView(user, '표만')

    await waitFor(() => expect(layoutRequests()).toHaveLength(2))
    expect(bodies()[1]).toEqual({ layout: { view: 'table', order: ['table', 'chart'], arrange: 'stacked' }, revision: 2 })
    expect(await screen.findByText(SAVED)).toBeVisible()
    expect(screen.queryByText(CONFLICT)).not.toBeInTheDocument()
  })
})

describe('그 밖의 실패 (AC22d)', () => {
  it('stops on 403, keeps the changed layout on the screen and sends no more requests', async () => {
    const { user } = await open()
    failAttempt(1, () => forbidden('권한 없음'))

    await chooseView(user, '표만')

    expect(await screen.findByRole('alert')).toHaveTextContent(FORBIDDEN)
    expect(viewRadio('표만')).toBeChecked()
    await chooseView(user, '표+차트')
    dragTile('표', '차트', 'bottom')
    expect(viewRadio('표+차트')).toBeChecked()
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('stacked')
    expect(layoutRequests()).toHaveLength(1)
  })

  it('stops on 404 with a link to the list and sends no more requests', async () => {
    const { user } = await open()
    failAttempt(1, () => notFound('없음'))

    await chooseView(user, '표만')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(NOT_FOUND)
    expect(within(alert).getByRole('link')).toHaveAttribute('href', '/reports')
    await chooseView(user, '차트만')
    expect(layoutRequests()).toHaveLength(1)
    expect(viewRadio('차트만')).toBeChecked()
  })

  it.each([
    ['a server error', () => new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 내부 오류입니다' })],
    ['a network error', () => new ApiError(0, { type: 'https://x/problems/network', title: 'Network Error', status: 0, detail: '서버에 연결할 수 없습니다.' })],
    ['a layout violation', () => invalidReport([{ location: ['layout', 'view'], code: 'invalid-value', message: '보기 방식 오류' }])],
  ])('keeps the screen layout on %s and offers the retry button', async (_name, error) => {
    const { user } = await open()
    failAttempt(1, error)

    await chooseView(user, '표만')

    expect(await screen.findByRole('alert')).toHaveTextContent(FAILED)
    expect(screen.getByRole('button', { name: '다시 시도' })).toBeEnabled()
    expect(viewRadio('표만')).toBeChecked()
    expect(layoutRequests()).toHaveLength(1)
  })

  it('retries the last screen value with the last confirmed revision and clears the failure', async () => {
    const { user } = await open()
    failAttempt(1, () => new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 내부 오류입니다' }))
    await chooseView(user, '표만')
    await screen.findByRole('alert')

    await user.click(screen.getByRole('button', { name: '다시 시도' }))

    await waitFor(() => expect(layoutRequests()).toHaveLength(2))
    expect(bodies()[1]).toEqual({ layout: { view: 'table', order: ['chart', 'table'], arrange: 'side_by_side' }, revision: 1 })
    expect(await screen.findByText(SAVED)).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '다시 시도' })).not.toBeInTheDocument()
  })

  it('saves the next change after a failure with the last confirmed revision, without any automatic retry', async () => {
    const { user } = await open()
    failAttempt(1, () => new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 내부 오류입니다' }))
    await chooseView(user, '표만')
    await screen.findByRole('alert')
    expect(layoutRequests()).toHaveLength(1)

    await chooseView(user, '차트만')

    await waitFor(() => expect(layoutRequests()).toHaveLength(2))
    expect(bodies()[1]).toEqual({ layout: { view: 'chart', order: ['chart', 'table'], arrange: 'side_by_side' }, revision: 1 })
    expect(await screen.findByText(SAVED)).toBeVisible()
  })

  it('ends in the failed state when the waiting value fails to save, with no more requests and the buttons enabled again', async () => {
    const { user } = await open()
    const gate = holdSaves()
    await chooseView(user, '표만')
    await screen.findByText(SAVING)
    await chooseView(user, '차트만') // 대기 값
    mockControl.setLayoutSaveGate(() => {
      throw new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 내부 오류입니다' })
    })
    await gate.release()
    await waitFor(() => expect(layoutRequests()).toHaveLength(2)) // 요청 1이 끝나면 대기 값이 요청 2로 나간다
    await screen.findByRole('alert')

    expect(layoutRequests()).toHaveLength(2) // 실패 뒤 더 나가지 않는다
    expect(screen.getByRole('button', { name: '복제' })).toBeEnabled()
  })
})
