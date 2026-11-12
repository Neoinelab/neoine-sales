// 차트 탭은 React.lazy 청크이므로 reportChart 도구가 미리 읽어 둔다.
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DATALABELS_MOCK_ID, lastChart, renderedCharts } from '../../../test/chartMock'
import { mockControl } from '../../../test/fake/default'
import {
  AMOUNT_HEADER,
  amountCol,
  chartDatasets,
  chartLabels,
  chooseKind,
  createChart,
  familyRadio,
  expectPressed,
  kindButton,
  openChartTab,
  openGroupedDesigner,
  optionAt,
  panelField,
  STATUS_COL,
  chartToggle,
  USERS_HEADER,
  usersCol,
  VENDOR_COL,
  valueGroup,
} from '../../../test/reportChart'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import { expectTab, resultTab, showTab, tile } from '../../../test/reportLayout'
import {
  addColumn,
  answerWith,
  chipButton,
  openDesigner,
  rerun,
  runQuery,
  saveButton,
  saveDialog,
  settingsOf,
  setupReportClock,
  typeName,
} from '../../../test/reportScreen'

setupReportClock()

const NEEDS_GROUPING = '그룹핑한 결과로 차트를 만들 수 있습니다'
const TOO_MANY_GROUPS = '차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다'

describe('결과 탭의 차트 타일', () => {
  // 테스트 코드: RC-050
  it('결과 탭에는 차트 탭이 따로 없고 차트는 표 타일 옆의 타일이다', async () => {
    // when: 그룹핑한 결과를 조회한 디자이너를 연다
    await openGroupedDesigner(1)

    // then: 탭은 작성·결과뿐이고 결과 탭에 표 타일과 차트 타일이 있으며 아직 그린 차트는 없다
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['작성', '결과'])
    expectTab('result')
    expect(within(tile('표')).getByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(await screen.findByRole('region', { name: '차트 타일' })).toBeVisible()
    expect(renderedCharts()).toHaveLength(0)
  })

  // 테스트 코드: RC-050
  it('차트를 만들기 전에는 차트 타일에 차트 만들기 빈 상태가 보인다', async () => {
    // when: 그룹핑한 결과를 조회한 디자이너를 연다
    await openGroupedDesigner(1)

    // then: 차트 만들기 버튼이 활성이고 차트 설정 버튼은 없다
    expect(await within(tile('차트')).findByRole('button', { name: '차트 만들기' })).toBeEnabled()
    expect(chartToggle()).toBeNull()
  })

  // 테스트 코드: RC-053
  it('차트를 만들면 설정 패널이 열리고 차트 설정 버튼으로 열고 닫는다', async () => {
    // given: 그룹핑한 결과를 조회한 디자이너
    const { user } = await openGroupedDesigner(1)
    // when: 차트를 만든다
    await createChart(user)

    // then: 설정 패널이 열려 있고 종류 버튼이 보인다
    expect(chartToggle()).toHaveAttribute('aria-expanded', 'true')
    expect(kindButton('묶은 세로 막대')).toBeVisible()

    // when: 차트 설정 버튼을 눌러 패널을 닫는다
    await user.click(chartToggle() as HTMLElement)

    // then: 패널은 닫히고 그림은 남는다
    expect(chartToggle()).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('button', { name: '묶은 세로 막대' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '차트 삭제' })).not.toBeInTheDocument()
    expect(screen.getByRole('img')).toBeVisible() // 그림은 설정 패널과 무관하게 남는다

    // when: 차트 설정 버튼을 다시 눌러 패널을 연다
    await user.click(chartToggle() as HTMLElement)

    // then: 패널이 다시 열린다
    expect(chartToggle()).toHaveAttribute('aria-expanded', 'true')
    expect(kindButton('묶은 세로 막대')).toBeVisible()
  })

  // 테스트 코드: RC-053
  it('다시 조회해도 차트·열린 설정·결과 탭이 유지된다', async () => {
    // given: 그룹핑한 결과를 조회한 디자이너에서 차트를 만든 상태
    const { user } = await openGroupedDesigner(1)
    await createChart(user)

    // when: 다시 조회한다
    await rerun(user)

    // then: 결과 탭에서 차트가 다시 그려지고 설정 패널이 열려 있으며 범주 선택이 유지된다
    await waitFor(() => expect(mockControl.reportQueries()).toHaveLength(2))
    expectTab('result')
    expect(await screen.findByRole('img')).toBeVisible()
    expect(chartToggle()).toHaveAttribute('aria-expanded', 'true')
    expect(panelField('범주')).toHaveDisplayValue('Vendor')
  })

  // 테스트 코드: RC-050
  it('표만 보기로 바꾸면 차트 타일과 그림이 사라진다', async () => {
    // given: 그룹핑한 결과를 조회한 디자이너에서 차트를 만든 상태
    const { user } = await openGroupedDesigner(1)
    await createChart(user)

    // when: 표만 보기를 고른다
    await user.click(screen.getByRole('radio', { name: '표만' }))

    // then: 차트 타일과 그림이 없고 표만 보인다
    expect(screen.queryByRole('region', { name: '차트 타일' })).not.toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()
  })
})

