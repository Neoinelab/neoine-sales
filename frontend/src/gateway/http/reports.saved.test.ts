import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ReportLayout, SavedReportInput } from '../../shared/model/reportTypes'
import { serverUserRef } from '../../test/fixtures/serverDeal'
import { USER_ID } from '../../test/fake/seed/ids'
import { createHttpGateway } from './index'
import { createReportsHttp } from './reports'
import { json, noContent, problem, stubFetch, stubNetworkDown } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

/** 저장 리포트 HTTP 어댑터. 서버 JSON은 snake_case, 화면 모델은 camelCase. */

const SERVER_DEFINITION = {
  columns: [
    { field: 'deal.vendor', group: true },
    { field: 'deal.name', prefix_length: 5, group: false, label: '이름 앞부분', aggregate: 'count' },
    { field: 'deal.amount', group: false, aggregate: 'sum', sort: 'desc' },
  ],
  conditions: [
    { field: 'deal.amount', operator: 'between', value: [1_000_000, 2_000_000] },
    { field: 'deal.expected_close', operator: 'relative', value: { period: 'last_n_days', days: 30 } },
    { field: 'deal.name', operator: 'is_empty' },
  ],
  combine: 'or',
  row_limit: 10000,
}

const CAMEL_DEFINITION = {
  columns: [
    { field: 'deal.vendor', group: true },
    { field: 'deal.name', prefixLength: 5, group: false, label: '이름 앞부분', aggregate: 'count' },
    { field: 'deal.amount', group: false, aggregate: 'sum', sort: 'desc' },
  ],
  conditions: [
    { field: 'deal.amount', operator: 'between', value: [1_000_000, 2_000_000] },
    { field: 'deal.expected_close', operator: 'relative', value: { period: 'last_n_days', days: 30 } },
    { field: 'deal.name', operator: 'is_empty' },
  ],
  combine: 'or',
  rowLimit: 10000,
}

function serverSummary(over: Record<string, unknown> = {}) {
  return {
    id: 12,
    name: 'Vendor별 분기 Pipeline',
    description: 'Lost 제외, 올해 Expected Close',
    visibility: 'public',
    owner: serverUserRef({ id: USER_ID.kim }),
    updated_by: serverUserRef({ id: USER_ID.old, name: '강퇴사', label: '강퇴사(퇴사)', resigned: true }),
    entities: ['deal', 'action'],
    created_at: '2026-10-24T17:20:00+09:00',
    updated_at: '2026-10-25T09:00:00+09:00',
    chart_kind: null,
    ...over,
  }
}

const SERVER_CHART = {
  kind: 'stacked_bar',
  category: 0,
  series: 1,
  values: [2],
  swap: true,
  title: '분기 Pipeline',
  legend: 'right',
  data_labels: true,
  category_axis_title: 'Vendor',
  value_axis_title: '금액',
  value_min: 0,
  value_max: 12.5,
  secondary_axis: false,
  histogram: null,
  show_total: false,
  combo_series: null,
}

const CAMEL_CHART = {
  kind: 'stacked_bar',
  category: 0,
  series: 1,
  values: [2],
  swap: true,
  title: '분기 Pipeline',
  legend: 'right',
  dataLabels: true,
  categoryAxisTitle: 'Vendor',
  valueAxisTitle: '금액',
  valueMin: 0,
  valueMax: 12.5,
  secondaryAxis: false,
  histogram: null,
  showTotal: false,
  comboSeries: null,
}

const SERVER_LAYOUT = { view: 'chart', order: ['chart', 'table'], arrange: 'side_by_side' }
const CAMEL_LAYOUT: ReportLayout = { view: 'chart', order: ['chart', 'table'], arrange: 'side_by_side' }

const serverDetail = (over: Record<string, unknown> = {}) => ({
  ...serverSummary(),
  revision: 3,
  definition: SERVER_DEFINITION,
  generated_sql: 'SELECT deal.vendor FROM deals',
  chart: null,
  chart_problem: null,
  layout: SERVER_LAYOUT,
  ...over,
})

const serverResult = () => ({
  row_scope: 'deal',
  action_filter: 'none',
  deal_numbers_once: false,
  columns: [{ index: 0, field: 'deal.vendor', label: 'Vendor', entity: 'deal', type: 'code', value_type: 'text', format: null, unit: null, prefix_length: null, group: true, aggregate: null }],
  rows: [['Silverfort']],
  totals: null,
  total_count: 1,
  truncated: false,
  row_limit: 1000,
  sql: 'SELECT demo',
  elapsed_ms: 21,
  today: '2026-10-27',
})

