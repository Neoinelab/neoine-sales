import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { ReportResult } from '../../../shared/model/reportTypes'
import { mockControl } from '../../../test/fake/default'
import { seedVendorId } from '../../../test/fixtures/vendors'
import { groupedAmountResult, resultColumn, resultOf } from '../../../test/reportDesigner'
import { showTab, STALE_NOTE } from '../../../test/reportLayout'
import {
  addColumn,
  addCondition,
  chipButton,
  chipTexts,
  lastQuery,
  openAndRun,
  openDesigner,
  rerun,
  resultTable,
  runButton,
  runQuery,
  settingsOf,
  tableTexts,
  setupReportClock,
} from '../../../test/reportScreen'

setupReportClock()

describe('앞 N자 입력 검사', () => {
  // 테스트 코드: RQ-077
  it('앞 N자의 N이 비면 요청 없이 N을 고치라고 안내한다', async () => {
    // given: 앞 N자를 켜고 N을 비운 Deal 이름 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    await user.click(chipButton(0))
    await user.click(within(settingsOf('Deal 이름')).getByRole('checkbox', { name: '앞 N자만 보기' }))
    await user.clear(within(settingsOf('Deal 이름')).getByLabelText('앞 N자의 N'))

    // when: 조회한다
    await runQuery(user)

    // then: 요청이 없고 N 칸에 1~200 정수 안내와 오류 표시가 보인다
    expect(mockControl.reportQueries()).toEqual([])
    expect(within(settingsOf('Deal 이름')).getByText('1~200 사이 정수를 입력하세요')).toBeVisible()
    expect(within(settingsOf('Deal 이름')).getByLabelText('앞 N자의 N')).toBeInvalid()
  })

  // 테스트 코드: RQ-086
  it('N이 올바르면 포맷 키 없이 앞 N자만 보낸다', async () => {
    // given: 앞 N자를 켠(N 20) Deal 이름 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    await user.click(chipButton(0))
    await user.click(within(settingsOf('Deal 이름')).getByRole('checkbox', { name: '앞 N자만 보기' }))

    // when: 조회한다
    await runQuery(user)

    // then: 요청 컬럼에 앞 N자 20이 있고 포맷 키는 없다
    expect(mockControl.reportQueries()).toEqual([
      { columns: [{ field: 'deal.name', prefixLength: 20, group: false }], conditions: [], combine: 'and', rowLimit: 1000 },
    ])
  })
})