describe('그룹핑 없는 결과 안내', () => {
  // 테스트 코드: RC-050
  it('결과에 그룹 컬럼이 없으면 그룹핑을 안내하고 차트 만들기를 막는다', async () => {
    // given: Deal code 컬럼만 조회한 디자이너
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await runQuery(user)
    await screen.findByRole('table', { name: '조회 결과' })

    // when: 차트 탭을 연다
    await openChartTab(user)

    // then: "그룹핑한 결과로 차트를 만들 수 있습니다" 안내가 보이고 차트 만들기 버튼이 비활성이다
    expect(screen.getByText(NEEDS_GROUPING)).toBeVisible()
    expect(screen.getByRole('button', { name: '차트 만들기' })).toBeDisabled()
  })

  // 테스트 코드: RC-050
  it('그룹 컬럼이 3개 이상이면 차트를 만들 수 없다고 안내한다', async () => {
    // given: 그룹 컬럼 3개를 조회한 디자이너
    const { user } = await openDesigner()
    for (const label of ['Vendor', 'Status', 'Forecast']) {
      await addColumn(user, label)
      await user.click(chipButton(['Vendor', 'Status', 'Forecast'].indexOf(label)))
      await user.click(within(settingsOf(label)).getByRole('checkbox', { name: '그룹핑' }))
    }
    await addColumn(user, '금액')
    answerWith(
      resultOf({
        columns: [
          VENDOR_COL,
          STATUS_COL,
          resultColumn({ index: 2, field: 'deal.forecast', label: 'Forecast', type: 'code', valueType: 'text', format: null, group: true }),
          amountCol(3),
        ],
        rows: [['Silverfort', 'Won', '90', 1_000_000]],
      }),
    )
    await runQuery(user)
    await screen.findByRole('table', { name: '조회 결과' })

    // when: 차트 탭을 연다
    await openChartTab(user)

    // then: "차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다" 안내가 보이고 차트 만들기 버튼이 비활성이다
    expect(screen.getByText(TOO_MANY_GROUPS)).toBeVisible()
    expect(screen.getByRole('button', { name: '차트 만들기' })).toBeDisabled()
  })
})

