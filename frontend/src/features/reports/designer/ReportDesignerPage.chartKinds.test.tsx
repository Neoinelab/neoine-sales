import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { lastChart } from '../../../test/chartMock'
import {
  AMOUNT_HEADER,
  chartDatasets,
  chartLabels,
  chooseKind,
  createChart,
  expectPressed,
  familyRadio,
  openChartTab,
  openGroupedDesigner,
  optionAt,
  panelField,
  USERS_HEADER,
  valueGroup,
} from '../../../test/reportChart'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import { addColumn, answerWith, openDesigner, runQuery, saveButton, saveDialog, setupReportClock, typeName } from '../../../test/reportScreen'

setupReportClock()

/** 그룹핑 없는 결과: 0 = Deal code(텍스트), 1 = Users count(숫자 필드, 집계 없음). 값 0..10. */
const UNGROUPED = resultOf({
  columns: [
    resultColumn({ index: 0, field: 'deal.code', label: 'Deal code', type: 'text', valueType: 'text', format: null }),
    resultColumn({ index: 1, field: 'deal.users', label: 'Users count', type: 'number', valueType: 'integer', format: null, unit: null, aggregate: null }),
  ],
  rows: Array.from({ length: 11 }, (_, i) => [`D-${i}`, i]),
})

async function openUngrouped() {
  const rendered = await openDesigner()
  answerWith(UNGROUPED)
  await addColumn(rendered.user, 'Deal code')
  await addColumn(rendered.user, 'Users count')
  await runQuery(rendered.user)
  await screen.findByRole('table', { name: '조회 결과' })
  await openChartTab(rendered.user)
  return rendered
}

describe('그룹핑 없는 리포트의 히스토그램', () => {
  // 테스트 코드: RC-050
  it('그룹핑이 없으면 히스토그램만 만들 수 있다고 안내하고 차트 만들기는 쓸 수 있다', async () => {
    // when: Deal code와 숫자 컬럼만 조회한 디자이너를 연다
    await openUngrouped()

    // then: 차트 만들기 버튼이 활성이고 "그룹핑이 없으면 히스토그램만 만들 수 있습니다" 안내가 보인다
    expect(await screen.findByRole('button', { name: '차트 만들기' })).toBeEnabled()
    expect(screen.getByText('그룹핑이 없으면 히스토그램만 만들 수 있습니다')).toBeVisible()
  })

  // 테스트 코드: RC-052
  it('그룹핑 없는 결과의 기본 차트는 숫자 컬럼의 히스토그램이다', async () => {
    // given: Deal code와 숫자 컬럼만 조회한 디자이너
    const { user } = await openUngrouped()

    // when: 차트를 만든다
    await createChart(user)

    expectPressed('히스토그램')
    // then: 히스토그램이 눌리고 막대 차트로 그려지며 구간 개수의 합이 표본 수다
    expect(familyRadio('히스토그램')).toBeChecked()
    expect(lastChart().type).toBe('bar')
    expect((chartDatasets()[0]?.data as number[]).reduce((a, b) => a + b, 0)).toBe(11)
  })

  // 테스트 코드: RC-052
  it('그룹핑 없는 히스토그램을 저장하면 범주 없는 히스토그램으로 다시 읽힌다', async () => {
    // given: Deal code와 숫자 컬럼만 조회한 디자이너에서 차트를 만든 상태
    const { user } = await openUngrouped()
    await createChart(user)

    await waitFor(() => expect(saveButton()).toBeEnabled())
    // when: 이름을 입력해 저장한다
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '히스토그램 리포트')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 저장된 리포트의 차트 종류가 histogram이고 차트 범주가 null이다
    await waitFor(async () => expect((await gateway.reports.list()).some((r) => r.name === '히스토그램 리포트')).toBe(true))
    const saved = (await gateway.reports.list()).find((r) => r.name === '히스토그램 리포트')
    expect(saved?.chartKind).toBe('histogram')
    expect((await gateway.reports.get(saved?.id ?? 0)).chart).toMatchObject({ kind: 'histogram', category: null })
  })

  // 테스트 코드: RC-060
  it('히스토그램은 범주 칸이 이유와 함께 잠긴다', async () => {
    // given: Deal code와 숫자 컬럼만 조회한 디자이너
    const { user } = await openUngrouped()

    // when: 차트를 만든다
    await createChart(user)

    // then: 범주 칸이 비활성이고 "이 차트는 범주 열을 쓰지 않습니다" 안내가 보인다
    expect(panelField('범주')).toBeDisabled()
    expect(screen.getByText('이 차트는 범주 열을 쓰지 않습니다')).toBeVisible()
  })

  // 테스트 코드: RC-061
  it('구간 수를 입력하면 그 구간 수로 다시 그린다', async () => {
    // given: Deal code와 숫자 컬럼만 조회한 디자이너에서 차트를 만든 상태
    const { user } = await openUngrouped()
    await createChart(user)

    // when: 구간 수 방식에 5를 입력한다
    await user.selectOptions(panelField('구간 방식'), '구간 수')
    await user.type(panelField('구간 수'), '5')

    // then: 구간 이름 5개와 개수 3·2·2·2·2로 그려진다
    expect(chartLabels()).toEqual(['[0, 2]', '(2, 4]', '(4, 6]', '(6, 8]', '(8, 10]'])
    expect(chartDatasets()[0]?.data).toEqual([3, 2, 2, 2, 2])
  })

  // 테스트 코드: RC-061
  it('자동 방식에서는 구간 수·너비 칸이 잠겨 있다', async () => {
    // given: Deal code와 숫자 컬럼만 조회한 디자이너
    const { user } = await openUngrouped()
    // when: 차트를 만든다
    await createChart(user)

    // then: 구간 방식이 자동이고 구간 수·너비 칸이 비활성이다
    expect(panelField('구간 방식')).toHaveDisplayValue('자동')
    expect(panelField('구간 수')).toBeDisabled()
    expect(panelField('구간 너비')).toBeDisabled()
  })

  // 테스트 코드: RC-068
  it('잘못된 구간 수는 칸 옆에 안내가 보인다', async () => {
    // given: Deal code와 숫자 컬럼만 조회한 디자이너에서 차트를 만든 상태
    const { user } = await openUngrouped()
    await createChart(user)

    // when: 구간 수 방식에 0을 입력한다
    await user.selectOptions(panelField('구간 방식'), '구간 수')
    await user.type(panelField('구간 수'), '0')

    // then: "구간 수는 1~100의 정수입니다" 안내가 보이고 칸이 aria-invalid다
    expect(screen.getByText('구간 수는 1~100의 정수입니다')).toBeVisible()
    expect(panelField('구간 수')).toHaveAttribute('aria-invalid', 'true')
  })
})