describe('조회 요청', () => {
  // 테스트 코드: RQ-086, RQ-089
  it('설계한 대로 요청을 보내고 결과 표를 보인다', async () => {
    // given: Vendor 그룹, 금액 내림차순 정렬, Silverfort Vendor 조건을 설계했다
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액')
    await user.click(chipButton(0))
    await user.click(within(settingsOf('Vendor')).getByRole('checkbox', { name: '그룹핑' }))
    await addCondition(user, 'Vendor')
    await user.click(screen.getByRole('button', { name: /^조건 1 값/ }))
    await user.click(within(screen.getByRole('group', { name: '조건 1 값' })).getByRole('checkbox', { name: 'Silverfort' }))
    await user.click(chipButton(1))
    await user.selectOptions(within(settingsOf('금액')).getByRole('combobox', { name: '정렬' }), 'desc')

    // when: 조회한다
    await runQuery(user)

    // then: 결과 표가 보이고 요청이 설계와 같으며 표 행이 서버 결과와 같다
    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(mockControl.reportQueries()).toEqual([
      {
        columns: [
          { field: 'deal.vendor', group: true },
          { field: 'deal.amount', group: false, aggregate: 'sum', sort: 'desc' },
        ],
        conditions: [{ field: 'deal.vendor', operator: 'in', value: [seedVendorId('Silverfort')] }],
        combine: 'and',
        rowLimit: 1000,
      },
    ])
    expect(tableTexts()).toEqual([
      ['Vendor 1', '1,000'],
      ['Vendor 2', '2,000'],
      ['Vendor 3', '3,000'],
    ])
  })

  // 테스트 코드: RQ-074
  it('정렬은 컬럼 설정에서 고르고(기본 정렬 없음) 조회 줄에는 없다', async () => {
    // given: Deal code 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')

    // when: 컬럼 설정의 정렬 선택을 본다
    const select = within(settingsOf('Deal code')).getByRole('combobox', { name: '정렬' })

    // then: 정렬 없음·오름차순·내림차순이고 기본은 정렬 없음, 조회 줄에는 정렬 선택이 없고 최대 행·조회만 있다
    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['정렬 없음', '오름차순', '내림차순'])
    expect(select).toHaveDisplayValue('정렬 없음')
    expect(screen.getAllByRole('combobox', { name: '정렬' })).toHaveLength(1)
    expect(screen.queryByRole('combobox', { name: '정렬 방향' })).not.toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: '최대 행' })).toBeVisible()
    expect(runButton()).toBeVisible()
    // when: 내림차순을 고른다
    await user.selectOptions(select, 'desc')
    // then: 칩에 내림 배지가 붙고 우선순위 번호는 없다
    expect(chipTexts()[0]).toContain('▼ 내림')
    expect(chipTexts()[0]).not.toMatch(/내림 \d/)
  })

  // 테스트 코드: RQ-076
  it('정렬한 칩에만 배지가 붙고 둘 이상 정렬하면 우선순위 번호가 붙는다', async () => {
    // given: Deal code, Deal 이름, Solution 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')
    await addColumn(user, 'Solution')
    // when: Solution을 오름차순으로 정렬한다
    await user.selectOptions(within(settingsOf('Solution')).getByRole('combobox', { name: '정렬' }), 'asc')
    // then: Solution 칩에 번호 없는 오름 배지가 붙는다
    expect(chipTexts()[2]).toContain('▲ 오름')
    expect(chipTexts()[2]).not.toMatch(/오름 \d/)

    // when: Deal code도 내림차순으로 정렬한다
    await user.click(chipButton(0))
    await user.selectOptions(within(settingsOf('Deal code')).getByRole('combobox', { name: '정렬' }), 'desc')

    // then: Deal code는 내림 1, Deal 이름은 배지 없음, Solution은 오름 2다
    expect(chipTexts()[0]).toContain('▼ 내림 1')
    expect(chipTexts()[1]).not.toMatch(/[▲▼]/)
    expect(chipTexts()[2]).toContain('▲ 오름 2')
  })

  // 테스트 코드: RQ-086
  it('컬럼 정렬을 컬럼 순서대로 보낸다', async () => {
    // given: Deal code 오름차순, Deal 이름 내림차순 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await user.selectOptions(within(settingsOf('Deal code')).getByRole('combobox', { name: '정렬' }), 'asc')
    await addColumn(user, 'Deal 이름')
    await user.selectOptions(within(settingsOf('Deal 이름')).getByRole('combobox', { name: '정렬' }), 'desc')

    // when: 조회한다
    await runQuery(user)

    // then: 요청 컬럼에 정렬이 컬럼 순서대로 담긴다
    await screen.findByRole('table', { name: '조회 결과' })
    expect(mockControl.reportQueries()).toEqual([
      {
        columns: [
          { field: 'deal.code', group: false, sort: 'asc' },
          { field: 'deal.name', group: false, sort: 'desc' },
        ],
        conditions: [],
        combine: 'and',
        rowLimit: 1000,
      },
    ])
  })

  // 테스트 코드: RQ-086
  it('정렬한 컬럼을 빼면 정렬과 배지도 함께 없어진다', async () => {
    // given: Deal 이름을 오름차순으로 정렬한 설계
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')
    await user.selectOptions(within(settingsOf('Deal 이름')).getByRole('combobox', { name: '정렬' }), 'asc')

    // when: Deal 이름 컬럼을 빼고 조회한다
    await user.click(screen.getByRole('button', { name: 'Deal 이름 빼기' }))
    await runQuery(user)

    await screen.findByRole('table', { name: '조회 결과' })
    // when: 작성 탭으로 옮긴다
    await showTab(user, 'design')
    // then: 칩에 정렬 배지가 없고 요청 컬럼은 Deal code 하나다
    expect(chipTexts()[0]).not.toMatch(/[▲▼]/)
    expect(lastQuery().columns).toEqual([{ field: 'deal.code', group: false }])
  })

  // 테스트 코드: RQ-087
  it('최대 행은 100·1,000·10,000 중 고르고 기본은 1,000이며 고른 값을 보낸다', async () => {
    // given: Deal code 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    // when: 최대 행 선택지를 본다
    const select = screen.getByRole('combobox', { name: '최대 행' })

    // then: 100·1,000·10,000이고 기본은 1,000이다
    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['100', '1,000', '10,000'])
    expect(select).toHaveDisplayValue('1,000')

    // when: 100을 고르고 조회한다
    await user.selectOptions(select, '100')
    await runQuery(user)

    // then: 요청의 행 수 제한이 100이다
    await screen.findByRole('table', { name: '조회 결과' })
    expect(mockControl.reportQueries()[0]?.rowLimit).toBe(100)
  })

  // 테스트 코드: RQ-085
  it('읽을 수 없는 입력이 있으면 요청을 보내지 않고 고치면 보낸다', async () => {
    // given: Users count 조건에 1.5를 입력했다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Users count')
    const input = screen.getByRole('textbox', { name: '조건 1 값' })
    await user.type(input, '1.5')

    // when: 조회한다
    await runQuery(user)

    // then: 요청이 없고 값 칸이 오류 표시와 정수 안내를 가진다
    expect(mockControl.reportQueries()).toHaveLength(0)
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription(/정수로 입력하세요/)

    // when: 값을 15로 고치고 다시 조회한다
    await user.clear(input)
    await user.type(input, '15')
    await runQuery(user)

    // then: 요청이 한 번 가고 오류 표시가 사라진다
    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(mockControl.reportQueries()).toHaveLength(1)

    // when: 작성 탭으로 옮긴다
    await showTab(user, 'design')
    // then: 값 칸의 오류 표시가 사라져 있다
    expect(screen.getByRole('textbox', { name: '조건 1 값' })).not.toHaveAttribute('aria-invalid', 'true')
  })

  // 테스트 코드: RQ-085
  it('입력 안내 문구가 정수 규칙과 빈 목록을 각각 알려준다', async () => {
    // given: 금액 값 abc, 선택 없는 Vendor 조건
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, '금액')
    await addCondition(user, 'Vendor')
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), 'abc')

    // when: 조회한다
    await runQuery(user)

    // then: 정수 안내와 하나 이상 선택하라는 안내가 보이고 요청이 없다
    expect(screen.getByText('정수로 입력하세요')).toBeVisible()
    expect(screen.getByText('하나 이상 선택하세요')).toBeVisible()
    expect(mockControl.reportQueries()).toHaveLength(0)
  })

  // 테스트 코드: RQ-088
  it('조회 중에는 조회 중… 버튼이 꺼져 두 번째 조회를 막는다', async () => {
    // given: 끝나지 않는 조회 요청을 설정한 Deal code 설계
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    let release: (result: ReportResult) => void = () => undefined
    mockControl.setReportQueryHandler(() => new Promise<ReportResult>((resolve) => (release = resolve)))

    // when: 조회한다
    await runQuery(user)

    // then: 조회 중… 버튼이 보이고 꺼져 있다
    const running = await screen.findByRole('button', { name: '조회 중…' })
    expect(running).toBeDisabled()

    // when: 서버가 결과를 돌려준다
    release(resultOf())

    // then: 결과 표가 보이고 작성 탭에서 조회 버튼이 다시 켜진다
    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()

    // when: 작성 탭으로 옮긴다
    await showTab(user, 'design')
    // then: 조회 버튼이 다시 켜져 있다
    expect(runButton()).toBeEnabled()
  })
})

