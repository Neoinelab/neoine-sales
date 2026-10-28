import { describe, expect, it } from 'vitest'

/**
 * T-ARCH-01: 화면(features)은 `shared/api`와 `mock/`을 직접 import하지 않는다.
 * 화면은 `data/*` 훅만 쓰고, 훅이 게이트웨이를 안다. 실제 연동으로 바꿀 때 mock만 지울 수 있어야 한다.
 */
const sources = import.meta.glob('../features/**/*.{ts,tsx}', { query: '?raw', import: 'default', eager: true }) as Record<
  string,
  string
>

const FORBIDDEN = /(?:from\s+|import\s*\(\s*|import\s+)['"][^'"]*(?:shared\/api|\/mock|gateway\/http)(?:\/[^'"]*)?['"]/

function featureSources(): [string, string][] {
  return Object.entries(sources).filter(([path]) => !/\.test\.tsx?$/.test(path))
}

/**
 * T-ARCH-02: 앱(비테스트) 코드는 테스트 전용 픽스처·도우미(`test/`, `mock/testing`)를 import하지 않는다.
 * 샘플 업무 데이터는 `test/fixtures`에만 있고 앱 기본 시드는 빈 업무 데이터다.
 */
const appSources = import.meta.glob(['../**/*.{ts,tsx}', '!../test/**', '!../**/*.test.{ts,tsx}', '!../**/test{Helpers,Utils}.ts'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const TEST_IMPORT = /(?:from\s+|import\s*\(\s*|import\s+)['"][^'"]*(?:\/test\/|\/mock\/testing|\.\/testing)[^'"]*['"]/

describe('T-ARCH-02 앱 코드의 테스트 픽스처 경계', () => {
  it('scans real app source files', () => {
    expect(Object.keys(appSources).length).toBeGreaterThan(100)
    expect(Object.keys(appSources).some((p) => p.includes('/mock/'))).toBe(false)
  })

  it('has no src/mock directory', () => {
    const mockFiles = Object.keys(import.meta.glob('../mock/**/*'))
    expect(mockFiles).toEqual([])
  })

  it('app sources have no gateway mode switch or mock control', () => {
    const MOCK_WORDS = /VITE_GATEWAY|gatewayMode|mockControl|MockBanner|MockPanel/
    const offenders = Object.entries(appSources)
      .filter(([, text]) => MOCK_WORDS.test(text))
      .map(([path]) => path)
    expect(offenders).toEqual([])
  })

  it('has no import of test fixtures or test helpers in app sources', () => {
    const offenders = Object.entries(appSources)
      .filter(([, text]) => TEST_IMPORT.test(text))
      .map(([path]) => path)
    expect(offenders).toEqual([])
  })

  it('detects the forbidden import forms (self check of the pattern)', () => {
    expect(TEST_IMPORT.test("import { buildSampleSeed } from '../test/fixtures/sampleSeed'")).toBe(true)
    expect(TEST_IMPORT.test("import { newMock } from './testing'")).toBe(true)
    expect(TEST_IMPORT.test("import { defaultMock } from '../test/fake/default'")).toBe(true)
    expect(TEST_IMPORT.test("import { emptyBusinessSeed } from './seed'")).toBe(false)
  })
})

describe('T-ARCH-01 features 경계', () => {
  it('scans real feature source files', () => {
    expect(featureSources().length).toBeGreaterThan(50)
  })

  it('has no import of shared/api or mock/ in features sources', () => {
    const offenders = featureSources()
      .filter(([, text]) => FORBIDDEN.test(text))
      .map(([path]) => path)
    expect(offenders).toEqual([])
  })

  it('detects the forbidden import forms (self check of the pattern)', () => {
    expect(FORBIDDEN.test("import { ApiError } from '../../shared/api/problem'")).toBe(true)
    expect(FORBIDDEN.test("import { x } from '../../mock/default'")).toBe(true)
    expect(FORBIDDEN.test("const m = await import('../../mock')")).toBe(true)
    expect(FORBIDDEN.test("import { createHttpGateway } from '../../gateway/http'")).toBe(true)
    expect(FORBIDDEN.test("import { unwrap } from '../../gateway/http/request'")).toBe(true)
    expect(FORBIDDEN.test("import { gatewayMode } from '../../gateway/mode'")).toBe(false)
    expect(FORBIDDEN.test("import { useDeals } from '../../data/deals'")).toBe(false)
    expect(FORBIDDEN.test("import type { Deal } from '../../shared/model/types'")).toBe(false)
  })
})

/**
 * T-ARCH-03 (시간 기준 서버 통일 AC7): 앱 코드는 `gateway/clock.ts` 밖에서 브라우저 시계·시간대를 읽지 않는다.
 * 지금·오늘은 `useToday`(서버 동기 시계), 시각 표시는 서버 문자열의 오프셋 벽시계(`formatDateTime`·`formatStamp`)만 쓴다.
 * 대상은 T-ARCH-02와 같은 앱 코드이고, 계약 스위트(`gateway/contract/**`, 앱 번들에 들어가지 않는 테스트 코드)도 테스트로 보고 제외한다.
 * 주석은 검사하지 않는다(규칙을 설명하는 글에 금지 패턴이 나올 수 있다).
 */
const CLOCK_FILE = '../gateway/clock.ts'

const timeSources = import.meta.glob(
  ['../**/*.{ts,tsx}', '!../test/**', '!../**/*.test.{ts,tsx}', '!../**/test{Helpers,Utils}.ts', '!../gateway/contract/**'],
  { query: '?raw', import: 'default', eager: true },
) as Record<string, string>

/** 블록 주석과 줄 주석을 지운다(문자열 안의 `://`는 남긴다). */
function stripComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`\\])\/\/.*$/gm, '$1')
}

const LOCAL_GETTERS = 'get(?:FullYear|Month|Date|Day|Hours|Minutes|Seconds|Milliseconds|Year)'
const LOCAL_SETTERS = 'set(?:FullYear|Month|Date|Hours|Minutes|Seconds|Milliseconds)'
const DATE_OPTION_KEYS = 'dateStyle|timeStyle|timeZone|weekday|era|year|month|day|hour|minute|second'

/** 이름만으로 Date 값으로 보는 수신자(변수 호출 포함). 숫자의 toLocaleString('en-US')는 허용해야 해서 이름으로 좁힌다. */
const DATE_RECEIVER = '(?:\\b(?:d|dt|date|now|time|day)|[A-Za-z0-9_]*(?:Date|Time|At|Day|Stamp|Now))'
/** 오프셋(Z, +09:00) 없이 끝나는 날짜·시각 문자열(템플릿 보간 포함)을 Date로 해석하는 호출. */
const OFFSETLESS_PARSE = '\\b(?:new\\s+Date|Date\\.parse)\\s*\\(\\s*([\'"`])[^\'"`]*[T ]\\d{2}:\\d{2}[\\d:.]*\\1'
const OFFSETLESS_PARSE_TAIL = '\\b(?:new\\s+Date|Date\\.parse)\\s*\\(\\s*([\'"`])[^\'"`]*(?:\\d|\\})T(?:\\$\\{[^}]*\\})?[\\d:.]*\\1'

const FORBIDDEN_TIME: [string, RegExp][] = [
  ['Date.now(', /\bDate\.now\s*\(/],
  ['new Date()', /\bnew\s+Date\s*\(\s*\)/],
  ['getTimezoneOffset', /\bgetTimezoneOffset\b/],
  ['toLocaleDateString/toLocaleTimeString', /\.toLocale(?:Date|Time)String\s*\(/],
  ['toLocaleString of a date', new RegExp(`\\.toLocaleString\\s*\\([^)]*\\b(?:${DATE_OPTION_KEYS})\\b|\\bnew\\s+Date\\s*\\([^)]*\\)\\.toLocaleString`)],
  ['local getters and setters', new RegExp(`\\.(?:${LOCAL_GETTERS}|${LOCAL_SETTERS})\\s*\\(`)],
  ['Intl.DateTimeFormat without timeZone', /\bIntl\.DateTimeFormat\s*\((?![^)]*\btimeZone\b)/],
  ['toLocaleString of a date variable', new RegExp(`${DATE_RECEIVER}\\.toLocaleString\\s*\\(`)],
  ['offsetless date-time string parse', new RegExp(OFFSETLESS_PARSE)],
  ['offsetless date-time template parse', new RegExp(OFFSETLESS_PARSE_TAIL)],
  ['String(new Date(...))', /\bString\s*\(\s*new\s+Date\s*\(/],
  ['Date toString', new RegExp(`\\bnew\\s+Date\\s*\\([^)]*\\)\\.toString\\s*\\(|${DATE_RECEIVER}\\.toString\\s*\\(`)],
  ['resolved browser time zone', /resolvedOptions\s*\(\s*\)\s*\.timeZone/],
]

function timeOffenders(files: [string, string][]): string[] {
  return files.flatMap(([path, text]) => {
    const code = stripComments(text)
    return FORBIDDEN_TIME.filter(([, pattern]) => pattern.test(code)).map(([name]) => `${path}: ${name}`)
  })
}

describe('T-ARCH-03 앱 코드의 브라우저 시계·시간대 경계', () => {
  it('scans real app source files and knows the clock file', () => {
    expect(Object.keys(timeSources).length).toBeGreaterThan(100)
    expect(Object.keys(timeSources)).toContain(CLOCK_FILE)
    expect(Object.keys(timeSources).some((p) => p.includes('/test/'))).toBe(false)
  })

  it('app sources do not read the browser clock or time zone outside gateway/clock.ts', () => {
    const files = Object.entries(timeSources).filter(([path]) => path !== CLOCK_FILE)

    expect(timeOffenders(files)).toEqual([])
  })

  it('keeps the only browser clock read inside gateway/clock.ts', () => {
    expect(stripComments(timeSources[CLOCK_FILE] ?? '')).toMatch(/\bDate\.now\b/)
  })

  it.each([
    'const t = Date.now()',
    'const d = new Date()',
    'new Date( )',
    'd.getTimezoneOffset()',
    "x.toLocaleDateString('ko-KR')",
    'x.toLocaleTimeString()',
    "new Date(iso).toLocaleString('ko-KR', { dateStyle: 'medium', timeStyle: 'short' })",
    "date.toLocaleString('ko-KR', { hour: '2-digit' })",
    'new Date(iso).toLocaleString()',
    'd.getFullYear()',
    'd.getMonth()',
    'd.getDate()',
    'd.getDay()',
    'd.getHours()',
    'd.getMinutes()',
    'd.setDate(d.getDate() + 1)',
    'd.setHours(0)',
    'Intl.DateTimeFormat().resolvedOptions().timeZone',
    "new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium' }).format(d)",
    "new Intl.DateTimeFormat('ko-KR').format(d)",
    'new Intl.DateTimeFormat()',
    'deal.createdAt.toLocaleString()',
    "d.toLocaleString('ko-KR')",
    "actedAt.toLocaleString('ko-KR', opts)",
    'new Date(`${day}T00:00:00`)',
    "new Date('2026-10-23T09:00:00')",
    "new Date('2026-10-23T09:00')",
    "new Date('2026-10-23 09:00')",
    'new Date(`${day}T${time}`)',
    "Date.parse('2026-10-23T09:00:00.000')",
    'String(new Date(iso))',
    'new Date(iso).toString()',
    'createdAt.toString()',
  ])('detects the forbidden form %s (self check of the pattern)', (code) => {
    expect(timeOffenders([['x.ts', code]])).not.toEqual([])
  })

  it.each([
    'const d = new Date(iso)',
    'Date.UTC(2026, 9, 23)',
    'Date.parse(iso)',
    'd.getUTCFullYear()',
    'd.getUTCHours()',
    'd.setUTCDate(d.getUTCDate() + 1)',
    "setDate(e.target.value)",
    "row.users.toLocaleString('en-US')",
    "n.toLocaleString('en-US')",
    "new Intl.DateTimeFormat('ko-KR', { timeZone: 'UTC' }).format(d)",
    "new Intl.DateTimeFormat('ko-KR', {\n dateStyle: 'medium',\n timeZone: 'UTC',\n}).format(d)",
    "new Date('2026-10-23T09:00:00+09:00')",
    "new Date('2026-10-23T00:00:00Z')",
    'new Date(`${day}T00:00:00Z`)',
    'new Date(`${day}T00:00:00${offset}`)',
    "new Date('2026-10-23')",
    'String(count)',
    'row.users.toString()',
    'id.toString()',
    'value.toLocaleString()',
  ])('allows %s (self check of the pattern)', (code) => {
    expect(timeOffenders([['x.ts', code]])).toEqual([])
  })

  it('ignores forbidden words in comments', () => {
    const code = ['// new Date() 대신 useToday', '/* Date.now() 금지 */', 'const url = "http://x/y"', 'const ok = 1 // d.getHours()'].join('\n')

    expect(timeOffenders([['x.ts', code]])).toEqual([])
  })
})

/**
 * T-ARCH-04 (Reports 4단계 AC21, 작성/결과 탭 분리 AC17): 차트 코드(Chart.js)는 차트 타일이 처음 보일 때 받는 lazy 청크에만 있다.
 * 디자이너·보기 화면·결과 패널·타일은 차트 모듈을 정적으로 import하지 않고(타입 import만 허용) 차트 타일이 `chart/ChartTab`을 동적 import한다.
 */
const reportSources = import.meta.glob('../features/reports/**/*.{ts,tsx}', { query: '?raw', import: 'default', eager: true }) as Record<string, string>

const EAGER_FILES = [
  '../features/reports/designer/Designer.tsx',
  '../features/reports/designer/DesignPanel.tsx',
  '../features/reports/view/ReportViewPage.tsx',
  '../features/reports/result/ResultPanel.tsx',
  '../features/reports/result/ResultTiles.tsx',
  '../features/reports/result/TableTile.tsx',
  '../features/reports/result/ChartTile.tsx',
]
const CHART_MODULE = /^(?:chart\.js(?:\/.*)?|react-chartjs-2|chartjs-plugin-datalabels)$|(?:^|\/)chart\/(?:ChartTab|ChartSettingsPanel|ReportChart|chartRegistry|buildChart|pivot)$/
const STATIC_IMPORT = /^import\s+(?!type\b)(?:[^'";]*?\s+from\s+)?['"]([^'"]+)['"]/gm

function staticChartImports(text: string): string[] {
  return [...text.matchAll(STATIC_IMPORT)].map((m) => m[1] ?? '').filter((spec) => CHART_MODULE.test(spec))
}

describe('T-ARCH-04 리포트 차트 코드의 lazy 경계', () => {
  it('has the chart tab module as the lazy entry', () => {
    expect(Object.keys(reportSources)).toContain('../features/reports/chart/ChartTab.tsx')
  })

  it.each(EAGER_FILES)('%s imports no chart module statically', (file) => {
    const text = reportSources[file]

    expect(text).toBeDefined()
    expect(staticChartImports(text ?? '')).toEqual([])
  })

  it('loads the chart tab module through a dynamic import in the chart tile', () => {
    expect(reportSources['../features/reports/result/ChartTile.tsx']).toMatch(/import\(\s*['"][^'"]*chart\/ChartTab['"]\s*\)/)
  })

  it('imports Chart.js only inside the chart folder', () => {
    const offenders = Object.entries(reportSources)
      .filter(([path]) => !/\.test\.tsx?$/.test(path) && !path.includes('/reports/chart/'))
      .filter(([, text]) => staticChartImports(text).length > 0)
      .map(([path]) => path)

    expect(offenders).toEqual([])
  })

  it('detects a static chart import and ignores type imports and dynamic imports (self check of the pattern)', () => {
    expect(staticChartImports("import { Chart } from 'react-chartjs-2'")).toEqual(['react-chartjs-2'])
    expect(staticChartImports("import ChartTab from '../chart/ChartTab'")).toEqual(['../chart/ChartTab'])
    expect(staticChartImports("import type { ChartData } from 'chart.js'")).toEqual([])
    expect(staticChartImports("const Tab = lazy(() => import('../chart/ChartTab'))")).toEqual([])
  })
})
