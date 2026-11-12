import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { ruleOf } from '../../test/cssRule'

/** 본문 영역 여백: 모든 페이지가 화면 너비를 쓰고 좌우 여백은 각각 5%만 둔다(최대 너비 제한 없음, UI-R38). */

const indexCss = readFileSync('src/index.css', 'utf8')
const contentRules = () => [...indexCss.matchAll(/(?:^|\})\s*\.content\s*\{([^}]*)\}/gm)].map((m) => m[1] ?? '')

describe('본문 영역 좌우 여백 (정적 점검)', () => {
  // 테스트 코드: UI-060
  it('기본 규칙은 좌우 5% 여백이다', () => {
    // when: .content 기본 규칙을 읽는다
    const rule = ruleOf(indexCss, '.content')
    // then: padding이 24px 5%다
    expect(rule).toMatch(/padding:\s*24px 5%/)
  })

  // 테스트 코드: UI-060
  it('좁은 화면 규칙도 좌우 5% 여백을 유지한다', () => {
    // when: 모든 .content 규칙을 읽는다
    const rules = contentRules()
    // then: 규칙이 둘 이상이고 모두 좌우 5%다
    expect(rules.length).toBeGreaterThan(1)
    for (const rule of rules) expect(rule).toMatch(/padding:\s*\d+px 5%/)
  })

  // 테스트 코드: UI-060
  it('본문 최대 너비를 제한하지 않는다', () => {
    // when: 모든 .content 규칙을 읽는다
    const rules = contentRules()
    // then: max-width가 없다
    for (const rule of rules) expect(rule).not.toContain('max-width')
  })
})