describe('차트 만들기와 종류', () => {
  // 테스트 코드: RC-051
  it('그룹 1개 결과의 기본 차트는 첫 값으로 그린 묶은 세로 막대다', async () => {
    // given: 그룹핑한 결과를 조회한 디자이너에서 차트 탭을 연다
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)

    // when: 차트를 만든다
    await createChart(user)

    // then: 막대 차트가 범주·값대로 그려지고 묶은 세로 막대가 눌려 있으며 차트 삭제 버튼이 보인다
    expect(lastChart().type).toBe('bar')
    expect(chartLabels()).toEqual(['Silverfort', 'Okta', '(없음)'])
    expect(chartDatasets()).toHaveLength(1)
    expect(chartDatasets()[0]?.data).toEqual([3_000_000, 1_500_000, 500_000])
    expectPressed('묶은 세로 막대')
    expect(screen.getByRole('button', { name: '차트 삭제' })).toBeVisible()
    expect(screen.queryByRole('button', { name: '차트 만들기' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-051
  it('기본 패널 값은 축 제목이 머리글이고 제목은 없으며 범례는 위다', async () => {
    // given: 그룹핑한 결과를 조회한 디자이너에서 차트 탭을 연다
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)

    // when: 차트를 만든다
    await createChart(user)

    // then: 범주가 Vendor, 축 제목이 머리글, 차트 제목이 비어 있고 범례는 위이며 첫 값만 체크되어 있다
    expect(panelField('범주')).toHaveDisplayValue('Vendor')
    expect(panelField('가로축 제목')).toHaveValue('Vendor')
    expect(panelField('세로축 제목')).toHaveValue(AMOUNT_HEADER)
    expect(panelField('차트 제목')).toHaveValue('')
    expect(panelField('범례')).toHaveDisplayValue('위')
    expect(within(valueGroup()).getByRole('checkbox', { name: AMOUNT_HEADER })).toBeChecked()
    expect(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER })).not.toBeChecked()
  })

  // 테스트 코드: RC-051
  it('그룹 2개 결과의 기본 차트는 둘째 그룹을 계열로 한 누적 세로 막대다', async () => {
    // given: 그룹 2개 결과의 디자이너에서 차트 탭을 연다
    const { user } = await openGroupedDesigner(2)
    await openChartTab(user)

    // when: 차트를 만든다
    await createChart(user)

    expectPressed('누적 세로 막대')
    // then: 누적 세로 막대이고 범주 Vendor, 계열 Status로 두 데이터셋이 누적된다
    expect(panelField('범주')).toHaveDisplayValue('Vendor')
    expect(panelField('계열')).toHaveDisplayValue('Status')
    expect(chartLabels()).toEqual(['Silverfort', 'Okta'])
    expect(chartDatasets().map((d) => d.label)).toEqual(['Won', 'Open'])
    expect(optionAt('scales', 'x', 'stacked')).toBe(true)
  })

  // 테스트 코드: RC-053
  it('차트 삭제 버튼을 누르면 차트가 없는 상태로 돌아간다', async () => {
    // given: 그룹핑한 결과를 조회한 디자이너에서 차트를 만든 상태
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)
    await createChart(user)

    // when: 차트 삭제를 누른다
    await user.click(screen.getByRole('button', { name: '차트 삭제' }))

    // then: 그림이 없고 차트 만들기 버튼이 활성이며 종류 버튼이 사라진다
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '차트 만들기' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: '묶은 세로 막대' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-054
  it('분류 13개와 고른 분류의 하위 종류만 보이고 분류를 바꾸면 그 분류로 옮겨진다', async () => {
    // when: 그룹핑한 결과를 조회한 디자이너에서 차트를 만든다
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)
    await createChart(user)

    // then: 분류 13개와 세로 막대형의 하위 종류 3개만 보이고 묶은 세로 막대가 눌려 있다
    expect(within(screen.getByRole('radiogroup', { name: '차트 분류' })).getAllByRole('radio')).toHaveLength(13)
    expect(familyRadio('세로 막대형')).toBeChecked()
    const subKinds = within(screen.getByRole('group', { name: '하위 종류' })).getAllByRole('button')
    expect(subKinds.map((b) => b.textContent)).toEqual(['묶은 세로 막대', '누적 세로 막대', '100% 누적 세로 막대'])
    expect(kindButton('묶은 세로 막대')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByRole('button', { name: '도넛형' })).not.toBeInTheDocument()

    // when: 도넛형을 고른다
    await chooseKind(user, '도넛형')

    // then: 원형 분류가 선택되고 도넛형이 눌리며 세로 막대 종류는 사라진다
    expect(familyRadio('원형')).toBeChecked()
    expect(kindButton('도넛형')).toHaveAttribute('aria-pressed', 'true')
    expect(kindButton('원형')).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByRole('button', { name: '묶은 세로 막대' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-054
  it('다른 분류를 고르면 그 분류의 첫 하위 종류로 바뀐다', async () => {
    // given: 그룹핑한 결과를 조회한 디자이너에서 차트를 만든 상태
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)
    await createChart(user)

    // when: 꺾은선형 분류를 고른다
    await user.click(familyRadio('꺾은선형'))

    // then: 꺾은선이 눌리고 꺾은선 차트로 그려진다
    expect(kindButton('꺾은선')).toHaveAttribute('aria-pressed', 'true')
    expect(lastChart().type).toBe('line')
  })

  // 테스트 코드: RC-089
  it('꺾은선은 표식 없이, 표식이 있는 꺾은선은 표식과 함께 그린다', async () => {
    // given: 그룹핑한 결과를 조회한 디자이너에서 차트를 만든 상태
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)
    await createChart(user)

    // when: 꺾은선을 고른다
    await chooseKind(user, '꺾은선')
    // then: 모든 데이터셋의 표식 반지름이 0이다
    expect(chartDatasets().every((d) => (d as Record<string, unknown>).pointRadius === 0)).toBe(true)

    // when: 표식이 있는 꺾은선을 고른다
    await chooseKind(user, '표식이 있는 꺾은선')
    // then: 모든 데이터셋의 표식 반지름이 양수다
    expect(chartDatasets().every((d) => Number((d as Record<string, unknown>).pointRadius) > 0)).toBe(true)
  })

  // 테스트 코드: RC-054
  it.each([
    ['묶은 가로 막대', 'bar'],
    ['누적 세로 막대', 'bar'],
    ['100% 누적 세로 막대', 'bar'],
    ['꺾은선', 'line'],
    ['영역', 'line'],
    ['원형', 'pie'],
    ['도넛형', 'doughnut'],
  ])('하위 종류를 고르면 바로 그 종류로 미리보기를 다시 그린다 (%s)', async (name, type) => {
    // given: 그룹핑한 결과를 조회한 디자이너에서 차트를 만든 상태
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)
    await createChart(user)

    // when: 하위 종류를 고른다
    await chooseKind(user, name)

    // then: 차트 종류가 바뀐다
    expect(lastChart().type).toBe(type)
  })

  // 테스트 코드: RC-087
  it('가로 막대는 범주 축이 y이고 축 이름이 방향에 맞게 바뀐다', async () => {
    // given: 그룹핑한 결과를 조회한 디자이너에서 차트를 만든 상태
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)
    await createChart(user)

    // when: 묶은 가로 막대를 고른다
    await chooseKind(user, '묶은 가로 막대')

    // then: indexAxis가 y이고 세로축 제목(범주)·가로축 제목(값)이 각각 범주·값 머리글이다
    expect(optionAt('indexAxis')).toBe('y')
    expect(panelField('세로축 제목(범주)')).toHaveValue('Vendor')
    expect(panelField('가로축 제목(값)')).toHaveValue(AMOUNT_HEADER)
  })

  // 테스트 코드: RC-057
  it('원형으로 바꾸면 계열 없음·값 하나·전환 없음으로 정리한다', async () => {
    // given: 그룹핑한 결과를 조회한 디자이너에서 값 2개를 고른 차트
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)
    await createChart(user)
    await user.click(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER }))
    expect(chartDatasets()).toHaveLength(2)

    // when: 원형으로 바꾼다
    await chooseKind(user, '원형')

    // then: 데이터셋 1개이고 계열·행/열 전환 칸이 잠기며 Users 값은 해제된다
    expect(chartDatasets()).toHaveLength(1)
    expect(panelField('계열')).toBeDisabled()
    expect(panelField('행/열 전환')).toBeDisabled()
    expect(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER })).not.toBeChecked()
  })

  // 테스트 코드: RC-055
  it('그룹이 2개이면 그룹 하나만 쓰는 분류가 이유와 함께 잠긴다', async () => {
    // given: 그룹 2개 결과의 디자이너에서 차트 탭을 연다
    const { user } = await openGroupedDesigner(2)
    await openChartTab(user)
    // when: 차트를 만든다
    await createChart(user)

    // then: 원형·분산형·폭포·깔때기·콤보 분류는 비활성이고 이유가 title에 있다
    for (const name of ['원형', '분산형(X, Y) 또는 거품형', '폭포', '깔때기', '콤보']) {
      expect(familyRadio(name)).toBeDisabled()
      expect(familyRadio(name)).toHaveAttribute('title', '그룹핑 컬럼이 1개 이하일 때 쓸 수 있습니다')
    }
    for (const name of ['세로 막대형', '가로 막대형', '꺾은선형', '영역형', '방사형', '트리맵', '선버스트', '히스토그램']) expect(familyRadio(name)).toBeEnabled()
  })

  // 테스트 코드: RC-055
  it('맞지 않는 하위 종류는 이유를 title로 두고 잠긴다', async () => {
    // given: 그룹 2개 결과에서 차트를 만든 상태
    const { user } = await openGroupedDesigner(2)
    await openChartTab(user)
    await createChart(user)

    // when: 히스토그램 분류를 고른다
    await user.click(familyRadio('히스토그램'))

    // then: 히스토그램은 활성이고 파레토는 비활성이며 이유가 title에 있다
    expect(kindButton('히스토그램')).toBeEnabled()
    expect(kindButton('파레토')).toBeDisabled()
    expect(kindButton('파레토')).toHaveAttribute('title', '그룹핑 컬럼이 1개 이하일 때 쓸 수 있습니다')
  })
})