describe('결과 표', () => {
  // 테스트 코드: RQ-094
  it('총 행 수와 조회 시간을 보인다', async () => {
    // when: 3행·210ms 결과로 조회한다
    await openAndRun(resultOf({ rows: [['A'], ['B'], ['C']], elapsedMs: 210 }), 'Deal code')

    // then: 총 3행 · 조회 0.21초가 보인다
    expect(screen.getByText(/총 3행 · 조회 0\.21초/)).toBeVisible()
  })

  // 테스트 코드: RQ-096
  it('금액은 원 단위 정수로 머리글에 (원)을 붙이고 숫자는 오른쪽 정렬하며 빈 값은 —이다', async () => {
    // when: 금액 합계 결과로 조회한다 (전제: 값 1,234,500·999,999·null)
    await openAndRun(groupedAmountResult([['Silverfort', 1_234_500], ['Okta', 999_999], ['Zscaler', null]], null), 'Vendor')

    // then: 머리글이 금액 합계 (원)이고 값이 콤마 정수, 빈 값이 —이다
    expect(within(resultTable()).getByRole('columnheader', { name: /^금액 합계\s?\(원\)$/ })).toBeVisible()
    expect(within(resultTable()).getByRole('columnheader', { name: 'Vendor' })).toBeVisible()
    expect(tableTexts()).toEqual([
      ['Silverfort', '1,234,500'],
      ['Okta', '999,999'],
      ['Zscaler', '—'],
    ])
    // then: 숫자 칸과 머리글만 오른쪽 정렬 클래스를 가진다
    const [firstRow] = within(resultTable()).getAllByRole('row').slice(1)
    const cells = within(firstRow as HTMLElement).getAllByRole('cell')
    expect(cells[1]).toHaveClass('report-num')
    expect(cells[0]).not.toHaveClass('report-num')
    expect(within(resultTable()).getByRole('columnheader', { name: /금액 합계/ })).toHaveClass('report-num')
  })

  // 테스트 코드: RQ-097
  it('날짜와 시각을 서버 오프셋 벽시계와 앱 시계 기준으로 보인다', async () => {
    // when: 시각(ymd_hm)과 상대 시각 날짜 열의 결과로 조회한다 (전제: 앱 시계 2026-10-15)
    await openAndRun(
      resultOf({
        today: '2026-10-15',
        columns: [
          resultColumn({ index: 0, field: 'deal.created_at', label: '등록', type: 'datetime', valueType: 'datetime', format: 'ymd_hm' }),
          resultColumn({ index: 1, field: 'deal.expected_close', label: '마감', type: 'date', valueType: 'date', format: 'relative' }),
        ],
        rows: [['2026-04-01T00:30:00+09:00', '2026-10-24']],
      }),
      'Deal code',
    )

    // then: 시각은 서버 오프셋 벽시계, 날짜는 3일 전으로 보인다
    expect(tableTexts()).toEqual([['2026-04-01 00:30', '3일 전']])
  })

  // 테스트 코드: RQ-095
  it('합계 행은 합계가 있는 결과에서 켜고 끄며 금액을 원으로 보인다', async () => {
    // given: 합계가 있는 그룹핑 결과
    const result = groupedAmountResult(
      [
        ['A', 1_000_000],
        ['B', 3_000_000],
      ],
      [null, 4_000_000],
    )
    // when: 조회한다
    const { user } = await openAndRun(result, 'Vendor')

    // then: 합계 행이 켜지기 전에는 데이터 행만 보이고 합계 체크는 꺼져 있다
    expect(tableTexts()).toEqual([
      ['A', '1,000,000'],
      ['B', '3,000,000'],
    ])
    const toggle = screen.getByRole('checkbox', { name: '합계 행' })
    expect(toggle).not.toBeChecked()

    // when: 합계 행을 켠다
    await user.click(toggle)

    // then: 마지막에 합계 행이 tfoot으로 붙는다
    expect(tableTexts()).toEqual([
      ['A', '1,000,000'],
      ['B', '3,000,000'],
      ['합계', '4,000,000'],
    ])
    expect(within(resultTable()).getAllByRole('row').at(-1)?.closest('tfoot')).not.toBeNull()

    // when: 합계 행을 끈다
    await user.click(toggle)

    // then: 데이터 행 둘만 남는다
    expect(tableTexts()).toHaveLength(2)
  })

  // 테스트 코드: RQ-096
  it('원 단위 표기는 금액 열 머리글에만 붙는다', async () => {
    // when: Vendor와 금액 합계 결과로 조회한다
    await openAndRun(groupedAmountResult([['A', 1_000_000]], [null, 1_000_000]), 'Vendor')

    // then: Vendor 머리글에는 단위가 없고 금액 합계 머리글에만 (원)이 붙는다
    const headers = within(resultTable()).getAllByRole('columnheader').map((h) => h.textContent)

    expect(headers[0]).toContain('Vendor')
    expect(headers[1]).toMatch(/금액 합계\s?\(원\)/)
  })

  // 테스트 코드: RQ-096
  it('합계 행의 금액도 원 단위 정수이고 구성비·소수 표기가 없다', async () => {
    // given: 금액 합계 결과
    const result = groupedAmountResult([['A', 123_456_789]], [null, 123_456_789])
    // when: 조회하고 합계 행을 켠다
    const { user } = await openAndRun(result, 'Vendor')
    await user.click(screen.getByRole('checkbox', { name: '합계 행' }))

    // then: 데이터 행과 합계 행이 모두 콤마 정수다
    expect(tableTexts()).toEqual([
      ['A', '123,456,789'],
      ['합계', '123,456,789'],
    ])
  })

  // 테스트 코드: RQ-095
  it('합계가 없는 결과에는 합계 행 체크박스가 없다', async () => {
    // when: 합계 없는 결과로 조회한다
    await openAndRun(resultOf({ rows: [['A']], totals: null }), 'Deal code')

    // then: 합계 행 체크박스가 없다
    expect(screen.queryByRole('checkbox', { name: '합계 행' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-095
  it('Deal당 한 번 센 결과는 합계 행을 켰을 때 그룹 합이 합계보다 클 수 있다고 안내한다', async () => {
    // when: Action 행 범위에서 Deal 숫자를 한 번씩 센 그룹핑 결과를 조회한다
    const { user } = await openAndRun(
      { ...groupedAmountResult([['A', 1000]], [null, 1000]), rowScope: 'action', actionFilter: 'join', dealNumbersOnce: true },
      'Vendor',
    )
    // then: 합계 행이 꺼져 있을 때는 안내가 없다
    expect(screen.queryByText(/그룹 값의 합이 합계 행보다 클 수 있습니다/)).not.toBeInTheDocument()

    // when: 합계 행을 켠다
    await user.click(screen.getByRole('checkbox', { name: '합계 행' }))

    // then: 그룹 합이 합계 행보다 클 수 있다는 안내가 보인다
    expect(screen.getByText(/한 Deal이 여러 그룹에 나오면 그룹마다 한 번씩 더하므로 그룹 값의 합이 합계 행보다 클 수 있습니다/)).toBeVisible()
  })

  // 테스트 코드: RQ-098
  it('앞 N자는 데이터 칸만 자르고 title에 전체 값을 두며 합계 행은 자르지 않는다', async () => {
    // given: 앞 N자 3이 걸린 Vendor 열과 숫자 열, 합계 행이 있는 결과
    const result = resultOf({
      columns: [
        resultColumn({ index: 0, field: 'deal.vendor', label: 'Vendor', type: 'code', group: true, prefixLength: 3 }),
        resultColumn({ index: 1, field: 'deal.users', label: 'Users count 합계', type: 'number', valueType: 'integer', format: null, unit: null, aggregate: 'sum', prefixLength: 3 }),
      ],
      rows: [['ABCDEF', 1_234_567]],
      totals: [null, 1_234_567],
    })
    // when: 조회하고 합계 행을 켠다
    const { user } = await openAndRun(result, 'Vendor')
    await user.click(screen.getByRole('checkbox', { name: '합계 행' }))

    // then: 데이터 칸은 ABC…·1,2…로 잘리고 title에 전체 값이 있으며 합계 행은 자르지 않는다
    const [dataRow, totalRow] = within(resultTable()).getAllByRole('row').slice(1) as [HTMLElement, HTMLElement]
    const [textCell, numberCell] = within(dataRow).getAllByRole('cell')

    expect(tableTexts()).toEqual([
      ['ABC…', '1,2…'],
      ['합계', '1,234,567'],
    ])
    expect(textCell).toHaveAttribute('title', 'ABCDEF')
    expect(numberCell).toHaveAttribute('title', '1,234,567')
    expect(within(totalRow).getAllByRole('cell')[1]).toHaveTextContent('1,234,567')
  })

  // 테스트 코드: RQ-098
  it('빈 값 대시와 정확히 N자인 값은 자르지 않는다', async () => {
    // given: 앞 N자 3이 걸린 열의 값 ABC와 빈 값
    const result = resultOf({
      columns: [resultColumn({ index: 0, label: 'Deal code', prefixLength: 3 })],
      rows: [['ABC'], [null]],
    })
    // when: 조회한다
    await openAndRun(result, 'Deal code')

    // then: ABC와 —가 그대로 보인다
    expect(tableTexts()).toEqual([['ABC'], ['—']])
  })

  // 테스트 코드: RQ-094
  it('잘림 표시를 보이고 100행을 넘으면 100행씩 페이지로 나눈다', async () => {
    // given: 총 12,345행 중 1,000행만 돌려준 결과
    const rows = Array.from({ length: 1000 }, (_, i) => [`행 ${i + 1}`])
    // when: 조회한다
    const { user } = await openAndRun(resultOf({ rows, totalCount: 12_345, truncated: true, rowLimit: 1000 }), 'Deal code')

    // then: 잘림 안내, 첫 페이지 100행, 1 페이지 표시가 보인다
    expect(screen.getByText(/총 12,345행 중 1,000행 표시\(최대 행 수 제한\)/)).toBeVisible()
    expect(tableTexts()).toHaveLength(100)
    expect(tableTexts()[0]).toEqual(['행 1'])
    expect(screen.getByRole('navigation', { name: '페이지' })).toHaveTextContent('1 페이지')

    // when: 다음을 누른다
    await user.click(screen.getByRole('button', { name: '다음' }))

    expect(tableTexts()).toHaveLength(100)
    // then: 둘째 페이지의 101번째 행부터 100행이고 2 페이지 표시다
    expect(tableTexts()[0]).toEqual(['행 101'])
    expect(screen.getByRole('navigation', { name: '페이지' })).toHaveTextContent('2 페이지')
  })

  // 테스트 코드: RQ-094
  it('100행 이하이면 페이지 표시가 없다', async () => {
    // when: 100행 결과로 조회한다
    await openAndRun(resultOf({ rows: Array.from({ length: 100 }, (_, i) => [`행 ${i + 1}`]), totalCount: 100 }), 'Deal code')

    // then: 100행이 모두 보이고 페이지·잘림 안내가 없다
    expect(tableTexts()).toHaveLength(100)
    expect(screen.queryByRole('navigation', { name: '페이지' })).not.toBeInTheDocument()
    expect(screen.queryByText(/최대 행 수 제한/)).not.toBeInTheDocument()
  })

  it('표는 자기 컨테이너 안에서 가로로 스크롤된다', async () => {
    // when: 기본 결과로 조회한다
    await openAndRun(null, 'Deal code')

    // then: 표의 부모가 report-scroll 클래스를 가진다
    expect(resultTable().parentElement).toHaveClass('report-scroll')
  })
})

describe('다시 조회', () => {
  const rowsOf = (n: number, prefix: string) => Array.from({ length: n }, (_, i) => [`${prefix} ${i + 1}`])

  // 테스트 코드: RQ-094
  it('새 결과가 보던 페이지보다 행이 적으면 첫 페이지를 다시 보인다', async () => {
    // given: 300행 결과의 셋째 페이지를 보고 있다
    const { user } = await openAndRun(resultOf({ rows: rowsOf(300, '행'), totalCount: 300 }), 'Deal code')
    // when: 다음 페이지로 가서 3행짜리 새 결과로 다시 조회한다
    await user.click(screen.getByRole('button', { name: '다음' }))
    await user.click(screen.getByRole('button', { name: '다음' }))
    expect(tableTexts()[0]).toEqual(['행 201'])

    mockControl.setReportQueryHandler(() => resultOf({ rows: rowsOf(3, '새'), totalCount: 3 }))
    await rerun(user)

    // then: 새 결과 3행이 보이고 페이지 표시가 없다
    await screen.findByText('새 1')
    expect(tableTexts()).toEqual([['새 1'], ['새 2'], ['새 3']])
    expect(screen.queryByRole('navigation', { name: '페이지' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-094
  it('새 결과가 길어도 첫 페이지부터 보인다', async () => {
    // given: 300행 결과의 둘째 페이지를 보고 있다
    const { user } = await openAndRun(resultOf({ rows: rowsOf(300, '행'), totalCount: 300 }), 'Deal code')
    await user.click(screen.getByRole('button', { name: '다음' }))

    // when: 250행짜리 새 결과로 다시 조회한다
    mockControl.setReportQueryHandler(() => resultOf({ rows: rowsOf(250, '새'), totalCount: 250 }))
    await rerun(user)

    // then: 첫 페이지 첫 행이 새 1이고 1 페이지 표시다
    await screen.findByText('새 1')
    expect(tableTexts()[0]).toEqual(['새 1'])
    expect(screen.getByRole('navigation', { name: '페이지' })).toHaveTextContent('1 페이지')
  })

  // 테스트 코드: RQ-095
  it('새 결과가 오면 합계 행이 꺼진다', async () => {
    // given: 합계 행을 켠 그룹핑 결과
    const grouped = groupedAmountResult([['A', 1000]], [null, 1000])
    const { user } = await openAndRun(grouped, 'Vendor')
    await user.click(screen.getByRole('checkbox', { name: '합계 행' }))
    expect(tableTexts()).toHaveLength(2)

    // when: 새 결과로 다시 조회한다
    mockControl.setReportQueryHandler(() => groupedAmountResult([['B', 2000]], [null, 2000]))
    await rerun(user)

    // then: 합계 행 체크가 꺼지고 데이터 행만 보인다
    await screen.findByText('B')
    expect(screen.getByRole('checkbox', { name: '합계 행' })).not.toBeChecked()
    expect(tableTexts()).toHaveLength(1)
  })
})

describe('설계 변경 안내', () => {
  // 테스트 코드: RQ-099
  it('조회 뒤 설계를 바꾸면 결과 탭에 다시 조회 안내가 보이고 다음 조회에서 사라진다', async () => {
    const { user } = await openDesigner()
    // given: Deal code 컬럼 설계
    await addColumn(user, 'Deal code')
    // when: 조회한다
    await runQuery(user)
    await screen.findByRole('table', { name: '조회 결과' })
    // then: 아직 다시 조회 안내가 없다
    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()

    // when: 작성 탭에서 컬럼을 더하고 결과 탭으로 돌아온다
    await showTab(user, 'design')
    await addColumn(user, 'Deal 이름')
    await showTab(user, 'result')

    // then: 다시 조회 안내와 이전 결과 표가 보인다
    expect(screen.getByText(STALE_NOTE)).toBeVisible()
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()

    // when: 다시 조회한다
    await rerun(user)

    // then: 새 열이 보이고 안내가 사라진다
    await screen.findByRole('columnheader', { name: 'Deal 이름' })
    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-099
  it('조회 뒤 컬럼 정렬을 바꿔도 다시 조회 안내가 보인다', async () => {
    const { user } = await openDesigner()
    // given: Deal code 컬럼 설계
    await addColumn(user, 'Deal code')
    // when: 조회한다
    await runQuery(user)
    await screen.findByRole('table', { name: '조회 결과' })

    // when: 정렬을 내림차순으로 바꾸고 결과 탭으로 돌아온다
    await showTab(user, 'design')
    await user.selectOptions(within(settingsOf('Deal code')).getByRole('combobox', { name: '정렬' }), 'desc')
    await showTab(user, 'result')

    // then: 다시 조회 안내가 보인다
    expect(screen.getByText(STALE_NOTE)).toBeVisible()

    // when: 정렬을 되돌리고 다시 조회한다
    await showTab(user, 'design')
    await user.selectOptions(within(settingsOf('Deal code')).getByRole('combobox', { name: '정렬' }), 'asc')
    await runQuery(user)

    await screen.findByRole('table', { name: '조회 결과' })
    // then: 안내가 사라진다
    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-099
  it('처음 조회하기 전에는 다시 조회 안내가 없다', async () => {
    // given: 빈 설계
    const { user } = await openDesigner()

    // when: 컬럼을 넣고 결과 탭으로 간다
    await addColumn(user, 'Deal code')
    await showTab(user, 'result')

    // then: 다시 조회 안내가 없다
    expect(screen.queryByText(/설계가 바뀌었습니다/)).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-099
  it('다시 조회 안내는 결과 탭에만 보이고 작성 탭에서는 숨는다', async () => {
    // given: 조회를 마치고 작성 탭에 있다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await runQuery(user)
    await screen.findByRole('table', { name: '조회 결과' })
    await showTab(user, 'design')

    // when: 컬럼을 더한다
    await addColumn(user, 'Deal 이름')

    // then: 안내가 작성 탭에서는 보이지 않는다
    expect(screen.getByText(STALE_NOTE)).not.toBeVisible() // 결과 탭의 안내라 작성 탭에서는 숨은 패널 안에 있다
    // when: 결과 탭으로 간다
    await showTab(user, 'result')
    // then: 안내가 보인다
    expect(screen.getByText(STALE_NOTE)).toBeVisible()
  })
})
