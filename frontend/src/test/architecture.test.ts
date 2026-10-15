import { describe, expect, it } from 'vitest'

/**
 * T-ARCH-01: 화면(features)은 `shared/api`와 `mock/`을 직접 import하지 않는다.
 * 화면은 `data/*` 훅만 쓰고, 훅이 게이트웨이를 안다. 실제 연동으로 바꿀 때 mock만 지울 수 있어야 한다.
 */
const sources = import.meta.glob('../features/**/*.{ts,tsx}', { query: '?raw', import: 'default', eager: true }) as Record<
  string,
  string
>

const FORBIDDEN = /(?:from\s+|import\s*\(\s*|import\s+)['"][^'"]*(?:shared\/api|\/mock)(?:\/[^'"]*)?['"]/

function featureSources(): [string, string][] {
  return Object.entries(sources).filter(([path]) => !/\.test\.tsx?$/.test(path))
}

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
    expect(FORBIDDEN.test("import { useDeals } from '../../data/deals'")).toBe(false)
    expect(FORBIDDEN.test("import type { Deal } from '../../shared/model/types'")).toBe(false)
  })
})