const INPUT: SavedReportInput = {
  name: ' 새 리포트 ',
  description: '설명',
  visibility: 'private',
  definition: CAMEL_DEFINITION as SavedReportInput['definition'],
  chart: null,
  layout: CAMEL_LAYOUT,
}

describe('저장 리포트 HTTP: 읽기', () => {
  // 테스트 코드: RS-103
  it('목록은 GET /reports로 읽고 요약을 camelCase로 바꾼다', async () => {
    // given: 서버 응답을 흉내 내는 fetch(요약 둘)
    const { calls } = stubFetch(json([serverSummary(), serverSummary({ id: 9, visibility: 'private', entities: ['deal'] })]))

    // when: 목록을 읽는다
    const list = await createReportsHttp().list()

    // then: GET 요청이고 요약이 camelCase이며 배치가 없다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/reports' })
    expect(list).toHaveLength(2)
    expect(list[0]).toEqual({
      id: 12,
      name: 'Vendor별 분기 Pipeline',
      description: 'Lost 제외, 올해 Expected Close',
      visibility: 'public',
      owner: { id: USER_ID.kim, name: '김영업', role: 'sales', status: 'active' },
      updatedBy: { id: USER_ID.old, name: '강퇴사', role: 'sales', status: 'resigned' },
      entities: ['deal', 'action'],
      createdAt: '2026-10-24T17:20:00+09:00',
      updatedAt: '2026-10-25T09:00:00+09:00',
      chartKind: null,
    })
    expect(list[1]).toMatchObject({ id: 9, visibility: 'private', entities: ['deal'] })
  })

  // 테스트 코드: RS-103
  it('상세는 정의와 함께 camelCase로 바꾼다', async () => {
    // given: 서버 상세 응답
    const { calls } = stubFetch(json(serverDetail()))

    // when: 상세를 읽는다
    const report = await createReportsHttp().get(12)

    // then: GET 요청이고 revision·SQL·만든 사람·정의가 camelCase로 온다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/reports/12' })
    expect(report).toMatchObject({ id: 12, revision: 3, generatedSql: 'SELECT deal.vendor FROM deals', owner: { id: USER_ID.kim }, entities: ['deal', 'action'] })
    expect(report.definition).toEqual(CAMEL_DEFINITION)
  })

  it('저장 정의의 null 포맷은 포맷 키 없이 옮긴다', async () => {
    // given: 컬럼의 format이 null인 저장 정의 응답
    const definition = { columns: [{ field: 'deal.name', format: null, group: false }], conditions: [], combine: 'and', row_limit: 100 }
    stubFetch(json(serverDetail({ definition })))

    // when: 리포트를 읽는다
    const { definition: mapped } = await createReportsHttp().get(12)

    // then: 첫 컬럼에 format 키가 없다
    expect('format' in (mapped.columns[0] ?? {})).toBe(false)
  })

  it('정의에 없는 키는 화면 모델에도 만들지 않는다', async () => {
    // given: 필드와 그룹 여부만 있는 저장 정의 응답
    stubFetch(json(serverDetail({ definition: { columns: [{ field: 'deal.code', group: false }], conditions: [], combine: 'and', row_limit: 100 } })))

    // when: 리포트를 읽는다
    const { definition } = await createReportsHttp().get(12)

    // then: 정의에 없는 sort·label 키가 생기지 않는다
    expect(definition).toEqual({ columns: [{ field: 'deal.code', group: false }], conditions: [], combine: 'and', rowLimit: 100 })
    expect('sort' in definition).toBe(false)
    expect('label' in (definition.columns[0] ?? {})).toBe(false)
  })

  it('컬럼별 정렬을 읽고 모르는 값은 버린다', async () => {
    // given: 정렬이 asc·null·desc·모르는 값인 컬럼 넷의 저장 정의 응답
    const columns = [
      { field: 'deal.code', group: false, sort: 'asc' },
      { field: 'deal.name', group: false, sort: null },
      { field: 'deal.vendor', group: false, sort: 'desc' },
      { field: 'deal.owner', group: false, sort: 'sideways' },
    ]
    stubFetch(json(serverDetail({ definition: { columns, conditions: [], combine: 'and', row_limit: 100 } })))

    // when: 리포트를 읽는다
    const { definition } = await createReportsHttp().get(12)

    // then: asc·desc만 남고 null과 모르는 값은 정렬 없음이며 최상위 sort 키가 없다
    expect(definition.columns.map((c) => c.sort)).toEqual(['asc', undefined, 'desc', undefined])
    expect('sort' in (definition.columns[1] ?? {})).toBe(false)
    expect('sort' in definition).toBe(false)
  })

  // 테스트 코드: RS-103
  it('HTTP 게이트웨이에 reports로 연결되어 있다', () => {
    // when: HTTP 게이트웨이의 reports를 꺼낸다
    const reports = createHttpGateway().reports

    // then: 저장 리포트 메서드 8개가 모두 함수다
    for (const name of ['list', 'get', 'create', 'update', 'copy', 'remove', 'run', 'saveReportLayout'] as const) expect(typeof reports[name]).toBe('function')
  })

  // 테스트 코드: RS-103
  it('저장 리포트 실행은 POST /reports/{id}/run이고 조회 결과와 같은 변환이다', async () => {
    // given: 서버 실행 응답
    const { calls } = stubFetch(json(serverResult()))

    // when: 저장 리포트를 실행한다
    const result = await createReportsHttp().run(12)

    // then: 본문 없는 POST이고 결과가 조회 결과와 같은 모양이다
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/reports/12/run' })
    expect(calls[0]?.body).toBeUndefined()
    expect(result).toMatchObject({ rowScope: 'deal', totalCount: 1, rowLimit: 1000, today: '2026-10-27', rows: [['Silverfort']] })
  })
})

