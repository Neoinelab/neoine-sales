import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { ruleOf, rulesMatching } from '../../test/cssRule'

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

describe('결과 타일 배치 (정적 점검, 작성/결과 탭 분리 AC12, AC14, AC16)', () => {
  it('lays the tiles out as a grid', () => {
    expect(ruleOf(css, '.report-tiles')).toMatch(/display:\s*grid/)
  })

  it('puts the tiles of one row side by side with the same width', () => {
    expect(ruleOf(css, '.report-tiles.is-side')).toMatch(/grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(0,\s*1fr\)/)
  })

  it('puts the tiles of two rows on top of each other', () => {
    expect(ruleOf(css, '.report-tiles.is-stacked')).toMatch(/grid-template-columns:\s*(?:minmax\(0,\s*1fr\)|1fr)\s*(;|$)/)
  })

  it('stacks the one-row layout into one column at 900px and below without touching the saved order', () => {
    const narrow = mediaBlock(900)
    expect(ruleOf(narrow, '.report-tiles.is-side')).toMatch(/grid-template-columns:\s*1fr\s*(;|$)/)
  })

  it.each(['left', 'right', 'top', 'bottom'])('marks the %s edge of the tile a drop would go to', (edge) => {
    expect(rulesMatching(css, new RegExp(`\\.report-tile\\.is-drop-${edge}\\b`)).length).toBeGreaterThan(0)
  })

  it('lets the chart tile stack the settings panel under the chart in the one-row layout', () => {
    expect(ruleOf(css, '.report-tiles.is-side .report-chart-wrap')).toMatch(/grid-template-columns:\s*1fr\s*(;|$)/)
  })
})
