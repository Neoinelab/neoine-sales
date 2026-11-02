import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * AC-10: 금액은 원 단위로 통일됐으므로 테스트가 아닌 소스(생성 타입 schema.d.ts 포함)에 천원 표기·변환의 잔재가 없다.
 * 계약 테스트 도구(`gateway/contract`)는 예전 포맷 거절 목록에 `krw_thousand`를 유지하므로 제외한다.
 * 판정 함수 `leftovers`는 아래 가짜 소스로 따로 검증한다.
 */
const SRC = join(__dirname, '..')
const FORBIDDEN = ['천원', 'toThousandWon', 'formatThousandWon', 'isThousandWonColumn', 'THOUSAND_WON_MAX', 'isSameShownAmount', 'krw_thousand']

export function leftovers(source: string): string[] {
  return FORBIDDEN.filter((word) => source.includes(word))
}

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return ['test', join('gateway', 'contract')].includes(relative(SRC, path)) ? [] : sources(path)
    return /\.tsx?$/.test(path) && !/\.test\.tsx?$/.test(path) ? [path] : []
  })
}

describe('leftovers()', () => {
  it('flags every thousand-won leftover', () => {
    for (const word of FORBIDDEN) expect(leftovers(`const a = "${word}"`)).toEqual([word])
  })

  it('accepts won-based sources', () => {
    expect(leftovers(`export const AMOUNT_LABEL = '금액(단위:원)'; formatWon(1); unit: 'krw'`)).toEqual([])
  })
})

describe('thousand-won guard', () => {
  it('scans the real source files', () => {
    const files = sources(SRC).map((f) => relative(SRC, f))
    expect(files.length).toBeGreaterThan(100)
    expect(files).toContain(join('shared', 'model', 'money.ts'))
    expect(files).toContain(join('shared', 'api', 'schema.d.ts'))
  })

  it('finds no thousand-won word or helper in the sources', () => {
    const offenders = sources(SRC)
      .map((file) => ({ file: relative(SRC, file), found: leftovers(readFileSync(file, 'utf8')) }))
      .filter((r) => r.found.length > 0)
    expect(offenders.map((o) => o.file).sort()).toEqual([])
  })
})