describe('설정이 차트 옵션에 바로 반영됨', () => {
  async function ready(groups: 1 | 2 = 1) {
    const rendered = await openGroupedDesigner(groups)
    await openChartTab(rendered.user)
    await createChart(rendered.user)
    return rendered
  }

  // 테스트 코드: RC-059
  it('범주·계열은 그룹 컬럼만, 값은 집계 컬럼만 고를 수 있다', async () => {
    // when: 그룹 2개 결과에서 차트를 만든다 (전제: 설정 패널 열림)
    await ready(2)

    const category = within(panelField('범주')).getAllByRole('option').map((o) => o.textContent)
    const series = within(panelField('계열')).getAllByRole('option').map((o) => o.textContent)

    // then: 범주·계열 선택지에 그룹 컬럼만 있고 값 체크박스는 집계 컬럼 둘뿐이다
    expect(category).toEqual(expect.arrayContaining(['Vendor', 'Status']))
    expect(category).not.toContain(AMOUNT_HEADER)
    expect(series).toEqual(expect.arrayContaining(['Vendor', 'Status']))
    expect(series).not.toContain(USERS_HEADER)
    expect(within(valueGroup()).getAllByRole('checkbox')).toHaveLength(2)
    expect(within(valueGroup()).getByRole('checkbox', { name: AMOUNT_HEADER })).toBeVisible()
    expect(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER })).toBeVisible()
    expect(within(valueGroup()).queryByRole('checkbox', { name: 'Vendor' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-059
  it('계열 컬럼을 범주로 고르면 범주와 계열이 서로 바뀐다', async () => {
    // given: 그룹 2개 결과에서 차트를 만든 상태
    const { user } = await ready(2)

    // when: 범주를 Status로 고른다
    await user.selectOptions(panelField('범주'), 'Status')

    // then: 범주 Status, 계열 Vendor로 바뀌고 차트 라벨이 Won·Open이다
    expect(panelField('범주')).toHaveDisplayValue('Status')
    expect(panelField('계열')).toHaveDisplayValue('Vendor')
    expect(chartLabels()).toEqual(['Won', 'Open'])
  })

  // 테스트 코드: RC-059
  it('값 컬럼을 체크하면 머리글 이름의 데이터셋이 늘어난다', async () => {
    // given: 차트를 만든 상태
    const { user } = await ready()

    // when: Users 값 컬럼을 체크한다
    await user.click(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER }))

    // then: 데이터셋 이름이 금액·Users 머리글이고 둘째 데이터셋 값은 [30, 10, 5]다
    expect(chartDatasets().map((d) => d.label)).toEqual([AMOUNT_HEADER, USERS_HEADER])
    expect(chartDatasets()[1]?.data).toEqual([30, 10, 5])
  })

  // 테스트 코드: RC-082
  it('행/열 전환을 켜면 범주와 계열이 맞바뀐 차트가 그려진다', async () => {
    // given: 그룹 2개 결과에서 차트를 만든 상태
    const { user } = await ready(2)

    // when: 행/열 전환을 켠다
    await user.click(panelField('행/열 전환'))

    // then: 라벨이 Won·Open, 데이터셋 이름이 Silverfort·Okta다
    expect(chartLabels()).toEqual(['Won', 'Open'])
    expect(chartDatasets().map((d) => d.label)).toEqual(['Silverfort', 'Okta'])
  })

  // 테스트 코드: RC-065
  it('차트 제목을 입력하면 미리보기에 바로 반영된다', async () => {
    // given: 차트를 만든 상태
    const { user } = await ready()

    // when: 차트 제목을 입력한다
    await user.type(panelField('차트 제목'), 'Vendor별 금액')

    // then: 제목 플러그인이 표시되고 입력한 글자다
    expect(optionAt('plugins', 'title')).toMatchObject({ display: true, text: 'Vendor별 금액' })
  })

  // 테스트 코드: RC-065
  it.each([
    ['오른쪽', 'right'],
    ['아래', 'bottom'],
    ['위', 'top'],
  ])('범례 위치를 바꾸면 바로 반영된다 (%s)', async (label, position) => {
    // given: 차트를 만든 상태에서 범례를 다른 위치로 둔다
    const { user } = await ready()
    await user.selectOptions(panelField('범례'), label === '위' ? '아래' : '위')

    // when: 범례를 해당 위치로 고른다
    await user.selectOptions(panelField('범례'), label)

    // then: 범례가 그 위치로 표시된다
    expect(optionAt('plugins', 'legend')).toMatchObject({ display: true, position })
  })

  // 테스트 코드: RC-065
  it('범례를 숨김으로 두면 범례가 숨는다', async () => {
    // given: 차트를 만든 상태
    const { user } = await ready()

    // when: 범례를 숨김으로 고른다
    await user.selectOptions(panelField('범례'), '숨김')

    // then: 범례 display가 false다
    expect(optionAt('plugins', 'legend', 'display')).toBe(false)
  })

  // 테스트 코드: RC-085
  it('데이터 레이블을 켜면 표시되고 플러그인이 차트 인스턴스에 붙는다', async () => {
    // given: 차트를 만든 상태(데이터 레이블은 꺼짐)
    const { user } = await ready()
    expect(optionAt('plugins', 'datalabels', 'display')).toBe(false)

    // when: 데이터 레이블을 켠다
    await user.click(panelField('데이터 레이블'))

    // then: display가 true이고 차트 인스턴스 플러그인에 데이터 레이블이 들어 있다
    expect(optionAt('plugins', 'datalabels', 'display')).toBe(true)
    expect(lastChart().plugins).toContainEqual(expect.objectContaining({ id: DATALABELS_MOCK_ID }))
  })

  // 테스트 코드: RC-065
  it('축 제목을 바꾸면 바로 반영되고 비운 축 제목은 표시하지 않는다', async () => {
    // given: 차트를 만든 상태
    const { user } = await ready()

    // when: 가로축 제목을 지우고 세로축 제목에 글자를 더한다
    await user.clear(panelField('가로축 제목'))
    await user.type(panelField('세로축 제목'), '!')

    // then: 가로축 제목은 표시되지 않고 세로축 제목은 바뀐 글자다
    expect(optionAt('scales', 'x', 'title', 'display')).toBeFalsy()
    expect(optionAt('scales', 'y', 'title', 'text')).toBe(`${AMOUNT_HEADER}!`)
  })

  // 테스트 코드: RC-065
  it('값 축 최소·최대를 넣으면 반영되고 지우면 자동으로 돌아간다', async () => {
    // given: 차트를 만든 상태
    const { user } = await ready()

    // when: 세로축 최소 0, 최대 5000을 입력한다
    await user.type(panelField('세로축 최소'), '0')
    await user.type(panelField('세로축 최대'), '5000')

    // then: y 축 min·max가 0·5000이다
    expect(optionAt('scales', 'y', 'min')).toBe(0)
    expect(optionAt('scales', 'y', 'max')).toBe(5000)

    // when: 세로축 최대를 지운다
    await user.clear(panelField('세로축 최대'))

    // then: y 축에 max 키가 없다
    expect('max' in (optionAt('scales', 'y') as object)).toBe(false)
  })

  // 테스트 코드: RC-104
  it('콤보의 꺾은선 계열을 계열 표에서 보조 축에 둘 수 있다', async () => {
    // given: 콤보로 바꾸고 Users를 값에 더한 차트
    const { user } = await ready()
    await chooseKind(user, '콤보')
    await user.click(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER }))

    // when: Users 계열의 보조 축을 체크한다
    await user.click(screen.getByRole('checkbox', { name: `${USERS_HEADER} 보조 축` }))

    // then: 막대 + 보조 축(y1, 오른쪽) 꺾은선으로 그려진다
    expect(lastChart().type).toBe('bar')
    expect(chartDatasets()).toHaveLength(2)
    expect((chartDatasets()[1] as Record<string, unknown>).yAxisID).toBe('y1')
    expect(optionAt('scales', 'y1', 'position')).toBe('right')
  })

  // 테스트 코드: RC-066
  it('종류가 쓰지 않는 칸은 이유와 함께 잠긴다', async () => {
    // given: 차트를 만든 상태
    const { user } = await ready()

    // when: 묶은 세로 막대를 고른다
    await user.click(kindButton('묶은 세로 막대'))

    // then: 보조 축 체크박스가 비활성이고 title에 콤보 안내가 있다
    expect(panelField('보조 축')).toBeDisabled()
    expect(panelField('보조 축')).toHaveAttribute('title', expect.stringMatching(/콤보/))
  })

  // 테스트 코드: RC-073
  it('차트 그림은 결과 표를 가리키는 접근성 이름을 가진다', async () => {
    // when: 그룹 1개 결과에서 차트를 만든다 (전제: 설정 패널 열림)
    await ready()

    // then: 그림의 접근성 이름에 "같은 값이 결과 표에 있습니다"가 있다
    expect(screen.getByRole('img')).toHaveAccessibleName(/같은 값이 결과 표에 있습니다/)
  })
})