describe('저장 리포트 HTTP: 쓰기', () => {
  // 테스트 코드: RS-103
  it('만들기·덮어쓰기(revision 포함)·복제·삭제 요청을 경로와 snake_case 본문으로 보낸다', async () => {
    // given: 서버 응답 넷
    const { calls } = stubFetch(json(serverDetail(), 201, { Location: '/api/v1/reports/12' }), json(serverDetail({ revision: 4 })), json(serverDetail({ id: 13 }), 201), noContent())
    const http = createReportsHttp()

    // when: 만들기, 덮어쓰기, 복제, 삭제를 차례로 부른다
    const created = await http.create(INPUT)
    const updated = await http.update(12, { ...INPUT, revision: 3 })
    const copied = await http.copy(12, { name: '복사본', description: '', visibility: 'public' })
    await http.remove(12)

    // then: 경로·메서드가 맞고 본문이 snake_case이며 복제는 메타뿐이다
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/reports' })
    expect(calls[0]?.body).toEqual({ name: ' 새 리포트 ', description: '설명', visibility: 'private', definition: SERVER_DEFINITION, chart: null, layout: SERVER_LAYOUT })
    expect(calls[1]).toMatchObject({ method: 'PUT', path: '/api/v1/reports/12' })
    expect(calls[1]?.body).toEqual({ name: ' 새 리포트 ', description: '설명', visibility: 'private', definition: SERVER_DEFINITION, chart: null, layout: SERVER_LAYOUT, revision: 3 })
    expect(calls[2]).toMatchObject({ method: 'POST', path: '/api/v1/reports/12/copy' })
    expect(calls[2]?.body).toEqual({ name: '복사본', description: '', visibility: 'public' })
    expect(calls[3]).toMatchObject({ method: 'DELETE', path: '/api/v1/reports/12' })
    expect(created.revision).toBe(3)
    expect(updated.revision).toBe(4)
    expect(copied.id).toBe(13)
  })

  // 테스트 코드: RS-103
  it('만들기 본문에는 SQL·id·만든 사람을 담지 않는다', async () => {
    // given: 서버 응답
    const { calls } = stubFetch(json(serverDetail(), 201))

    // when: 만든다
    await createReportsHttp().create(INPUT)

    // then: 본문 키가 이름·설명·공개 범위·정의·차트·배치뿐이다
    expect(Object.keys(calls[0]?.body as object).sort()).toEqual(['chart', 'definition', 'description', 'layout', 'name', 'visibility'])
  })

  // 테스트 코드: RS-103
  it('삭제는 본문 없이 성공한다', async () => {
    // given: 본문 없는 204 응답
    stubFetch(noContent())

    // when·then: 삭제가 값 없이 성공한다
    await expect(createReportsHttp().remove(12)).resolves.toBeUndefined()
  })
})

