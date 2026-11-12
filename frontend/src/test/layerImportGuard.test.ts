import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

/** 재리뷰 후속 AC12: gateway 매퍼는 features/ 를 import하지 않는다(키 목록은 shared/model에 둔다). */
const SRC = join(__dirname, '..')
const FILE = join('gateway', 'http', 'mappers', 'reportChart.ts')
const IMPORT_FROM = /(?:import|export)\s[^'"]*?from\s*['"]([^'"]+)['"]|import\s*\(\s*['"]([^'"]+)['"]\s*\)/g

describe('gateway layering', () => {
  // gateway의 reportChart 매퍼는 features/를 import하지 않는다.
  it('does not import from features/ in reportChart mapper', () => {
    // given: reportChart 매퍼 소스
    const source = readFileSync(join(SRC, FILE), 'utf8')
    // when: import 경로를 모은다
    const specs = [...source.matchAll(IMPORT_FROM)].map((m) => m[1] ?? m[2] ?? '')
    // then: features/ 경로가 없다
    expect(specs.filter((s) => /(^|\/)features\//.test(s))).toEqual([])
  })
})
