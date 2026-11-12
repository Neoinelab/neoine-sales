import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { ruleOf } from '../../test/cssRule'

// vitest는 frontend/ 에서 실행된다. jsdom은 CSS를 계산하지 못하므로 선언을 정적으로 점검한다.
const read = () => readFileSync('src/shared/ui/kvGrid.css', 'utf8')

describe('kvGrid.css (정적 점검)', () => {
  // 테스트 코드: UI-059
  it('글자 크기를 선언하지 않는다', () => {
    // when: CSS를 읽는다
    const css = read()
    // then: font-size가 없다
    expect(css).not.toContain('font-size')
  })

  // 테스트 코드: UI-059
  it('최대 3열로 깔고 좁으면 1열로 접힌다', () => {
    // when: 격자 규칙을 읽는다
    const grid = ruleOf(read(), '.kv-grid')
    // then: auto-fill 최대 3열이다
    expect(grid).toContain('repeat(auto-fill')
    expect(grid).toContain('/ 3)')
  })

  // 테스트 코드: UI-059
  it('라벨은 고정 열에 두고 값은 기준선에 맞춘다', () => {
    // when: 행 규칙과 값 규칙을 읽는다
    const row = ruleOf(read(), '.kv-grid > :is(.kv-row, .field)')
    const value = ruleOf(read(), '.kv-grid dd')
    // then: 두 열·baseline 정렬이고 긴 값은 줄바꿈한다
    expect(row).toContain('var(--kv-label-w) minmax(0, 1fr)')
    expect(row).toContain('align-items: baseline')
    expect(value).toContain('overflow-wrap: anywhere')
  })

  // 테스트 코드: UI-059
  it('콤보 목록에 grid-column을 주는 선택자는 격자 행인 콤보에만 걸린다', () => {
    // 값 칸(dd) 안의 콤보(상세 인라인 편집)는 1열 grid라, 목록에 2열을 주면 폭 0인 암묵 열에 붙어 스크롤바만 보인다.
    // when: CSS의 모든 규칙을 훑는다
    const css = read()
    // then: grid-column을 주는 .combo-list 선택자는 모두 `.kv-grid > `로 시작한다
    for (const m of css.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
      const selector = (m[1] ?? '').trim()
      if (selector.includes('.combo-list') && (m[2] ?? '').includes('grid-column')) {
        expect(selector).toMatch(/^\.kv-grid > /)
      }
    }
  })

  // 테스트 코드: UI-059
  it('긴 값이 자기 열 안에서 줄어들 수 있다', () => {
    // when: 행 규칙을 읽는다
    const row = ruleOf(read(), '.kv-grid > :is(.kv-row, .field)')
    // then: min-width: 0이 있다
    expect(row).toContain('min-width: 0')
  })
})