describe('저장 리포트 HTTP: 오류', () => {
  const issues = [
    { location: ['columns', 0, 'field'], code: 'unknown-field', message: '허용되지 않은 필드입니다: deal.nope' },
    { location: ['row_limit'], code: 'row-limit-invalid', message: '최대 행 수가 올바르지 않습니다' },
  ]
  const invalidBody = () => problem(422, 'invalid-report', '허용되지 않은 필드입니다: deal.nope', { errors: issues })

  // 테스트 코드: RS-104
  it.each([
    ['create', (h: ReturnType<typeof createReportsHttp>) => h.create(INPUT)],
    ['update', (h: ReturnType<typeof createReportsHttp>) => h.update(12, { ...INPUT, revision: 3 })],
    ['copy', (h: ReturnType<typeof createReportsHttp>) => h.copy(12, { name: 'a', description: '', visibility: 'public' })],
    ['run', (h: ReturnType<typeof createReportsHttp>) => h.run(12)],
  ])('정의 위반 422는 %s에서도 위치·code·문구를 reportErrors로 옮긴다', async (_name, call) => {
    // given: errors가 있는 invalid-report 응답
    stubFetch(invalidBody())

    // when: 해당 요청을 부른다
    const error = await call(createReportsHttp()).catch((e: unknown) => e)

    // then: invalid-report ApiError이고 reportErrors가 서버 위반과 같다
    expect(error).toMatchObject({ status: 422, kind: 'invalid-report', message: '허용되지 않은 필드입니다: deal.nope' })
    expect((error as { problem: { reportErrors: unknown } }).problem.reportErrors).toEqual(issues)
  })

  // 테스트 코드: RS-104
  it('409 두 종류를 구분해 이름 중복과 저장 충돌을 화면이 알 수 있게 한다', async () => {
    // given: already-exists와 invalid-state 응답
    stubFetch(problem(409, 'already-exists', '같은 이름의 리포트가 이미 있습니다.'), problem(409, 'invalid-state', '다른 사용자가 먼저 이 리포트를 저장했습니다.'))
    const http = createReportsHttp()

    // when: 만들기와 덮어쓰기를 부른다
    const duplicate = await http.create(INPUT).catch((e: unknown) => e)
    const conflict = await http.update(12, { ...INPUT, revision: 1 }).catch((e: unknown) => e)

    // then: kind가 각각 already-exists, invalid-state다(conflict로 합치지 않는다)
    expect(duplicate).toMatchObject({ status: 409, kind: 'already-exists', message: '같은 이름의 리포트가 이미 있습니다.' })
    expect(conflict).toMatchObject({ status: 409, kind: 'invalid-state', message: '다른 사용자가 먼저 이 리포트를 저장했습니다.' })
  })

  // 테스트 코드: RS-104
  it.each([
    [404, 'not-found', 'not-found'],
    [403, 'forbidden', 'forbidden'],
    [422, 'invalid-value', 'validation'],
    [422, 'request-validation', 'validation'],
    [401, 'unauthenticated', 'unauthorized'],
  ] as const)('%s %s 응답은 %s kind와 서버 문구의 오류가 된다', async (status, serverKind, kind) => {
    // given: 해당 상태·kind의 서버 응답
    stubFetch(problem(status, serverKind, '서버 문구'))

    // when·then: 삭제가 그 kind와 서버 문구로 거절된다
    await expect(createReportsHttp().remove(12)).rejects.toMatchObject({ status, kind, message: '서버 문구' })
  })

  // 테스트 코드: RS-104
  it('연결이 끊기면 네트워크 오류가 된다', async () => {
    // given: 연결이 끊긴 상태
    stubNetworkDown()

    // when·then: 목록과 만들기가 네트워크 오류로 거절된다
    await expect(createReportsHttp().list()).rejects.toMatchObject({ status: 0, kind: 'network' })
    await expect(createReportsHttp().create(INPUT)).rejects.toMatchObject({ status: 0, kind: 'network' })
  })

  // 테스트 코드: RS-104
  it('실행의 시간 초과는 report-timeout kind의 오류가 된다', async () => {
    // given: 503 report-timeout 응답
    stubFetch(problem(503, 'report-timeout', '조회가 10초 안에 끝나지 않았습니다.'))

    // when·then: 실행이 report-timeout 오류로 거절된다
    await expect(createReportsHttp().run(12)).rejects.toMatchObject({ status: 503, kind: 'report-timeout' })
  })
})


