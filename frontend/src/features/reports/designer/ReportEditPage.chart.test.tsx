// 편집 화면은 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportEditPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { lastChart } from '../../../test/chartMock'
import { mockControl } from '../../../test/fake/default'
import { chooseKind, createChart, expectPressed, openChartTab, optionAt, panelField } from '../../../test/reportChart'
import { NO_RESULT_NOTE, showTab } from '../../../test/reportLayout'
import { addCountedColumn, chipButton, chipItems, chipTexts, openEditor, settingsOf, saveButton, saveDialog, setupReportClock, UNSAVED_MARK, waitForHiddenResult } from '../../../test/reportScreen'
import { MINE_PUBLIC, SAVED_SAMPLES, VENDOR_CHART, WITH_CHART, savedReport } from '../../../test/savedReports'

setupReportClock()

const LEAVE_TITLE = '저장하지 않은 변경이 있습니다'
const REVERT_TITLE = '저장된 설계로 되돌릴까요?'
const WITH_CHART_ID = WITH_CHART.id
const menuLink = (name: string): HTMLElement => within(screen.getByRole('navigation', { name: '주 메뉴' })).getByRole('link', { name })
const unsavedMark = () => screen.queryByText(UNSAVED_MARK)
const openWithChart = () => openEditor(WITH_CHART_ID, { savedReports: [...SAVED_SAMPLES, WITH_CHART] })

