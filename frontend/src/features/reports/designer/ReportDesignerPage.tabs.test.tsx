import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ApiError } from '../../../shared/api/problem'
import type { ReportIssue } from '../../../shared/model/reportTypes'
import { mockControl } from '../../../test/fake/default'
import { invalidReport, REPORT_TIMEOUT_MESSAGE, reportTimeout } from '../../../test/fake/errors'
import { groupedAmountResult, resultOf } from '../../../test/reportDesigner'
import {
  chooseView,
  designTab,
  dragTile,
  expectTab,
  NO_RESULT_NOTE,
  panelOf,
  queryTile,
  resultTab,
  showTab,
  STALE_NOTE,
  tile,
  tileOrder,
  viewGroup,
} from '../../../test/reportLayout'
import {
  addColumn,
  addCondition,
  chipItems,
  openAndRun,
  openDesigner,
  rerun,
  runQuery,
  setupReportClock,
  tableTexts,
} from '../../../test/reportScreen'

setupReportClock()

const failWith = (...issues: ReportIssue[]): void =>
  mockControl.setReportQueryHandler(() => {
    throw invalidReport(issues)
  })
const issue = (location: (string | number)[], message: string): ReportIssue => ({ location, code: 'x', message })
const runBar = (): HTMLElement => screen.getByRole('region', { name: '최대 행과 조회' })