describe('숫자 단위', () => {
  // 테스트 코드: RC-086
  it('금액은 원 단위 그대로 그린다', async () => {
    // given: 그룹핑한 결과를 조회한 디자이너에서 차트 탭을 연다
    const { user } = await openGroupedDesigner(1)
    await openChartTab(user)

    // when: 차트를 만든다
    await createChart(user)

    // then: 첫 데이터셋 값이 원 단위 그대로다
    expect(chartDatasets()[0]?.data).toEqual([3_000_000, 1_500_000, 500_000])
  })
})

describe('컬럼 편집과 차트', () => {
  // 테스트 코드: RC-070
  it('범주 컬럼을 빼도 안내만 뜨고 나머지 설정은 유지된다', async () => {
    // given: 그룹 2개 결과에서 차트를 만들고 제목을 입력한 상태
    const { user } = await openGroupedDesigner(2)
    await openChartTab(user)
    await createChart(user)
    await user.type(panelField('차트 제목'), '유지할 제목')

    // when: 작성 탭에서 범주 컬럼 Vendor를 뺀다
    await showTab(user, 'design')
    await user.click(screen.getByRole('button', { name: 'Vendor 빼기' }))
    await openChartTab(user)

    // then: "범주 열을 고르세요" 안내가 보이고 제목은 그대로다
    expect(screen.getByText('범주 열을 고르세요')).toBeVisible()
    expect(panelField('차트 제목')).toHaveValue('유지할 제목')
  })

  // 테스트 코드: RC-069
  it('불완전한 차트를 저장하다 거절되면 결과 탭으로 옮기고 설정 패널을 연다', async () => {
    // given: 차트를 만든 뒤 범주 컬럼을 빼고 다시 조회한 새 리포트 설계(작성 탭)
    const { user } = await openGroupedDesigner(2)
    await openChartTab(user)
    await createChart(user)
    await showTab(user, 'design')
    await user.click(screen.getByRole('button', { name: 'Vendor 빼기' }))
    answerWith(resultOf({ columns: [{ ...STATUS_COL, index: 0 }, amountCol(1), usersCol(2)], rows: [['Won', 1_000_000, 10]] }))
    await runQuery(user)
    await waitFor(() => expect(mockControl.reportQueries()).toHaveLength(2))
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await showTab(user, 'design') // 저장 전 탭을 작성 탭으로 두고, 위반 위치(차트)를 따라 결과 탭으로 옮겨지는지 본다

    // when: 이름을 입력해 저장한다
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '차트 있는 새 리포트')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 결과 탭으로 옮겨지고 설정 패널이 열리며 차트 칸에 서버 위반이 보이고 "결과 (고칠 곳 1)"이며 저장 요청은 한 번뿐이다
    await waitFor(() => expect(resultTab()).toHaveAttribute('aria-selected', 'true'))
    expect(chartToggle()).toHaveAttribute('aria-expanded', 'true')
    expect(await within(tile('차트')).findByText(/범주 열은 그룹핑한 컬럼이어야 합니다/)).toBeVisible()
    expect(resultTab()).toHaveTextContent('결과 (고칠 곳 1)')
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'create')).toHaveLength(1)
  })
})

