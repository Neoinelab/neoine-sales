import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

/** 재리뷰 후속 AC12: gateway 매퍼는 features/ 를 import하지 않는다(키 목록은 shared/model에 둔다). */
const SRC = join(__dirname, '..')
const FILE = join('gateway', 'http', 'mappers', 'reportChart.ts')
const IMPORT_FROM = /(?:import|export)\s[^'"]*?from\s*['"]([^'"]+)['"]|import\s*\(\s*['"]([^'"]+)['"]\s*\)/g

describe('gateway layering', () => {
  it('does not import from features/ in reportChart mapper', () => {
    const source = readFileSync(join(SRC, FILE), 'utf8')
    const specs = [...source.matchAll(IMPORT_FROM)].map((m) => m[1] ?? m[2] ?? '')

    expect(specs.filter((s) => /(^|\/)features\//.test(s))).toEqual([])
  })
})