describe('작성 탭과 결과 탭', () => {
  // 테스트 코드: RQ-068, RS-082
  it('디자이너 이름의 tablist에 작성·결과 탭이 있고 작성 탭으로 열린다', async () => {
    // when: 디자이너를 연다
    await openDesigner()

    // then: 탭은 작성, 결과이고 작성 탭이 선택되며 제목이 보인다
    const tablist = screen.getByRole('tablist', { name: '리포트 디자이너' })
    expect(within(tablist).getAllByRole('tab').map((t) => t.textContent)).toEqual(['작성', '결과'])
    expectTab('design')
    expect(screen.getByRole('heading', { level: 1, name: '새 리포트' })).toBeVisible()
  })

  // 테스트 코드: RQ-068
  it('필드 목록·범위·컬럼·조건·최대 행·조회 버튼은 작성 탭에 있다', async () => {
    // when: 디자이너를 연다
    await openDesigner()
    // then: 작성 탭 안에 필드 버튼, 최대 행, 조회, 조건 없음 안내가 있고 보기 선택은 없다
    const design = within(panelOf('design'))

    expect(design.getByRole('button', { name: 'Deal code 컬럼에 추가' })).toBeVisible()
    expect(design.getByRole('combobox', { name: '최대 행' })).toBeVisible()
    expect(design.getByRole('button', { name: '조회' })).toBeVisible()
    expect(design.getByRole('region', { name: '최대 행과 조회' })).toBeVisible()
    expect(design.getByText(/조건이 없으면 모든 Deal이 대상입니다/)).toBeVisible()
    expect(design.queryByRole('radiogroup', { name: '보기', hidden: true })).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-068
  it('보기 선택·타일·SQL 보기는 결과 탭에 있다', async () => {
    // given: 디자이너를 열었다
    const { user } = await openDesigner()
    // when: 결과 탭으로 옮긴다
    await showTab(user, 'result')
    // then: 결과 탭에 보기 선택과 SQL 안내가 있고 조회 버튼은 없다
    const result = within(panelOf('result'))

    expect(result.getByRole('radiogroup', { name: '보기' })).toBeVisible()
    expect(result.getByText('조회하면 서버가 만든 SQL이 여기에 보입니다')).toBeVisible()
    expect(result.queryByRole('button', { name: '조회', hidden: true })).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-068, RS-082
  it('보이지 않는 패널은 DOM에 숨은 채 유지된다', async () => {
    // when: 디자이너를 연다
    await openDesigner()

    // then: 결과 패널은 hidden이고 접근성 트리에서는 빠진다
    const result = panelOf('result')

    expect(result).toHaveAttribute('hidden')
    expect(within(result).getByRole('radiogroup', { name: '보기', hidden: true })).toBeInTheDocument()
    expect(screen.queryByRole('radiogroup', { name: '보기' })).not.toBeInTheDocument() // 접근성 트리에서는 빠진다
  })

  // 테스트 코드: RQ-068, RS-082
  it('탭 버튼으로 패널을 바꾼다', async () => {
    // given: 작성 탭이 열린 디자이너
    const { user } = await openDesigner()

    // when: 결과 탭 버튼을 누른다
    await user.click(resultTab())
    // then: 결과 탭이 선택되고 조회 버튼이 보이지 않는다
    expectTab('result')
    expect(screen.queryByRole('button', { name: '조회' })).not.toBeInTheDocument()

    // when: 작성 탭 버튼을 누른다
    await user.click(designTab())
    // then: 작성 탭이 선택되고 필드 버튼이 보인다
    expectTab('design')
    expect(screen.getByRole('button', { name: 'Deal code 컬럼에 추가' })).toBeVisible()
  })

  // 테스트 코드: RQ-068
  it('결과 탭에 다녀와도 설계가 유지된다', async () => {
    // given: 컬럼 하나와 조건 하나를 설계했다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Vendor')

    // when: 결과 탭에 갔다가 작성 탭으로 돌아온다
    await showTab(user, 'result')
    await showTab(user, 'design')

    // then: 컬럼과 조건이 그대로다
    expect(chipItems()).toHaveLength(1)
    expect(screen.getByRole('combobox', { name: '조건 1 필드' })).toBeVisible()
  })
})

describe('조회 성공', () => {
  // 테스트 코드: RQ-089, RS-083
  it('조회가 성공하면 결과 탭으로 옮겨 결과 표를 보인다', async () => {
    // when: Deal code 컬럼으로 조회한다 (전제: 서버가 두 행을 돌려준다)
    await openAndRun(resultOf({ rows: [['A'], ['B']] }), 'Deal code')

    // then: 결과 탭이 열리고 표 타일에 결과 표와 행이 보이며 조회 버튼은 숨는다
    expectTab('result')
    expect(within(tile('표')).getByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(await screen.findByRole('region', { name: '차트 타일' })).toBeVisible()
    expect(tableTexts()).toEqual([['A'], ['B']])
    expect(screen.queryByRole('button', { name: '조회' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-089, RS-083
  it('두 번째 조회 뒤에도 결과 탭으로 옮긴다', async () => {
    // given: 한 번 조회한 뒤 작성 탭으로 돌아왔다
    const { user } = await openAndRun(resultOf({ rows: [['A']] }), 'Deal code')
    // when: 새 결과를 돌려주는 서버로 다시 조회한다
    await showTab(user, 'design')

    mockControl.setReportQueryHandler(() => resultOf({ rows: [['새']] }))
    await runQuery(user)

    // then: 새 결과가 보이고 결과 탭이 열린다
    expect(await screen.findByText('새')).toBeVisible()
    expectTab('result')
  })

  // 테스트 코드: RS-085
  it('보기 방식이 표만이면 다시 조회해도 표 타일만 보인다', async () => {
    // given: 조회를 마친 디자이너
    const { user } = await openAndRun(resultOf({ rows: [['A']] }), 'Deal code')

    // when: 표만을 고르고 작성 탭에서 다시 조회한다
    await chooseView(user, '표만')
    await showTab(user, 'design')
    mockControl.setReportQueryHandler(() => resultOf({ rows: [['B']] }))
    await runQuery(user)

    // then: 새 결과가 보이고 차트 타일은 없다
    expect(await screen.findByText('B')).toBeVisible()
    expect(queryTile('차트')).toBeNull()
  })
})

describe('조회 실패', () => {
  // 테스트 코드: RQ-090
  it('정의 위반이면 작성 탭에 머물며 조회 줄 바로 아래에 고칠 곳을 보인다', async () => {
    // given: 컬럼 둘에 위반이 있다고 서버가 알려준다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, '금액')
    failWith(issue(['columns', 0], '첫 컬럼 문구'), issue(['columns', 1, 'aggregate'], '집계 문구'))

    // when: 조회한다
    await runQuery(user)

    // then: 고칠 곳 2개 알림이 작성 탭의 조회 줄 아래에 있고 해당 칩에 오류 표시가 붙는다
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('고칠 곳 2개')
    expect(alert).toHaveTextContent('컬럼 1(Deal code)')
    expect(alert).toHaveTextContent('집계 문구')
    expectTab('design')
    expect(panelOf('design')).toContainElement(alert)
    expect(runBar().compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(chipItems()[0]).toHaveClass('is-invalid')
  })

  // 테스트 코드: RQ-093, RS-083
  it('시간 초과이면 작성 탭에 머물며 서버 문구를 조회 줄 아래에 보인다', async () => {
    // given: 시간 초과를 내는 서버
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    mockControl.setReportQueryHandler(() => {
      throw reportTimeout()
    })

    // when: 조회한다
    await runQuery(user)

    // then: 시간 초과 문구가 조회 줄 아래에 보이고 작성 탭에 머문다
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(REPORT_TIMEOUT_MESSAGE)
    expectTab('design')
    expect(runBar().compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  // 테스트 코드: RQ-093, RS-083
  it('그 밖의 서버 오류이면 작성 탭에 머문다', async () => {
    // given: 500 오류를 내는 서버
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    mockControl.setReportQueryHandler(() => {
      throw new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 내부 오류입니다' })
    })

    // when: 조회한다
    await runQuery(user)

    // then: 서버 문구가 보이고 작성 탭에 머문다
    expect(await screen.findByRole('alert')).toHaveTextContent('서버 내부 오류입니다')
    expectTab('design')
  })

  // 테스트 코드: RQ-085
  it('읽을 수 없는 입력이면 요청 없이 작성 탭에 머문다', async () => {
    // given: Users count 조건에 1.5를 입력했다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Users count')
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), '1.5')

    // when: 조회한다
    await runQuery(user)

    // then: 요청이 없고 작성 탭에 머물며 값 칸에 오류 표시가 붙는다
    expect(mockControl.reportQueries()).toHaveLength(0)
    expectTab('design')
    expect(screen.getByRole('textbox', { name: '조건 1 값' })).toHaveAttribute('aria-invalid', 'true')
  })

  // 테스트 코드: RQ-093, RS-083
  it('조회가 실패해도 결과 탭에 이전 결과가 남는다', async () => {
    // given: 한 번 조회한 결과가 있고 서버가 이제 시간 초과를 낸다
    const { user } = await openAndRun(resultOf({ rows: [['이전 결과']] }), 'Deal code')
    mockControl.setReportQueryHandler(() => {
      throw reportTimeout()
    })

    // when: 다시 조회한다
    await rerun(user)

    // then: 작성 탭에 시간 초과 문구가 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent(REPORT_TIMEOUT_MESSAGE)
    expectTab('design')
    // when: 결과 탭으로 옮긴다
    await showTab(user, 'result')
    // then: 이전 결과가 그대로다
    expect(tableTexts()).toEqual([['이전 결과']])
  })
})

describe('결과가 아직 없을 때', () => {
  // 테스트 코드: RS-084
  it('조회 전 결과 탭은 안내를 보이되 보기와 배치를 바꿀 수 있다', async () => {
    // given: 조회 전 디자이너
    const { user } = await openDesigner()

    // when: 결과 탭을 연다
    await showTab(user, 'result')

    // then: 표 타일에 안내가 보이고 보기 선택이 있다
    expect(within(tile('표')).getByText(NO_RESULT_NOTE)).toBeVisible()
    expect(viewGroup()).toBeVisible()

    // when: 표 타일을 차트 타일의 오른쪽에 놓는다
    dragTile('표', '차트', 'right')
    // then: 순서가 바뀐다
    expect(tileOrder()).toEqual(['차트', '표'])

    // when: 차트만을 고른다
    await chooseView(user, '차트만')
    // then: 차트 타일만 보인다
    expect(queryTile('표')).toBeNull()
    expect(tile('차트')).toBeVisible()
  })

  // 테스트 코드: RS-084
  it('결과 없이도 표만을 고를 수 있다', async () => {
    // given: 조회 전 결과 탭
    const { user } = await openDesigner()
    await showTab(user, 'result')

    // when: 표만을 고른다
    await chooseView(user, '표만')

    // then: 차트 타일이 없고 표 타일에 안내가 남는다
    expect(queryTile('차트')).toBeNull()
    expect(within(tile('표')).getByText(NO_RESULT_NOTE)).toBeVisible()
  })
})

describe('설계 변경 안내', () => {
  // 테스트 코드: RS-084
  it('보기·배치 변경은 설계 변경 안내를 띄우지 않는다', async () => {
    // given: 조회를 마친 디자이너
    const { user } = await openAndRun(null, 'Deal code')

    // when: 보기와 배치를 바꾼다
    await chooseView(user, '표만')
    await chooseView(user, '표+차트')
    dragTile('표', '차트', 'right')

    // then: 다시 조회 안내가 없다
    expect(screen.queryByText(STALE_NOTE)).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-099
  it('조회 뒤 최대 행을 바꾸면 다시 조회 안내가 보인다', async () => {
    // given: 조회를 마친 결과
    const { user } = await openAndRun(null, 'Deal code')
    await showTab(user, 'design')

    // when: 작성 탭에서 최대 행을 100으로 바꾸고 결과 탭으로 돌아온다
    await user.selectOptions(screen.getByRole('combobox', { name: '최대 행' }), '100')
    await showTab(user, 'result')

    // then: 다시 조회 안내가 보인다
    expect(screen.getByText(STALE_NOTE)).toBeVisible()
  })
})

describe('탭 이름의 고칠 곳 수', () => {
  // 테스트 코드: RQ-090
  it('작성 탭 이름에 고칠 곳 수가 붙고 고치는 대로 줄어 없어진다', async () => {
    // given: 컬럼 둘에 위반이 있다고 서버가 알려준다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')
    failWith(issue(['columns', 0], '코드 컬럼 문구'), issue(['columns', 1, 'label'], '이름 컬럼 문구'))

    // when: 조회한다
    await runQuery(user)

    // then: 작성 탭 이름에 고칠 곳 2가 붙고 결과 탭은 그대로다
    expect(await screen.findByRole('tab', { name: '작성 (고칠 곳 2)' })).toBeVisible()
    expect(resultTab()).toHaveTextContent(/^결과$/)

    // when: 한 컬럼의 표시 이름을 고친다
    await user.type(within(screen.getByRole('region', { name: '컬럼 설정: Deal 이름' })).getByRole('textbox', { name: '표시 이름' }), '이름')

    // then: 고칠 곳 1로 줄어든다
    expect(screen.getByRole('tab', { name: '작성 (고칠 곳 1)' })).toBeVisible()

    // when: 위반이 남은 컬럼을 뺀다
    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))

    // then: 탭 이름에서 수가 사라진다
    expect(designTab()).toHaveTextContent(/^작성$/)
  })

  // 테스트 코드: RQ-090
  it('위반이 없으면 두 탭 이름 모두 수가 없다', async () => {
    // when: 위반 없이 조회한다
    await openAndRun(null, 'Deal code')

    // then: 작성, 결과 탭 이름에 수가 없다
    expect(designTab()).toHaveTextContent(/^작성$/)
    expect(resultTab()).toHaveTextContent(/^결과$/)
  })
})

describe('탭을 옮겨도 결과 화면 상태가 남는다', () => {
  const rowsOf = (n: number) => Array.from({ length: n }, (_, i) => [`행 ${i + 1}`])

  // 테스트 코드: RQ-068, RS-082
  it('탭을 옮겨도 표 페이지가 남는다', async () => {
    // given: 300행 결과의 둘째 페이지를 보고 있다
    const { user } = await openAndRun(resultOf({ rows: rowsOf(300), totalCount: 300 }), 'Deal code')
    await user.click(screen.getByRole('button', { name: '다음' }))
    expect(tableTexts()[0]).toEqual(['행 101'])

    // when: 작성 탭에 갔다가 결과 탭으로 돌아온다
    await showTab(user, 'design')
    await showTab(user, 'result')

    // then: 둘째 페이지가 그대로다
    expect(tableTexts()[0]).toEqual(['행 101'])
    expect(screen.getByRole('navigation', { name: '페이지' })).toHaveTextContent('2 페이지')
  })

  // 테스트 코드: RQ-068, RS-082
  it('탭을 옮겨도 합계 행 선택이 남는다', async () => {
    const result = groupedAmountResult([['A', 1_000_000]], [null, 1_000_000])
    // given: 합계 행을 켠 결과
    const { user } = await openAndRun(result, 'Vendor')
    await user.click(screen.getByRole('checkbox', { name: '합계 행' }))

    // when: 작성 탭에 갔다가 결과 탭으로 돌아온다
    await showTab(user, 'design')
    await showTab(user, 'result')

    // then: 합계 행이 켜진 채 마지막 행이 합계다
    expect(screen.getByRole('checkbox', { name: '합계 행' })).toBeChecked()
    expect(tableTexts().at(-1)?.[0]).toBe('합계')
  })

  // 테스트 코드: RS-082
  it('탭을 옮겨도 고른 보기와 배치가 남는다', async () => {
    // given: 조회를 마친 디자이너
    const { user } = await openAndRun(null, 'Deal code')
    // when: 배치를 바꾸고 작성 탭에 갔다 돌아온다
    dragTile('표', '차트', 'right')
    await chooseView(user, '표+차트')

    await showTab(user, 'design')
    await showTab(user, 'result')

    // then: 배치가 그대로다
    expect(tileOrder()).toEqual(['차트', '표'])
  })
})
