import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * 금액은 원 단위로 통일됐으므로 테스트가 아닌 소스(생성 타입 schema.d.ts 포함)에 천원 표기·변환의 잔재가 없다.
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
  // 테스트 코드: UI-031
  it('천원 잔재 금지어 일곱 개를 각각 잡아낸다', () => {
    for (const word of FORBIDDEN) {
      // given: 금지어 하나를 담은 가짜 소스
      const source = `const a = "${word}"`
      // when: 판정한다
      const found = leftovers(source)
      // then: 그 단어로 걸린다
      expect(found).toEqual([word])
    }
  })

  // 테스트 코드: UI-031
  it('원 단위 소스는 통과한다', () => {
    // given: 원 단위 표기만 쓴 가짜 소스
    const source = `export const AMOUNT_LABEL = '금액(단위:원)'; formatWon(1); unit: 'krw'`
    // when: 판정한다
    const found = leftovers(source)
    // then: 위반이 없다
    expect(found).toEqual([])
  })
})

describe('thousand-won guard', () => {
  // 테스트 코드: UI-031
  it('실제 소스 100개 넘는 파일을 검사 대상으로 삼는다', () => {
    // when: 검사 대상 소스를 모은다
    const files = sources(SRC).map((f) => relative(SRC, f))
    // then: 100개가 넘고 money.ts와 생성 타입이 들어 있다
    expect(files.length).toBeGreaterThan(100)
    expect(files).toContain(join('shared', 'model', 'money.ts'))
    expect(files).toContain(join('shared', 'api', 'schema.d.ts'))
  })

  // 테스트 코드: UI-031
  it('실제 소스에는 천원 단어도 도우미도 없다', () => {
    // when: 실제 소스를 모두 판정한다
    const offenders = sources(SRC)
      .map((file) => ({ file: relative(SRC, file), found: leftovers(readFileSync(file, 'utf8')) }))
      .filter((r) => r.found.length > 0)
    // then: 위반 파일이 없다
    expect(offenders.map((o) => o.file).sort()).toEqual([])
  })
})