describe('종류별 옵션', () => {
  async function ready(groups: 1 | 2 = 1) {
    const rendered = await openGroupedDesigner(groups)
    await openChartTab(rendered.user)
    await createChart(rendered.user)
    return rendered
  }

  // 테스트 코드: RC-062
  it('합계 막대 옵션은 폭포에만 있고 켜면 합계 막대가 그려진다', async () => {
    // given: 그룹 1개 결과에서 차트를 만든 상태
    const { user } = await ready()
    // when: 폭포를 고른다
    await chooseKind(user, '폭포')
    // then: 합계 항목이 없다(증가·감소)
    expect(chartDatasets().map((d) => d.label)).toEqual(['증가', '감소'])

    // when: "마지막에 합계 막대"를 켠다
    await user.click(screen.getByRole('checkbox', { name: '마지막에 합계 막대' }))

    // then: 합계 데이터셋과 합계 라벨이 생긴다
    expect(chartDatasets().map((d) => d.label)).toEqual(['증가', '감소', '합계'])
    expect(chartLabels()).toEqual(['Silverfort', 'Okta', '(없음)', '합계'])
  })

  // 테스트 코드: RC-062
  it('폭포가 아닌 종류에는 합계 막대 옵션이 없다', async () => {
    // when: 그룹 1개 결과에서 차트를 만든다 (전제: 묶은 세로 막대)
    await ready()

    // then: 합계 막대 체크박스가 없다
    expect(screen.queryByRole('checkbox', { name: '마지막에 합계 막대' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RC-064
  it('콤보는 첫 프리셋으로 계열 표를 채우고 다른 프리셋을 적용할 수 있다', async () => {
    // when: 콤보로 바꾸고 Users를 값에 더한다
    const { user } = await ready()
    await chooseKind(user, '콤보')
    await user.click(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER }))

    // then: 프리셋 선택이 "묶은 세로 막대 - 꺾은선"이다
    expect(panelField('콤보 프리셋')).toHaveDisplayValue('묶은 세로 막대 - 꺾은선')

    // when: "묶은 세로 막대 - 보조 축의 꺾은선" 프리셋을 고른다
    await user.selectOptions(panelField('콤보 프리셋'), '묶은 세로 막대 - 보조 축의 꺾은선')

    // then: 꺾은선 계열이 y1(오른쪽 보조 축)에 놓인다
    expect((chartDatasets()[1] as Record<string, unknown>).yAxisID).toBe('y1')
    expect(optionAt('scales', 'y1', 'position')).toBe('right')
  })

  // 테스트 코드: RC-068
  it('모든 계열을 보조 축에 두면 서버와 같은 문구로 안내한다', async () => {
    // given: 콤보로 바꾸고 Users를 값에 더한 차트
    const { user } = await ready()
    await chooseKind(user, '콤보')
    await user.click(within(valueGroup()).getByRole('checkbox', { name: USERS_HEADER }))

    // when: 두 계열 모두 보조 축을 체크한다
    await user.click(screen.getByRole('checkbox', { name: `${AMOUNT_HEADER} 보조 축` }))
    await user.click(screen.getByRole('checkbox', { name: `${USERS_HEADER} 보조 축` }))

    // then: "모든 계열을 보조 축에 둘 수 없습니다"가 보인다
    expect(screen.getByText('모든 계열을 보조 축에 둘 수 없습니다')).toBeVisible()
  })
})
