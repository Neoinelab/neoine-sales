import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { ruleOf } from '../../test/cssRule'

/** Reports 디자이너 반응형·표시 규칙(정적 점검, Reports AC19). jsdom은 CSS를 계산하지 못하므로 선언을 문자열로 읽는다. */

const css = readFileSync('src/features/reports/reports.css', 'utf8')

/** `@media (max-width: <px>px) { ... }` 블록의 안쪽 본문(중첩 중괄호를 센다). */
function mediaBlock(width: number): string {
  const start = css.indexOf(`@media (max-width: ${width}px)`)
  if (start < 0) throw new Error(`미디어 쿼리 없음: ${width}px`)
  const open = css.indexOf('{', start)
  let depth = 0
  for (let i = open; i < css.length; i += 1) {
    if (css[i] === '{') depth += 1
    if (css[i] === '}') {
      depth -= 1
      if (depth === 0) return css.slice(open + 1, i)
    }
  }
  throw new Error('미디어 쿼리가 닫히지 않음')
}

describe('Reports 디자이너 배치 (정적 점검)', () => {
  it('lays the designer out as a 250px field panel next to the work area', () => {
    expect(ruleOf(css, '.report-designer')).toMatch(/grid-template-columns:\s*250px\s+1fr/)
  })

  it('keeps the field panel sticky on wide screens', () => {
    expect(ruleOf(css, '.report-fields')).toMatch(/position:\s*sticky/)
  })

  it('stacks the designer at 900px and the condition row at 640px', () => {
    const narrow = mediaBlock(900)
    expect(ruleOf(narrow, '.report-designer')).toMatch(/grid-template-columns:\s*1fr\s*(;|$)/)
    expect(ruleOf(narrow, '.report-fields')).toMatch(/max-height:\s*220px/)
    expect(ruleOf(narrow, '.report-fields')).toMatch(/position:\s*static/)

    const small = mediaBlock(640)
    expect(ruleOf(small, '.report-condition')).toMatch(/grid-template-columns:\s*1fr\s+1fr/)
  })

  it('aligns numbers to the right with tabular digits', () => {
    const rule = ruleOf(css, '.report-num')
    expect(rule).toMatch(/text-align:\s*right/)
    expect(rule).toMatch(/font-variant-numeric:\s*tabular-nums/)
  })

  it('scrolls the result table sideways', () => {
    expect(ruleOf(css, '.report-scroll')).toMatch(/overflow-x:\s*auto/)
  })

  it('colors the Deal and Action scopes with their own tokens', () => {
    expect(css).toMatch(/--report-deal\s*:/)
    expect(css).toMatch(/--report-action\s*:/)
    expect(ruleOf(css, '.scope-deal')).toMatch(/var\(--report-deal\)/)
    expect(ruleOf(css, '.scope-action')).toMatch(/var\(--report-action\)/)
  })

  it('keeps the tokens readable in the dark color scheme', () => {
    const dark = css.slice(css.indexOf('@media (prefers-color-scheme: dark)'))
    expect(dark).toMatch(/--report-deal\s*:/)
    expect(dark).toMatch(/--report-action\s*:/)
  })
})