async function overwrite(user: Awaited<ReturnType<typeof openEditor>>['user']): Promise<void> {
  await waitFor(() => expect(saveButton()).toBeEnabled())
  await user.click(saveButton())
  await user.click(within(await saveDialog()).getByRole('button', { name: '저장' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
}

async function revert(user: Awaited<ReturnType<typeof openEditor>>['user']): Promise<void> {
  await user.click(screen.getByRole('button', { name: '되돌리기' }))
  await user.click(within(await screen.findByRole('dialog', { name: REVERT_TITLE })).getByRole('button', { name: '되돌리기' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
}

describe('저장된 차트 열기', () => {
  // 테스트 코드: RC-075
  it('저장된 차트를 같은 패널 값과 차트 옵션으로 연다', async () => {
    // when: 저장된 차트가 있는 리포트의 편집 화면을 열고 차트 탭을 본다
    const { user } = await openWithChart()

    await openChartTab(user)

    expectPressed('묶은 세로 막대')
    // then: 종류·범주·제목·범례·축 제목이 저장값과 같고 차트가 그려지며 저장 안 됨 표시가 없다
    expect(panelField('범주')).toHaveDisplayValue('Vendor')
    expect(panelField('차트 제목')).toHaveValue('Vendor별 금액')
    expect(panelField('범례')).toHaveDisplayValue('위')
    expect(panelField('가로축 제목')).toHaveValue('Vendor')
    expect(panelField('세로축 제목')).toHaveValue('금액 합계')
    expect(lastChart().type).toBe('bar')
    expect(optionAt('plugins', 'title')).toMatchObject({ display: true, text: 'Vendor별 금액' })
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-075
  it('차트가 없는 저장 리포트는 차트 만들기 빈 상태로 연다', async () => {
    // when: 차트 없는 리포트의 편집 화면을 열고 차트 탭을 본다
    const { user } = await openEditor(MINE_PUBLIC.id)

    await openChartTab(user)

    // then: 차트 만들기 버튼이 활성이고 그림이 없다
    expect(await screen.findByRole('button', { name: '차트 만들기' })).toBeEnabled()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-076
  it('새 차트를 덮어쓰기로 저장하고 다시 열면 같은 설정으로 열린다', async () => {
    // given: 차트 없는 리포트에서 차트를 만들고 꺾은선·제목·오른쪽 범례·데이터 레이블로 바꿔 둔다
    const { user, goTo } = await openEditor(MINE_PUBLIC.id)
    await openChartTab(user)
    await createChart(user)
    await chooseKind(user, '꺾은선')
    await user.type(panelField('차트 제목'), '저장할 제목')
    await user.selectOptions(panelField('범례'), '오른쪽')
    await user.click(panelField('데이터 레이블'))

    // when: 덮어쓰기로 저장한다
    await overwrite(user)

    // then: 저장 요청과 서버 값이 바뀐 차트를 담고 저장 안 됨 표시가 없다
    const sent = mockControl.savedReportRequests().find((r) => r.op === 'update')
    expect((sent?.body as { chart: unknown }).chart).toMatchObject({ kind: 'line', category: 0, values: [1], title: '저장할 제목', legend: 'right', dataLabels: true })
    expect((await gateway.reports.get(MINE_PUBLIC.id)).chart).toMatchObject({ kind: 'line', title: '저장할 제목' })
    expect(unsavedMark()).not.toBeInTheDocument()

    // when: 목록으로 갔다가 같은 리포트의 편집 화면을 다시 연다
    goTo('/reports')
    await screen.findByRole('table', { name: '리포트 목록' })
    goTo(`/reports/${MINE_PUBLIC.id}/edit`)
    await waitForHiddenResult()
    await openChartTab(user)
    // then: 저장한 종류·제목·범례·데이터 레이블이 그대로 열린다
    expectPressed('꺾은선')
    expect(panelField('차트 제목')).toHaveValue('저장할 제목')
    expect(panelField('범례')).toHaveDisplayValue('오른쪽')
    expect(panelField('데이터 레이블')).toBeChecked()
    expect(lastChart().type).toBe('line')
    expect(optionAt('plugins', 'legend', 'position')).toBe('right')
  })

  // 테스트 코드: RC-076
  it('차트 삭제 뒤 덮어쓰면 저장된 차트가 지워진다', async () => {
    // given: 저장된 차트가 있는 리포트의 편집 화면에서 차트 삭제를 눌러 둔다
    const { user } = await openWithChart()
    await openChartTab(user)
    await user.click(await screen.findByRole('button', { name: '차트 삭제' }))

    // when: 덮어쓰기로 저장한다
    await overwrite(user)

    // then: 서버 차트가 없고 목록의 차트 종류도 없다
    expect((await gateway.reports.get(WITH_CHART_ID)).chart).toBeNull()
    expect((await gateway.reports.list()).find((r) => r.id === WITH_CHART_ID)?.chartKind).toBeNull()
  })

  // 테스트 코드: RC-076
  it('차트 제목만 바꿔 덮어써도 차트의 나머지 설정이 유지된다', async () => {
    // given: 저장된 차트가 있는 리포트의 편집 화면에서 차트 제목에 글자를 더해 둔다
    const { user } = await openWithChart()
    await openChartTab(user)
    await user.type(panelField('차트 제목'), ' 수정')

    // when: 덮어쓰기로 저장한다
    await overwrite(user)

    // then: 서버 차트가 제목만 바뀐 같은 차트이고 revision이 2다
    expect((await gateway.reports.get(WITH_CHART_ID)).chart).toMatchObject({ ...VENDOR_CHART, title: 'Vendor별 금액 수정' })
    expect((await gateway.reports.get(WITH_CHART_ID)).revision).toBe(2)
  })
})

describe('저장 안 됨과 떠날 때 확인', () => {
  // 테스트 코드: RC-077
  it('차트를 만들면 저장 안 됨으로 표시하고 결과는 그대로 두며 떠날 때 확인한다', async () => {
    // given: 차트 없는 리포트의 편집 화면(저장 안 됨 표시 없음)
    const { user } = await openEditor(MINE_PUBLIC.id)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    expect(unsavedMark()).not.toBeInTheDocument()
    await openChartTab(user)

    // when: 차트를 만든다
    await createChart(user)

    // then: 저장 안 됨 표시가 보이고 저장이 가능하며 결과 표는 다시 조회하지 않는다
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    expect(saveButton()).toBeEnabled()
    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()
    expect(mockControl.reportQueries()).toHaveLength(1)
    // when: 다른 메뉴 링크를 누른다
    await user.click(menuLink('Deals'))
    // then: 떠날 때 확인 창이 뜬다
    const dialog = await screen.findByRole('dialog', { name: LEAVE_TITLE })
    // when: 머물기를 누른다
    await user.click(within(dialog).getByRole('button', { name: '머물기' }))
    // then: 확인 창이 닫힌다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-077
  it('차트를 바꾸면 저장 안 됨이고 원래대로 돌리면 표시가 사라진다', async () => {
    // given: 저장된 차트가 있는 리포트의 편집 화면의 차트 탭
    const { user } = await openWithChart()
    await openChartTab(user)

    // when: 제목에 글자를 더한다
    await user.type(panelField('차트 제목'), 'x')
    // then: 저장 안 됨 표시가 보인다
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    // when: 더한 글자를 지운다
    await user.type(panelField('차트 제목'), '{Backspace}')

    // then: 제목이 원래대로이고 표시가 사라진다
    expect(panelField('차트 제목')).toHaveValue('Vendor별 금액')
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-077
  it('저장된 차트를 지우면 저장 안 됨이다', async () => {
    // given: 저장된 차트가 있는 리포트의 편집 화면의 차트 탭
    const { user } = await openWithChart()
    await openChartTab(user)

    // when: 차트 삭제를 누른다
    await user.click(await screen.findByRole('button', { name: '차트 삭제' }))

    // then: 저장 안 됨 표시가 보이고 저장이 가능하다
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    expect(saveButton()).toBeEnabled()
  })

  // 테스트 코드: RC-077
  it('차트를 만들었다가 다시 지우면 저장 안 됨이 아니다', async () => {
    // given: 차트 없는 리포트에서 차트를 만들어 둔다
    const { user } = await openEditor(MINE_PUBLIC.id)
    await openChartTab(user)
    await createChart(user)

    // when: 차트 삭제를 누른다
    await user.click(screen.getByRole('button', { name: '차트 삭제' }))

    // then: 저장 안 됨 표시가 없다
    expect(unsavedMark()).not.toBeInTheDocument()
  })
})

describe('되돌리기', () => {
  // 테스트 코드: RC-077
  it('되돌리면 저장된 차트 설정으로 돌아온다', async () => {
    // given: 저장된 차트가 있는 리포트의 편집 화면에서 제목과 종류를 바꿔 둔다
    const { user } = await openWithChart()
    await openChartTab(user)
    await user.type(panelField('차트 제목'), ' 바뀜')
    await chooseKind(user, '꺾은선')

    // when: 되돌린다
    await revert(user)

    await openChartTab(user)
    // then: 제목과 종류가 저장값으로 돌아오고 저장 안 됨 표시가 없다
    expect(panelField('차트 제목')).toHaveValue('Vendor별 금액')
    expectPressed('묶은 세로 막대')
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-077
  it('되돌리면 불러온 뒤 만든 차트는 사라진다', async () => {
    // given: 차트 없는 리포트에서 차트를 만들어 둔다
    const { user } = await openEditor(MINE_PUBLIC.id)
    await openChartTab(user)
    await createChart(user)

    // when: 되돌린다
    await revert(user)

    await openChartTab(user)
    // then: 차트 만들기 빈 상태이고 저장 안 됨 표시가 없다
    expect(await screen.findByRole('button', { name: '차트 만들기' })).toBeVisible()
    expect(unsavedMark()).not.toBeInTheDocument()
  })
})

describe('덮어쓰기 뒤 기준선', () => {
  // 테스트 코드: RC-077
  it('덮어쓴 뒤에는 서버가 정리한 제목이 기준선이라 저장 안 됨이 아니다', async () => {
    // given: 저장된 차트가 있는 리포트의 편집 화면에서 앞뒤 공백이 있는 제목을 입력해 둔다
    const { user } = await openWithChart()
    await openChartTab(user)
    await user.clear(panelField('차트 제목'))
    await user.type(panelField('차트 제목'), '  매출  ')

    // when: 덮어쓰기로 저장한다
    await overwrite(user)

    // then: 서버는 공백을 지운 제목을 저장하고 저장 안 됨 표시가 없다
    expect((await gateway.reports.get(WITH_CHART_ID)).chart?.title).toBe('매출')
    expect(unsavedMark()).not.toBeInTheDocument()
    // when: 범례를 바꾼다
    await user.selectOptions(panelField('범례'), '아래')
    // then: 저장 안 됨 표시가 보인다
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    // when: 되돌린다
    await revert(user)
    // then: 저장 안 됨 표시가 없다
    expect(unsavedMark()).not.toBeInTheDocument()
  })
})

describe('되돌리기 분기: 차트만 바뀐 경우와 조회 설계도 바뀐 경우', () => {
  // 테스트 코드: RC-077
  it('차트만 바꾼 경우의 되돌리기는 결과 표를 유지하고 차트만 되살린다', async () => {
    // given: 저장된 차트가 있는 리포트의 편집 화면에서 차트만 바꿔 둔다
    const { user } = await openWithChart()
    await openChartTab(user)
    await user.type(panelField('차트 제목'), ' 바뀜')
    await chooseKind(user, '꺾은선')
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()

    // when: 되돌린다
    await revert(user)

    await showTab(user, 'result')
    // then: 결과 표가 그대로 있고 제목·종류가 저장값이며 저장 안 됨 표시가 없다
    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()
    await openChartTab(user)
    expect(panelField('차트 제목')).toHaveValue('Vendor별 금액')
    expectPressed('묶은 세로 막대')
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-077
  it('조회 설계도 바뀐 경우의 되돌리기는 결과를 지우고 설계와 차트를 되살린다', async () => {
    // given: 저장된 차트가 있는 리포트의 편집 화면에서 조회 설계와 차트를 바꿔 둔다
    const { user } = await openWithChart()
    await user.click(chipButton(1))
    await user.selectOptions(within(settingsOf('금액 합계')).getByRole('combobox', { name: '정렬' }), '정렬 없음')
    expect(chipTexts()[1]).not.toMatch(/[▲▼]/)
    await addCountedColumn(user, 'Deal code')
    await openChartTab(user)
    await user.type(panelField('차트 제목'), ' 바뀜')
    await showTab(user, 'design')
    expect(chipItems()).toHaveLength(3)

    // when: 되돌린다
    await revert(user)

    // then: 컬럼과 정렬이 저장값이고 결과 표는 없으며 차트 설정이 저장값이고 저장 안 됨 표시가 없다
    expect(chipItems()).toHaveLength(2)
    expect(chipTexts()[1]).toContain('▼ 내림')

    // when: 결과 탭으로 옮겨 차트 탭을 연다
    await showTab(user, 'result')
    await openChartTab(user)
    // then: 결과 표는 없고 차트 설정이 저장값이며 저장 안 됨 표시가 없다
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()
    expect(screen.getByText(NO_RESULT_NOTE)).toBeVisible()
    expect(panelField('차트 제목')).toHaveValue('Vendor별 금액')
    expect(panelField('범주')).toHaveDisplayValue('Vendor')
    expect(unsavedMark()).not.toBeInTheDocument()
  })
})

describe('깨진 차트로 편집 화면을 열 때', () => {
  // 테스트 코드: RC-075
  it('저장 차트를 읽을 수 없으면 보기 화면처럼 안내 문구를 보인다', async () => {
    // given: 차트를 읽을 수 없는 저장 리포트
    const PROBLEM = '저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요.'
    const broken = savedReport({ id: 22, name: '깨진 차트', chartProblem: PROBLEM })
    const { user } = await openEditor(broken.id, { savedReports: [...SAVED_SAMPLES, broken] })

    // when: 편집 화면을 열고 차트 탭을 본다
    await openChartTab(user)

    // then: "저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다…" 안내가 보인다
    expect(screen.getByText(PROBLEM)).toBeVisible()
  })
})