describe('saved reports over HTTP: 차트', () => {
  // 테스트 코드: RC-079
  it('상세의 차트와 차트 문제를 화면 모양으로 바꾼다', async () => {
    // given: 차트가 있는 상세와 차트를 읽을 수 없는 상세 응답
    stubFetch(json(serverDetail({ chart: SERVER_CHART })), json(serverDetail({ chart: null, chart_problem: '저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요.' })))
    const http = createReportsHttp()

    // when: 상세를 두 번 조회한다
    const withChart = await http.get(12)
    const broken = await http.get(12)

    // then: 차트는 camelCase 화면 모양이고, 읽을 수 없는 상세는 차트가 null이며 chartProblem이 안내 문구다
    expect(withChart.chart).toEqual(CAMEL_CHART)
    expect(withChart.chartProblem).toBeNull()
    expect(broken.chart).toBeNull()
    expect(broken.chartProblem).toBe('저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요.')
  })

  // 테스트 코드: RC-079
  it('범위와 계열이 null이면 null로 둔다', async () => {
    // given: 범위와 계열이 null인 차트 응답
    stubFetch(json(serverDetail({ chart: { ...SERVER_CHART, series: null, value_min: null, value_max: null } })))

    // when: 상세를 조회한다
    const { chart } = await createReportsHttp().get(12)

    // then: 계열과 범위가 null이다
    expect(chart).toMatchObject({ series: null, valueMin: null, valueMax: null })
  })

  // 테스트 코드: RC-079
  it('목록 항목의 차트 종류를 바꾼다', async () => {
    // given: 차트 종류가 도넛형인 항목과 null인 항목의 목록 응답
    stubFetch(json([serverSummary({ chart_kind: 'doughnut' }), serverSummary({ id: 9, chart_kind: null })]))

    // when: 목록을 조회한다
    const list = await createReportsHttp().list()

    // then: 도넛형과 null이다
    expect(list.map((r) => r.chartKind)).toEqual(['doughnut', null])
  })

  // 테스트 코드: RC-079
  it.each([
    ['모르는 종류', { kind: 'hexagon' }],
    ['모르는 히스토그램 구간 방식', { kind: 'histogram', category: null, histogram: { bin_mode: 'log', bin_count: null, bin_width: null, overflow: null, underflow: null } }],
    ['모르는 콤보 계열 종류', { kind: 'combo', combo_series: [{ type: 'bar', secondary: false }] }],
    ['모르는 범례 위치', { legend: 'left' }],
  ])('응답에 모르는 값이 있으면 잘못된 응답으로 본다 (%s)', async (_name, over) => {
    // given: 모르는 종류·구간 방식·계열 종류·범례 위치가 든 차트 응답
    stubFetch(json(serverDetail({ chart: { ...SERVER_CHART, ...over } })))

    // when: 상세를 조회한다
    const error = await createReportsHttp().get(12).catch((e: unknown) => e)

    // then: 오류 종류가 malformed-response다
    expect(error).toMatchObject({ kind: 'malformed-response' })
  })

  // 테스트 코드: RC-079
  it('목록 항목의 모르는 차트 종류는 잘못된 응답으로 본다', async () => {
    // given: 차트 종류가 모르는 값인 목록 응답
    stubFetch(json([serverSummary({ chart_kind: 'hexagon' })]))

    // when: 목록을 조회한다
    const error = await createReportsHttp().list().catch((e: unknown) => e)

    // then: 오류 종류가 malformed-response다
    expect(error).toMatchObject({ kind: 'malformed-response' })
  })

  // 테스트 코드: RC-079
  it.each([
    'stacked_horizontal_bar',
    'stacked_100_horizontal_bar',
    'line_markers',
    'stacked_line',
    'stacked_line_markers',
    'stacked_100_line',
    'stacked_100_line_markers',
    'stacked_area',
    'stacked_100_area',
    'scatter_smooth_markers',
    'scatter_smooth',
    'scatter_line_markers',
    'scatter_line',
    'bubble',
    'radar',
    'radar_markers',
    'radar_filled',
    'treemap',
    'sunburst',
    'histogram',
    'pareto',
    'waterfall',
    'funnel',
  ])('새 종류 %s는 상세와 목록에서 그대로 바꾼다', async (kind) => {
    // given: 새 종류 차트의 상세와 목록 응답
    stubFetch(json(serverDetail({ chart: { ...SERVER_CHART, kind, category: kind === 'histogram' ? null : 0 } })), json([serverSummary({ chart_kind: kind })]))
    const http = createReportsHttp()

    // when: 상세와 목록을 조회한다
    const detail = await http.get(12)
    const list = await http.list()

    // then: 상세 차트 종류와 목록 차트 종류가 그 종류다
    expect(detail.chart?.kind).toBe(kind)
    expect(list[0]?.chartKind).toBe(kind)
  })

  // 테스트 코드: RC-079
  it('히스토그램의 null 범주와 구간 설정을 그대로 바꾼다', async () => {
    // given: 범주가 null인 히스토그램 응답
    stubFetch(json(serverDetail({ chart: { ...SERVER_CHART, kind: 'histogram', category: null, series: null, histogram: { bin_mode: 'count', bin_count: 8, bin_width: null, overflow: 100, underflow: null } } })))

    // when: 상세를 조회한다
    const { chart } = await createReportsHttp().get(12)

    // then: 범주가 null이고 구간 설정이 camelCase로 바뀐다
    expect(chart).toMatchObject({ kind: 'histogram', category: null, histogram: { binMode: 'count', binCount: 8, binWidth: null, overflow: 100, underflow: null } })
  })

  // 테스트 코드: RC-079
  it('합계 막대와 콤보 계열 설정을 바꾼다', async () => {
    // given: 폭포(합계 켬)와 콤보(계열 설정) 상세 응답
    stubFetch(
      json(serverDetail({ chart: { ...SERVER_CHART, kind: 'waterfall', series: null, show_total: true } })),
      json(serverDetail({ chart: { ...SERVER_CHART, kind: 'combo', series: null, values: [2, 3], secondary_axis: true, combo_series: [{ type: 'stacked_area', secondary: false }, { type: 'line_markers', secondary: true }] } })),
    )
    const http = createReportsHttp()

    // when: 상세를 두 번 조회한다
    const waterfall = await http.get(12)
    const combo = await http.get(12)

    // then: showTotal이 true이고 콤보 계열 설정이 그대로다
    expect(waterfall.chart?.showTotal).toBe(true)
    expect(combo.chart?.comboSeries).toEqual([
      { type: 'stacked_area', secondary: false },
      { type: 'line_markers', secondary: true },
    ])
  })

  // 테스트 코드: RC-079
  it('구간·합계·콤보 계열을 16키 snake_case로 보낸다', async () => {
    // given: 구간·합계·콤보 설정을 단 차트 입력 세 가지
    const histogram = { binMode: 'width', binCount: null, binWidth: 2.5, overflow: 100, underflow: null }
    const combo = [{ type: 'column', secondary: false }, { type: 'line', secondary: true }]
    const { calls } = stubFetch(json(serverDetail({ chart: SERVER_CHART }), 201), json(serverDetail({ chart: SERVER_CHART }), 201), json(serverDetail({ chart: SERVER_CHART }), 201))
    const http = createReportsHttp()

    // when: 차트를 담아 리포트를 세 번 만든다
    await http.create({ ...INPUT, chart: { ...CAMEL_CHART, kind: 'histogram', category: null, series: null, histogram } as unknown as SavedReportInput['chart'] })
    await http.create({ ...INPUT, chart: { ...CAMEL_CHART, kind: 'waterfall', series: null, showTotal: true } as unknown as SavedReportInput['chart'] })
    await http.create({ ...INPUT, chart: { ...CAMEL_CHART, kind: 'combo', series: null, secondaryAxis: true, comboSeries: combo } as unknown as SavedReportInput['chart'] })

    const sent = calls.map((c) => (c.body as { chart: Record<string, unknown> }).chart)
    // then: 본문 차트가 16키이고 구간·합계·콤보 설정이 snake_case 값이다
    expect(Object.keys(sent[0] ?? {})).toHaveLength(16)
    expect(sent[0]).toMatchObject({ category: null, histogram: { bin_mode: 'width', bin_count: null, bin_width: 2.5, overflow: 100, underflow: null }, show_total: false, combo_series: null })
    expect(sent[1]).toMatchObject({ show_total: true, histogram: null })
    expect(sent[2]).toMatchObject({ combo_series: combo, secondary_axis: true })
  })

  // 테스트 코드: RC-079
  it('만들기·수정 본문에 차트를 snake_case로 보낸다', async () => {
    // given: 차트가 있는 입력
    const { calls } = stubFetch(json(serverDetail({ chart: SERVER_CHART }), 201), json(serverDetail({ chart: SERVER_CHART })))
    const http = createReportsHttp()

    // when: 만들고 수정한다
    await http.create({ ...INPUT, chart: CAMEL_CHART as SavedReportInput['chart'] })
    await http.update(12, { ...INPUT, chart: CAMEL_CHART as SavedReportInput['chart'], revision: 3 })

    // then: 두 본문의 차트가 서버 모양과 같다
    expect((calls[0]?.body as { chart: unknown }).chart).toEqual(SERVER_CHART)
    expect((calls[1]?.body as { chart: unknown }).chart).toEqual(SERVER_CHART)
  })

  // 테스트 코드: RC-079
  it('차트가 없으면 null을 보내 덮어쓰기가 차트를 지운다', async () => {
    // given: 차트가 없는 입력
    const { calls } = stubFetch(json(serverDetail(), 201), json(serverDetail()))
    const http = createReportsHttp()

    // when: 만들고 수정한다
    await http.create(INPUT)
    await http.update(12, { ...INPUT, revision: 3 })

    // then: 두 본문에 chart: null이 있다
    expect(calls[0]?.body).toHaveProperty('chart', null)
    expect(calls[1]?.body).toHaveProperty('chart', null)
  })

  // 테스트 코드: RC-079
  it('불완전한 차트도 그대로 보내 서버가 위치와 함께 답하게 한다', async () => {
    // given: 범주가 null이고 범위가 글자인 차트 입력
    const { calls } = stubFetch(json(serverDetail(), 201))
    const incomplete = { ...CAMEL_CHART, category: null, valueMin: 'abc' } as unknown as SavedReportInput['chart']

    // when: 리포트를 만든다
    await createReportsHttp().create({ ...INPUT, chart: incomplete })

    // then: 본문 차트가 그 값을 그대로 담는다
    expect((calls[0]?.body as { chart: Record<string, unknown> }).chart).toMatchObject({ category: null, value_min: 'abc' })
  })

  // 테스트 코드: RC-079
  it('복제에는 차트를 보내지 않는다', async () => {
    // given: 복제 응답
    const { calls } = stubFetch(json(serverDetail({ id: 13 }), 201))

    // when: 리포트를 복제한다
    await createReportsHttp().copy(12, { name: '복사본', description: '', visibility: 'public' })

    // then: 본문이 이름·설명·공개 범위뿐이다
    expect(calls[0]?.body).toEqual({ name: '복사본', description: '', visibility: 'public' })
  })

  // 테스트 코드: RC-079
  it('차트 위치의 위반을 reportErrors로 옮긴다', async () => {
    // given: 차트 위치의 invalid-report 오류 응답
    const issues = [{ location: ['chart', 'values', 1], code: 'chart-value-invalid', message: '값 열은 숫자(집계) 컬럼이어야 합니다' }]
    stubFetch(problem(422, 'invalid-report', '값 열은 숫자(집계) 컬럼이어야 합니다', { errors: issues }))

    // when: 리포트를 만든다
    const error = await createReportsHttp().create(INPUT).catch((e: unknown) => e)

    // then: problem.reportErrors가 그 위반 목록이다
    expect((error as { problem: { reportErrors: unknown } }).problem.reportErrors).toEqual(issues)
  })
})

