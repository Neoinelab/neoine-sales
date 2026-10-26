import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { ruleOf } from '../../test/cssRule'

/** 본문 영역 여백(2026-10-26): 모든 페이지가 화면 너비를 쓰고 좌우 여백은 각각 5%만 둔다(최대 너비 제한 없음). */

const indexCss = readFileSync('src/index.css', 'utf8')
const contentRules = () => [...indexCss.matchAll(/(?:^|\})\s*\.content\s*\{([^}]*)\}/gm)].map((m) => m[1] ?? '')

describe('본문 영역 좌우 여백 (정적 점검)', () => {
  it('keeps 5% side padding on the page content', () => {
    expect(ruleOf(indexCss, '.content')).toMatch(/padding:\s*24px 5%/)
  })

  it('keeps 5% side padding on narrow screens too', () => {
    const rules = contentRules()
    expect(rules.length).toBeGreaterThan(1)
    for (const rule of rules) expect(rule).toMatch(/padding:\s*\d+px 5%/)
  })

  it('does not cap the content width any more', () => {
    for (const rule of contentRules()) expect(rule).not.toContain('max-width')
  })
})
