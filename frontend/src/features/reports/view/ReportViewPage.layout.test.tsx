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

/** 보기 화면 배치 자동 저장: 바꿀 때마다 `PUT .../layout`, 요청 중에는 한 개씩. */

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

describe('저장된 배치로 열기', () => {
  // 테스트 코드: RS-093
  it('저장된 보기 방식·순서·배치로 열고 아무것도 보내지 않는다', async () => {
    // when: 차트와 배치(차트 → 표, 한 줄)가 저장된 리포트의 보기 화면을 연다
    await open()

    // then: 저장된 순서와 한 줄 배치, 표+차트 선택으로 열리고 배치 저장 요청이 없다
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
    expect(viewRadio('표+차트')).toBeChecked()
    expect(layoutRequests()).toEqual([])
  })

  // 테스트 코드: RS-093
  it('차트만 저장된 배치는 차트 타일만 보인다', async () => {
    // given: 배치가 차트만으로 저장된 리포트
    const chartOnly = savedReport({ id: 42, name: '차트만', owner: PARK, chart: VENDOR_CHART, layout: { view: 'chart', order: ['chart', 'table'], arrange: 'stacked' } })
    // when: 보기 화면을 연다
    await openView(chartOnly.id, { savedReports: [...SAVED_SAMPLES, chartOnly] })

    // then: 차트 타일만 보이고 차트만이 선택되어 있다
    expect(await screen.findByRole('region', { name: '차트 타일' })).toBeVisible()
    expect(viewRadio('차트만')).toBeChecked()
    expect(screen.queryByRole('region', { name: '표 타일' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-093
  it('탭·차트 설정·저장 버튼이 없다', async () => {
    // when: 보기 화면을 연다
    await open()

    // then: 탭, 차트 설정·만들기·삭제, 저장 버튼이 없다
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '차트 설정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '차트 만들기' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '저장' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '차트 삭제' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-093
  it('저장 차트가 없으면 표만 보이고 차트 보기가 꺼지며 저장된 배치는 바뀌지 않는다', async () => {
    // given: 차트 없이 배치(차트 → 표, 한 줄)가 저장된 리포트
    const stored = savedReport({ id: 43, name: '차트 없음', owner: PARK, layout: SIDE })
    // when: 보기 화면을 연다
    await openView(stored.id, { savedReports: [...SAVED_SAMPLES, stored] })
    await screen.findByRole('table', { name: '조회 결과' })

    // then: 표+차트·차트만이 꺼지고 안내 title이 있으며 표 타일만 보이고 배치 요청 없이 저장된 배치가 그대로다
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

  it('깨진 차트 문제는 결과 영역 위에 보이고 리포트는 차트 없는 것으로 다룬다', async () => {
    // given: 차트를 읽을 수 없고 한 줄 배치가 저장된 남의 리포트
    const PROBLEM = '저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요.'
    const broken = savedReport({ id: 44, name: '깨진 차트', owner: PARK, chartProblem: PROBLEM, layout: SIDE })
    // when: 보기 화면을 연다
    await openView(broken.id, { savedReports: [...SAVED_SAMPLES, broken] })
    await screen.findByRole('table', { name: '조회 결과' })
    const message = screen.getByText(PROBLEM)

    // then: 문제 문구가 결과 표보다 앞에 보이고 차트만 보기는 비활성이다
    expect(message).toBeVisible()
    expect(message.compareDocumentPosition(screen.getByRole('table', { name: '조회 결과' })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(viewRadio('차트만')).toBeDisabled()
  })

  // 테스트 코드: RS-093
  it('수정 권한이 있으면 읽기 전용 안내가 없다', async () => {
    // when: 수정할 수 있는 사용자로 보기 화면을 연다
    await open()

    // then: 읽기 전용 안내가 없다
    expect(screen.queryByText(READ_ONLY_NOTE)).not.toBeInTheDocument()
  })
})

describe('바꿀 때마다 저장', () => {
  // 테스트 코드: RS-094
  it('보기 방식을 고르면 연 revision으로 바로 저장한다', async () => {
    // given: 리포트를 revision 1로 연다
    const { user } = await open()

    // when: 표만을 고른다
    await chooseView(user, '표만')

    // then: 연 revision의 배치 저장 요청이 한 번 가고 서버에 반영된다
    await waitFor(() => expect(layoutRequests()).toHaveLength(1))
    expect(layoutRequests()[0]).toMatchObject({ op: 'layout', id: REPORT.id, body: { layout: { view: 'table', order: ['chart', 'table'], arrange: 'side_by_side' }, revision: 1 } })
    expect(await gateway.reports.get(REPORT.id)).toMatchObject({ revision: 2, layout: { view: 'table', order: ['chart', 'table'], arrange: 'side_by_side' } })
  })

  // 테스트 코드: RS-094
  it('요청 중에는 저장 중, 끝나면 저장함 상태를 보인다', async () => {
    // given: 배치 저장 응답을 관문에 붙잡아 둔다
    const { user } = await open()
    const gate = holdSaves()

    // when: 보기 방식을 바꾼다
    await chooseView(user, '표만')

    // then: 저장 중 상태(polite)가 보인다
    expect(await screen.findByText(SAVING)).toBeVisible()
    expect(status()).toHaveTextContent(SAVING)
    expect(status()).toHaveAttribute('aria-live', 'polite')
    // when: 응답을 푼다
    await gate.release()
    // then: 저장함 상태가 보이고 저장 중은 사라진다
    expect(await screen.findByText(SAVED)).toBeVisible()
    expect(status()).toHaveTextContent(SAVED)
    expect(screen.queryByText(SAVING)).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-094
  it('타일은 놓을 때 한 번만 저장하고 끌어서 지나가는 동안은 저장하지 않는다', async () => {
    // given: 보기 화면
    await open()
    // when: 표 타일을 끌어 차트 위를 지나가게 한다
    const transfer = startDrag('표')

    dragOverTile(transfer, '차트', EDGE_POINT.bottom)
    dragOverTile(transfer, '차트', EDGE_POINT.left)
    // then: 아직 요청이 없다
    expect(layoutRequests()).toHaveLength(0)
    // when: 차트 아래쪽에 놓는다
    dropOnTile(transfer, '차트', EDGE_POINT.bottom)
    endDrag(transfer, '표')

    // then: 놓을 때 한 번 저장된다
    await waitFor(() => expect(layoutRequests()).toHaveLength(1))
    expect(bodies()[0]).toEqual({ layout: { view: 'both', order: ['chart', 'table'], arrange: 'stacked' }, revision: 1 })
  })

  // 테스트 코드: RS-094
  it('키보드 이동도 놓기와 같이 한 번 저장한다', async () => {
    // given: 보기 화면
    const { user } = await open()

    // when: 표 타일을 Alt+←로 옮긴다
    await moveByKey(user, '표', 'ArrowLeft')

    // then: 한 줄 배치가 한 번 저장된다
    await waitFor(() => expect(layoutRequests()).toHaveLength(1))
    expect(bodies()[0]?.layout).toEqual({ view: 'both', order: ['table', 'chart'], arrange: 'side_by_side' })
  })

  // 테스트 코드: RS-095
  it('배치가 바뀌지 않는 선택은 요청을 보내지 않는다', async () => {
    // given: 표+차트 보기 화면
    const { user } = await open()

    // when: 이미 고른 보기를 다시 고르고 표를 자기 자리에 놓는다
    await chooseView(user, '표+차트') // 이미 고른 보기
    dragTile('표', '표', 'right') // 자기 자신 위에 놓기

    // then: 요청도 저장 중 표시도 없다
    expect(layoutRequests()).toEqual([])
    expect(screen.queryByText(SAVING)).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-095
  it('이미 저장된 보기를 다시 고르면 요청을 보내지 않는다', async () => {
    // given: 표만을 저장한 보기 화면
    const { user } = await open()
    await chooseView(user, '표만')
    await screen.findByText(SAVED)

    // when: 같은 표만을 다시 고른다
    await chooseView(user, '표만') // 이미 저장된 보기를 다시 고름

    // then: 요청은 처음 한 번뿐이다
    expect(layoutRequests()).toHaveLength(1)
  })

  // 테스트 코드: RS-094
  it('머리의 최종 수정자·시각은 응답 값으로 바뀐다', async () => {
    // given: 박영업이 만든 리포트의 보기 화면(수정자 표시 없음)
    const { user } = await open()
    expect(screen.getByText(/박영업 · /)).not.toHaveTextContent('수정:')

    // when: 보기 방식을 바꿔 저장한다
    await chooseView(user, '표만')

    // then: 머리에 "(수정: 김영업)"이 보이고 서버 값도 그렇다
    expect(await screen.findByText(/\(수정: 김영업\)/)).toBeVisible()
    expect(await gateway.reports.get(REPORT.id)).toMatchObject({ updatedBy: { name: '김영업' }, revision: 2 })
  })

  // 테스트 코드: RS-095
  it('저장함 표시는 다음 변경과 함께 사라진다', async () => {
    // given: 표만을 저장하고 저장함이 보이는 화면
    const { user } = await open()
    const gate = holdSaves()
    await chooseView(user, '표만')
    await gate.release()
    await screen.findByText(SAVED)

    // when: 다음 변경을 한다
    await chooseView(user, '차트만')

    // then: 저장함이 지워지고 저장 중이 보이다가 다시 저장함이 된다
    expect(screen.queryByText(SAVED)).not.toBeInTheDocument()
    expect(await screen.findByText(SAVING)).toBeVisible()

    // when: 응답을 푼다
    await gate.release()
    // then: 다시 저장함이 보인다
    expect(await screen.findByText(SAVED)).toBeVisible()
  })
})

describe('연속 변경은 한 번에 하나씩', () => {
  // 테스트 코드: RS-096
  it('요청 중의 세 번 변경은 마지막 값과 새 revision을 실은 두 번째 요청 하나로 나간다', async () => {
    // given: 첫 응답을 관문에 붙잡아 둔다
    const { user } = await open()
    const gate = holdSaves()

    // when: 첫 요청을 보낸 뒤 요청 중에 세 번 더 바꾼다
    await chooseView(user, '표만') // 요청 1
    await screen.findByText(SAVING)
    await chooseView(user, '차트만') // 대기 값(중간 값은 버려진다)
    await chooseView(user, '표+차트')
    dragTile('표', '차트', 'bottom') // 마지막 값: 표+차트, 차트 → 표, 두 줄

    // then: 요청은 아직 하나다
    expect(layoutRequests()).toHaveLength(1)
    // when: 첫 응답을 푼다
    await gate.release()
    // then: 두 번째 요청이 마지막 값과 revision 2를 싣고 나가며 최종 저장 값이 마지막 값이다
    await waitFor(() => expect(layoutRequests()).toHaveLength(2))
    expect(bodies()[1]).toEqual({ layout: { view: 'both', order: ['chart', 'table'], arrange: 'stacked' }, revision: 2 })
    expect(bodies()[0]?.layout.view).toBe('table')

    // when: 두 번째 응답을 푼다
    await gate.release()
    // then: 저장함이 보이고 요청은 둘뿐이다
    expect(await screen.findByText(SAVED)).toBeVisible()
    expect(layoutRequests()).toHaveLength(2)
    expect(await gateway.reports.get(REPORT.id)).toMatchObject({ revision: 3, layout: { view: 'both', order: ['chart', 'table'], arrange: 'stacked' } })
  })

  // 테스트 코드: RS-096
  it('동시에 하나의 요청만 진행된다', async () => {
    // given: 첫 응답을 관문에 붙잡아 둔다
    const { user } = await open()
    const gate = holdSaves()

    // when: 요청 중에 여러 번 바꾼다
    await chooseView(user, '표만')
    await screen.findByText(SAVING)
    await chooseView(user, '차트만')
    await chooseView(user, '표+차트')
    dragTile('표', '차트', 'bottom')

    // then: 진행 중인 요청이 하나이고 보낸 요청도 하나다
    await waitFor(() => expect(gate.pending()).toBe(1))
    expect(layoutRequests()).toHaveLength(1)
  })

  // 테스트 코드: RS-096
  it('대기 값이 첫 응답 배치와 같으면 두 번째 요청이 없다', async () => {
    // given: 첫 응답을 관문에 붙잡아 둔다
    const { user } = await open()
    const gate = holdSaves()

    // when: 요청 중에 다른 값을 거쳐 첫 요청과 같은 값으로 되돌린다
    await chooseView(user, '표만') // 요청 1: 표만
    await screen.findByText(SAVING)
    await chooseView(user, '차트만') // 대기 값
    await chooseView(user, '표만') // 대기 값이 요청 1과 같아진다

    // when: 첫 응답을 푼다
    await gate.release()
    // then: 저장함이 보이고 요청은 하나뿐이다
    expect(await screen.findByText(SAVED)).toBeVisible()
    expect(layoutRequests()).toHaveLength(1)
    expect(viewRadio('표만')).toBeChecked()
  })

  // 테스트 코드: RS-096
  it('첫 응답이 와도 화면 배치는 대기 값 그대로다', async () => {
    // given: 첫 응답을 붙잡아 두고 요청 중에 값을 바꾼다
    const { user } = await open()
    const gate = holdSaves()
    await chooseView(user, '표만')
    await screen.findByText(SAVING)
    await chooseView(user, '차트만')

    // when: 첫 응답을 푼다
    await gate.release()
    await waitFor(() => expect(layoutRequests()).toHaveLength(2))

    // then: 화면 배치가 대기 값(차트만) 그대로다
    expect(viewRadio('차트만')).toBeChecked()
    expect(screen.queryByRole('region', { name: '표 타일' })).not.toBeInTheDocument()
    // when: 둘째 응답을 푼다
    await gate.release()
    // then: 저장 뒤에도 화면 배치가 그대로다
    await screen.findByText(SAVED)
    expect(viewRadio('차트만')).toBeChecked()
  })
})

describe('편집·복제 단추', () => {
  // 테스트 코드: RS-097
  it('저장 중에는 편집·복제가 꺼지고 끝나면 다시 켜지며 다시 조회는 영향이 없다', async () => {
    // given: 응답을 붙잡아 둔 보기 화면
    const { user } = await open()
    const gate = holdSaves()

    // when: 보기 방식을 바꿔 요청 중으로 만든다
    await chooseView(user, '표만')
    await screen.findByText(SAVING)

    // then: 복제는 비활성, 편집은 aria-disabled이고 title이 있으며 다시 조회는 켜져 있다
    expect(screen.getByRole('button', { name: '복제' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '복제' })).toHaveAttribute('title', BUSY_TITLE)
    const edit = editControl() as HTMLElement
    expect(edit).toHaveAttribute('aria-disabled', 'true')
    expect(edit).toHaveAttribute('title', BUSY_TITLE)
    expect(screen.getByRole('button', { name: '다시 조회' })).toBeEnabled()

    // when: 응답을 푼다
    await gate.release()
    await screen.findByText(SAVED)

    // then: 편집·복제를 다시 쓸 수 있다
    expect(screen.getByRole('button', { name: '복제' })).toBeEnabled()
    expect(editControl()).not.toHaveAttribute('aria-disabled', 'true')
  })

  // 테스트 코드: RS-097
  it('저장 중에는 편집 링크를 눌러도 이동하지 않는다', async () => {
    // given: 응답을 붙잡아 둔 저장 중 화면
    const { user, location } = await open()
    holdSaves()
    await chooseView(user, '표만')
    await screen.findByText(SAVING)

    // when: 편집 링크를 누른다
    await user.click(editControl() as HTMLElement)

    // then: 주소가 그대로다
    expect(location()).toBe(`/reports/${REPORT.id}`)
  })

  // 테스트 코드: RS-097
  it('대기 값이 남아 있는 동안에도 꺼져 있다', async () => {
    // given: 첫 응답을 붙잡고 요청 중에 한 번 더 바꾼다
    const { user } = await open()
    const gate = holdSaves()
    await chooseView(user, '표만')
    await screen.findByText(SAVING)
    await chooseView(user, '차트만')
    // when: 첫 응답만 푼다
    await gate.release()
    await waitFor(() => expect(layoutRequests()).toHaveLength(2))

    // then: 둘째 요청 중이라 복제가 꺼져 있다
    expect(screen.getByRole('button', { name: '복제' })).toBeDisabled()
    // when: 둘째 응답도 푼다
    await gate.release()
    await screen.findByText(SAVED)
    // then: 복제를 다시 쓸 수 있다
    expect(screen.getByRole('button', { name: '복제' })).toBeEnabled()
  })

  // 테스트 코드: RS-098
  it('복제하면 저장된 배치가 복사되고 복제 요청에는 배치가 없다', async () => {
    // given: 보기 방식을 표만으로 저장한 보기 화면
    const { user, location } = await open()
    await chooseView(user, '표만')
    await screen.findByText(SAVED)

    // when: 복제 창에서 이름을 정해 저장한다
    await user.click(screen.getByRole('button', { name: '복제' }))
    const dialog = await saveDialog()
    await typeName(user, dialog, '배치 복제본')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 새 리포트 편집 화면으로 간다
    await waitFor(() => expect(location()).toMatch(/^\/reports\/\d+\/edit$/))
    // then: 복제 요청 본문에 배치가 없고 복제본은 저장된 배치를 가진다
    const [copy] = mockControl.savedReportRequests().filter((r) => r.op === 'copy')
    expect(copy?.body).not.toHaveProperty('layout')
    const copied = (await gateway.reports.list()).find((r) => r.name === '배치 복제본')
    expect(copied).toBeDefined()
    expect(await gateway.reports.get(copied?.id as number)).toMatchObject({ layout: { view: 'table', order: ['chart', 'table'], arrange: 'side_by_side' } })
  })
})

describe('409: 그 사이 다른 사람이 저장함', () => {
  // 테스트 코드: RS-099
  it('409면 재시도 없이 멈추고 최신 배치를 다시 읽어 다시 조회하며 이유를 알린다', async () => {
    // given: 연 뒤 다른 사용자가 리포트를 저장했다, 지금까지의 실행 횟수
    const { user } = await open()
    mockControl.touchSavedReport(REPORT.id, { layout: OTHERS })
    const runsBefore = runCount()

    // when: 보기 방식을 바꾼다
    await chooseView(user, '표만')

    // then: 충돌 안내가 보이고 배치 요청은 한 번뿐이다
    expect(await screen.findByRole('alert')).toHaveTextContent(CONFLICT)
    expect(layoutRequests()).toHaveLength(1)
    // then: 화면 배치가 최신 저장 값으로 바뀌고 실행이 한 번 더 간다
    await waitFor(() => expect(tileOrder()).toEqual(['표', '차트']))
    expect(arrangement()).toBe('stacked')
    expect(viewRadio('표+차트')).toBeChecked()
    await waitFor(() => expect(runCount()).toBe(runsBefore + 1))
    expect(layoutRequests()).toHaveLength(1) // 재시도 없음
  })

  // 테스트 코드: RS-099
  it('대기 값은 버려지고 최신 저장 배치가 보인다', async () => {
    // given: 첫 응답을 붙잡고 대기 값을 만든 뒤 다른 사용자가 저장했다
    const { user } = await open()
    const gate = holdSaves()
    await chooseView(user, '표만')
    await screen.findByText(SAVING)
    await chooseView(user, '차트만') // 대기 값
    mockControl.touchSavedReport(REPORT.id, { layout: OTHERS })

    // when: 첫 응답을 푼다(409)
    await gate.release()

    // then: 충돌 안내가 보이고 화면 배치가 최신 저장 값이며 대기 값은 보내지 않는다
    expect(await screen.findByRole('alert')).toHaveTextContent(CONFLICT)
    await waitFor(() => expect(tileOrder()).toEqual(['표', '차트']))
    expect(layoutRequests()).toHaveLength(1)
    expect(viewRadio('표+차트')).toBeChecked()
  })

  // 테스트 코드: RS-099
  it('다시 읽는 동안의 변경은 보내지 않고 그 뒤의 변경은 새 revision으로 저장한다', async () => {
    // given: 최신 리포트 읽기를 붙잡아 두고 다른 사용자가 저장했다
    const { user } = await open()
    const original = gateway.reports.get.bind(gateway.reports)
    let release: () => void = () => undefined
    const held = new Promise<void>((resolve) => (release = resolve))
    vi.spyOn(gateway.reports, 'get').mockImplementation(async (id: number) => {
      await held
      return original(id)
    })
    mockControl.touchSavedReport(REPORT.id, { layout: OTHERS })

    // when: 보기 방식을 바꿔 409를 받는다
    await chooseView(user, '표만') // 409 -> 다시 읽기 시작(응답은 붙잡아 둔다)
    // then: 충돌 안내가 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent(CONFLICT)
    // when: 다시 읽는 중에 또 바꾼다
    await chooseView(user, '차트만') // 다시 읽는 중의 변경: 낡은 revision으로 보내면 안 된다
    // then: 그 변경은 보내지 않는다
    expect(layoutRequests()).toHaveLength(1)

    // when: 다시 읽기를 푼다
    release()
    // then: 최신 저장 값이 보이고 요청은 그대로 하나다
    await waitFor(() => expect(tileOrder()).toEqual(['표', '차트']))
    expect(viewRadio('표+차트')).toBeChecked() // 최신 저장 값, 그 변경은 버려졌다
    expect(layoutRequests()).toHaveLength(1)
    // when: 다시 읽은 뒤 바꾼다
    await chooseView(user, '표만')
    // then: 새 revision 2로 저장된다
    await waitFor(() => expect(layoutRequests()).toHaveLength(2))
    expect(bodies()[1]?.revision).toBe(2)
  })

  // 테스트 코드: RS-099
  it('다시 읽은 뒤의 변경은 새 revision으로 저장하고 충돌 안내가 사라진다', async () => {
    // given: 다른 사용자가 저장해 409로 최신 배치를 다시 읽은 화면
    const { user } = await open()
    mockControl.touchSavedReport(REPORT.id, { layout: OTHERS })
    // when: 다시 읽은 뒤 보기 방식을 바꾼다
    await chooseView(user, '표만')
    await screen.findByRole('alert')
    await waitFor(() => expect(tileOrder()).toEqual(['표', '차트']))

    await chooseView(user, '표만')

    // then: revision 2의 요청이 나가 저장되고 충돌 안내가 없다
    await waitFor(() => expect(layoutRequests()).toHaveLength(2))
    expect(bodies()[1]).toEqual({ layout: { view: 'table', order: ['table', 'chart'], arrange: 'stacked' }, revision: 2 })
    expect(await screen.findByText(SAVED)).toBeVisible()
    expect(screen.queryByText(CONFLICT)).not.toBeInTheDocument()
  })
})

describe('그 밖의 실패', () => {
  // 테스트 코드: RS-100
  it('403이면 바꾼 배치를 화면에 두고 멈추며 더 보내지 않는다', async () => {
    // given: 첫 배치 저장이 403으로 실패한다
    const { user } = await open()
    failAttempt(1, () => forbidden('권한 없음'))

    // when: 보기 방식을 바꾼다
    await chooseView(user, '표만')

    // then: 권한 안내가 보이고 바꾼 배치가 화면에 남는다
    expect(await screen.findByRole('alert')).toHaveTextContent(FORBIDDEN)
    expect(viewRadio('표만')).toBeChecked()
    // when: 다시 바꾸고 타일을 옮긴다
    await chooseView(user, '표+차트')
    dragTile('표', '차트', 'bottom')
    // then: 화면은 바뀌고 요청은 더 나가지 않는다
    expect(viewRadio('표+차트')).toBeChecked()
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('stacked')
    expect(layoutRequests()).toHaveLength(1)
  })

  // 테스트 코드: RS-100
  it('404면 목록 링크와 함께 멈추고 더 보내지 않는다', async () => {
    // given: 첫 배치 저장이 404로 실패한다
    const { user } = await open()
    failAttempt(1, () => notFound('없음'))

    // when: 보기 방식을 바꾼다
    await chooseView(user, '표만')

    // then: 찾을 수 없음 안내와 목록 링크가 보인다
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(NOT_FOUND)
    expect(within(alert).getByRole('link')).toHaveAttribute('href', '/reports')
    // when: 다시 바꾼다
    await chooseView(user, '차트만')
    // then: 요청은 더 나가지 않고 화면은 바뀐다
    expect(layoutRequests()).toHaveLength(1)
    expect(viewRadio('차트만')).toBeChecked()
  })

  // 테스트 코드: RS-101
  it.each([
    ['a server error', () => new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 내부 오류입니다' })],
    ['a network error', () => new ApiError(0, { type: 'https://x/problems/network', title: 'Network Error', status: 0, detail: '서버에 연결할 수 없습니다.' })],
    ['a layout violation', () => invalidReport([{ location: ['layout', 'view'], code: 'invalid-value', message: '보기 방식 오류' }])],
  ])('%s이면 화면 배치를 두고 "다시 시도" 단추를 보인다', async (_name, error) => {
    // given: 첫 배치 저장이 해당 오류로 실패한다
    const { user } = await open()
    failAttempt(1, error)

    // when: 보기 방식을 바꾼다
    await chooseView(user, '표만')

    // then: 실패 안내와 켜진 "다시 시도"가 보이고 화면 배치가 그대로이며 자동 재시도가 없다
    expect(await screen.findByRole('alert')).toHaveTextContent(FAILED)
    expect(screen.getByRole('button', { name: '다시 시도' })).toBeEnabled()
    expect(viewRadio('표만')).toBeChecked()
    expect(layoutRequests()).toHaveLength(1)
  })

  // 테스트 코드: RS-101
  it('"다시 시도"는 화면 배치를 마지막 확인 revision으로 보내고 안내를 지운다', async () => {
    // given: 첫 저장이 실패해 다시 시도 단추가 보인다
    const { user } = await open()
    failAttempt(1, () => new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 내부 오류입니다' }))
    await chooseView(user, '표만')
    await screen.findByRole('alert')

    // when: 다시 시도를 누른다
    await user.click(screen.getByRole('button', { name: '다시 시도' }))

    // then: revision 1로 다시 보내 저장되고 안내와 단추가 사라진다
    await waitFor(() => expect(layoutRequests()).toHaveLength(2))
    expect(bodies()[1]).toEqual({ layout: { view: 'table', order: ['chart', 'table'], arrange: 'side_by_side' }, revision: 1 })
    expect(await screen.findByText(SAVED)).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '다시 시도' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-101
  it('실패 뒤 다음 변경도 마지막 확인 revision으로 저장하고 자동 재시도는 없다', async () => {
    // given: 첫 저장이 실패한 화면(자동 재시도 없음)
    const { user } = await open()
    failAttempt(1, () => new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 내부 오류입니다' }))
    await chooseView(user, '표만')
    await screen.findByRole('alert')
    expect(layoutRequests()).toHaveLength(1)

    // when: 다음 변경을 한다
    await chooseView(user, '차트만')

    // then: 마지막 확인 revision 1로 저장된다
    await waitFor(() => expect(layoutRequests()).toHaveLength(2))
    expect(bodies()[1]).toEqual({ layout: { view: 'chart', order: ['chart', 'table'], arrange: 'side_by_side' }, revision: 1 })
    expect(await screen.findByText(SAVED)).toBeVisible()
  })

  // 테스트 코드: RS-101
  it('대기 값 저장이 실패하면 실패 상태로 끝나고 더 보내지 않으며 편집·복제가 다시 켜진다', async () => {
    // given: 첫 응답을 붙잡고 요청 중에 대기 값을 만든다, 다음 저장은 서버 오류로 실패한다
    const { user } = await open()
    const gate = holdSaves()
    await chooseView(user, '표만')
    await screen.findByText(SAVING)
    await chooseView(user, '차트만') // 대기 값
    mockControl.setLayoutSaveGate(() => {
      throw new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 내부 오류입니다' })
    })
    // when: 첫 응답을 푼다
    await gate.release()
    // then: 대기 값이 요청 2로 나가 실패한다
    await waitFor(() => expect(layoutRequests()).toHaveLength(2)) // 요청 1이 끝나면 대기 값이 요청 2로 나간다
    await screen.findByRole('alert')

    // then: 더 나가지 않고 복제가 다시 켜진다
    expect(layoutRequests()).toHaveLength(2) // 실패 뒤 더 나가지 않는다
    expect(screen.getByRole('button', { name: '복제' })).toBeEnabled()
  })
})