describe('저장 리포트 HTTP: 결과 배치', () => {
  // 테스트 코드: RS-105
  it('상세의 배치를 값 그대로 옮긴다', async () => {
    // given: 배치가 서로 다른 상세 응답 둘
    stubFetch(json(serverDetail()), json(serverDetail({ layout: { view: 'both', order: ['table', 'chart'], arrange: 'stacked' } })))
    const http = createReportsHttp()

    // when: 상세를 두 번 읽는다
    const sided = await http.get(12)
    const stacked = await http.get(12)

    // then: 배치가 서버 값 그대로다
    expect(sided.layout).toEqual(CAMEL_LAYOUT)
    expect(stacked.layout).toEqual({ view: 'both', order: ['table', 'chart'], arrange: 'stacked' })
  })

  // 테스트 코드: RS-105
  it('만들기·덮어쓰기·복제 응답의 배치도 그대로 옮긴다', async () => {
    // given: 서버 응답 셋
    stubFetch(json(serverDetail(), 201), json(serverDetail({ revision: 4 })), json(serverDetail({ id: 13 }), 201))
    const http = createReportsHttp()

    // when: 만들기, 덮어쓰기, 복제를 부른다
    const created = await http.create(INPUT)
    const updated = await http.update(12, { ...INPUT, revision: 3 })
    const copied = await http.copy(12, { name: '복사본', description: '', visibility: 'public' })

    // then: 세 응답의 배치가 서버 값 그대로다
    for (const report of [created, updated, copied]) expect(report.layout).toEqual(CAMEL_LAYOUT)
  })

  // 테스트 코드: RS-105
  it('목록 항목에는 배치가 없다', async () => {
    // given: 서버 목록 응답
    stubFetch(json([serverSummary()]))

    // when: 목록을 읽는다
    const [item] = await createReportsHttp().list()

    // then: 항목에 layout이 없다
    expect(item).not.toHaveProperty('layout')
  })

  // 테스트 코드: RS-105
  it('배치 저장은 PUT /reports/{id}/layout에 배치와 revision을 보내고 상세로 바꾼다', async () => {
    // given: 서버 상세 응답(revision 4)
    const { calls } = stubFetch(json(serverDetail({ revision: 4, updated_by: serverUserRef({ id: USER_ID.kim }) })))

    // when: 배치를 revision 3으로 저장한다
    const saved = await createReportsHttp().saveReportLayout(12, { layout: CAMEL_LAYOUT, revision: 3 })

    // then: PUT 경로와 본문이 맞고 응답이 상세(camelCase)로 바뀐다
    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/reports/12/layout' })
    expect(calls[0]?.body).toEqual({ layout: SERVER_LAYOUT, revision: 3 })
    expect(saved).toMatchObject({ id: 12, revision: 4, layout: CAMEL_LAYOUT, updatedBy: { id: USER_ID.kim } })
    expect(saved.definition).toEqual(CAMEL_DEFINITION)
  })

  // 테스트 코드: RS-105
  it('배치 저장은 layout과 revision 외에는 보내지 않는다', async () => {
    // given: 서버 상세 응답
    const { calls } = stubFetch(json(serverDetail()))

    // when: 배치를 저장한다
    await createReportsHttp().saveReportLayout(12, { layout: CAMEL_LAYOUT, revision: 3 })

    // then: 본문 키가 layout, revision뿐이다
    expect(Object.keys(calls[0]?.body as object).sort()).toEqual(['layout', 'revision'])
  })

  // 테스트 코드: RS-105
  it('낡은 revision의 배치 저장은 invalid-state kind의 오류가 된다', async () => {
    // given: 409 invalid-state 응답
    stubFetch(problem(409, 'invalid-state', '다른 사용자가 먼저 이 리포트를 저장했습니다.'))

    // when·then: 배치 저장이 invalid-state와 서버 문구로 거절된다
    await expect(createReportsHttp().saveReportLayout(12, { layout: CAMEL_LAYOUT, revision: 1 })).rejects.toMatchObject({
      status: 409,
      kind: 'invalid-state',
      message: '다른 사용자가 먼저 이 리포트를 저장했습니다.',
    })
  })

  // 테스트 코드: RS-105
  it.each([
    [404, 'not-found', 'not-found'],
    [403, 'forbidden', 'forbidden'],
    [401, 'unauthenticated', 'unauthorized'],
    [422, 'request-validation', 'validation'],
  ] as const)('배치 저장에서 %s %s 응답은 %s kind의 오류가 된다', async (status, serverKind, kind) => {
    // given: 해당 상태·kind의 서버 응답
    stubFetch(problem(status, serverKind, '서버 문구'))

    // when·then: 배치 저장이 그 kind와 서버 문구로 거절된다
    await expect(createReportsHttp().saveReportLayout(12, { layout: CAMEL_LAYOUT, revision: 1 })).rejects.toMatchObject({ status, kind, message: '서버 문구' })
  })

  // 테스트 코드: RS-105
  it('배치 값 위반은 layout 위치와 함께 reportErrors로 옮긴다', async () => {
    // given: [layout, order] 위치의 위반 응답
    const issues = [{ location: ['layout', 'order'], code: 'invalid-value', message: '타일 순서는 table과 chart를 한 번씩 담아야 합니다' }]
    stubFetch(problem(422, 'invalid-report', '타일 순서는 table과 chart를 한 번씩 담아야 합니다', { errors: issues }))

    // when: 배치를 저장한다
    const error = await createReportsHttp().saveReportLayout(12, { layout: CAMEL_LAYOUT, revision: 1 }).catch((e: unknown) => e)

    // then: invalid-report이고 reportErrors가 서버 위반과 같다
    expect(error).toMatchObject({ status: 422, kind: 'invalid-report' })
    expect((error as { problem: { reportErrors: unknown } }).problem.reportErrors).toEqual(issues)
  })

  // 테스트 코드: RS-105
  it('연결이 끊기면 배치 저장도 네트워크 오류가 된다', async () => {
    // given: 연결이 끊긴 상태
    stubNetworkDown()

    // when·then: 배치 저장이 네트워크 오류로 거절된다
    await expect(createReportsHttp().saveReportLayout(12, { layout: CAMEL_LAYOUT, revision: 1 })).rejects.toMatchObject({ status: 0, kind: 'network' })
  })
})