describe('큰 결과', () => {
  const TOO_MANY = '범주가 너무 많아 차트를 그리지 않습니다(최대 1,000개). 조건을 좁히세요'
  const TRUNCATED = '최대 행 수 제한으로 표시된 행만 차트에 그렸습니다'

  /** Vendor 그룹 + 금액 + Users count, 범주 n개. */
  const manyCategories = (n: number) =>
    resultOf({
      columns: [VENDOR_COL, amountCol(1), usersCol(2)],
      rows: Array.from({ length: n }, (_, i) => [`v${i}`, 1_000_000, 1]),
    })

  async function chartOf(result: ReturnType<typeof manyCategories>) {
    const { user } = await openGroupedDesigner(1)
    answerWith(result)
    await rerun(user)
    await waitFor(() => expect(mockControl.reportQueries()).toHaveLength(2))
    await openChartTab(user)
    await user.click(await screen.findByRole('button', { name: '차트 만들기' }))
    return user
  }

  // 테스트 코드: RC-084
  it('차트 점이 1,000개를 넘으면 그리지 않고 조건을 좁히라고 안내한다', async () => {
    // when: 범주 1,001개 결과에서 차트를 만든다
    await chartOf(manyCategories(1001))

    // then: "범주가 너무 많아…" 안내가 보이고 그림이 없다
    expect(await screen.findByText(TOO_MANY)).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-084
  it('점이 정확히 1,000개이면 그린다', async () => {
    // when: 범주 1,000개 결과에서 차트를 만든다
    await chartOf(manyCategories(1000))

    // then: 그림이 보이고 안내가 없으며 라벨이 1,000개다
    expect(await screen.findByRole('img')).toBeVisible()
    expect(screen.queryByText(TOO_MANY)).not.toBeInTheDocument()
    expect(chartLabels()).toHaveLength(1000)
  })

  // 테스트 코드: RC-073
  it('행 한도로 잘린 결과이면 표시된 행만 그렸다고 알린다', async () => {
    // when: 행 한도로 잘린 결과에서 차트를 만든다
    await chartOf({ ...manyCategories(3), truncated: true, totalCount: 5000 })

    // then: 그림이 보이고 "최대 행 수 제한으로 표시된 행만 차트에 그렸습니다" 안내가 있다
    expect(await screen.findByRole('img')).toBeVisible()
    expect(screen.getByText(TRUNCATED)).toBeVisible()
  })

  // 테스트 코드: RC-073
  it('잘리지 않은 결과에는 잘림 안내가 없다', async () => {
    // when: 잘리지 않은 결과에서 차트를 만든다
    await chartOf(manyCategories(3))

    // then: 그림이 그려지고 잘림 안내가 없다
    await screen.findByRole('img')
    expect(screen.queryByText(TRUNCATED)).not.toBeInTheDocument()
  })
})
