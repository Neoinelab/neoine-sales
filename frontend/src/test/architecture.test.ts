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
const appSources = import.meta.glob(['../**/*.{ts,tsx}', '!../test/**', '!../**/*.test.{ts,tsx}', '!../mock/testing.ts', '!../**/test{Helpers,Utils}.ts'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const TEST_IMPORT = /(?:from\s+|import\s*\(\s*|import\s+)['"][^'"]*(?:\/test\/|\/mock\/testing|\.\/testing)[^'"]*['"]/

describe('T-ARCH-02 앱 코드의 테스트 픽스처 경계', () => {
  it('scans real app source files', () => {
    expect(Object.keys(appSources).length).toBeGreaterThan(100)
    expect(Object.keys(appSources).some((p) => p.includes('/mock/seed/'))).toBe(true)
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
