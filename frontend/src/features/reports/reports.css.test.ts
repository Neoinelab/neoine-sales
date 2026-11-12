import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { ruleOf, rulesMatching } from '../../test/cssRule'

/** Reports 디자이너 반응형·표시 규칙(정적 점검). jsdom은 CSS를 계산하지 못하므로 선언을 문자열로 읽는다. */

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
  it('디자이너는 왼쪽 250px 필드 패널과 오른쪽 작업 영역의 두 칸이다', () => {
    // when: 디자이너 규칙을 읽는다
    const rule = ruleOf(css, '.report-designer')
    // then: 열이 250px과 1fr이다
    expect(rule).toMatch(/grid-template-columns:\s*250px\s+1fr/)
  })

  it('필드 패널은 넓은 화면에서 위쪽에 붙어 따라온다', () => {
    // when: 필드 패널 규칙을 읽는다
    const rule = ruleOf(css, '.report-fields')
    // then: position이 sticky다
    expect(rule).toMatch(/position:\s*sticky/)
  })

  it('900px 이하에서는 디자이너를 쌓고 640px 이하에서는 조건 행을 두 칸으로 줄인다', () => {
    // when: 900px·640px 미디어 쿼리 안의 규칙을 읽는다
    const narrow = mediaBlock(900)
    const small = mediaBlock(640)
    const designer = ruleOf(narrow, '.report-designer')
    const fields = ruleOf(narrow, '.report-fields')
    const condition = ruleOf(small, '.report-condition')
    // then: 디자이너는 한 칸, 필드 패널은 높이 220px의 정적 배치, 조건 행은 두 칸이다
    expect(designer).toMatch(/grid-template-columns:\s*1fr\s*(;|$)/)
    expect(fields).toMatch(/max-height:\s*220px/)
    expect(fields).toMatch(/position:\s*static/)
    expect(condition).toMatch(/grid-template-columns:\s*1fr\s+1fr/)
  })

  it('숫자 칸은 오른쪽 정렬이고 자릿수 너비가 같다', () => {
    // when: 숫자 칸 규칙을 읽는다
    const rule = ruleOf(css, '.report-num')
    // then: 오른쪽 정렬과 tabular-nums다
    expect(rule).toMatch(/text-align:\s*right/)
    expect(rule).toMatch(/font-variant-numeric:\s*tabular-nums/)
  })

  it('결과 표는 가로로 스크롤된다', () => {
    // when: 결과 표 스크롤 규칙을 읽는다
    const rule = ruleOf(css, '.report-scroll')
    // then: overflow-x가 auto다
    expect(rule).toMatch(/overflow-x:\s*auto/)
  })

  it('Deal 범위와 Action 범위는 각자의 색 토큰을 쓴다', () => {
    // when: 토큰 선언과 범위 규칙을 읽는다
    const deal = ruleOf(css, '.scope-deal')
    const action = ruleOf(css, '.scope-action')
    // then: 두 토큰이 선언되어 있고 범위마다 자기 토큰을 쓴다
    expect(css).toMatch(/--report-deal\s*:/)
    expect(css).toMatch(/--report-action\s*:/)
    expect(deal).toMatch(/var\(--report-deal\)/)
    expect(action).toMatch(/var\(--report-action\)/)
  })

  it('어두운 색 구성표에서도 두 토큰을 다시 정한다', () => {
    // when: 어두운 색 구성표 블록을 읽는다
    const dark = css.slice(css.indexOf('@media (prefers-color-scheme: dark)'))
    // then: 두 토큰이 선언되어 있다
    expect(dark).toMatch(/--report-deal\s*:/)
    expect(dark).toMatch(/--report-action\s*:/)
  })
})

describe('결과 타일 배치 (정적 점검)', () => {
  it('타일은 격자로 배치한다', () => {
    // when: 타일 규칙을 읽는다
    const rule = ruleOf(css, '.report-tiles')
    // then: display가 grid다
    expect(rule).toMatch(/display:\s*grid/)
  })

  it('한 줄 배치는 같은 너비의 두 칸에 나란히 놓는다', () => {
    // when: 한 줄 배치 규칙을 읽는다
    const rule = ruleOf(css, '.report-tiles.is-side')
    // then: 열이 같은 너비 둘이다
    expect(rule).toMatch(/grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(0,\s*1fr\)/)
  })

  it('두 줄 배치는 한 칸에 위아래로 쌓는다', () => {
    // when: 두 줄 배치 규칙을 읽는다
    const rule = ruleOf(css, '.report-tiles.is-stacked')
    // then: 열이 하나다
    expect(rule).toMatch(/grid-template-columns:\s*(?:minmax\(0,\s*1fr\)|1fr)\s*(;|$)/)
  })

  it('900px 이하에서는 저장된 순서를 건드리지 않고 한 줄 배치를 한 칸으로 쌓는다', () => {
    // when: 900px 미디어 쿼리 안의 한 줄 배치 규칙을 읽는다
    const rule = ruleOf(mediaBlock(900), '.report-tiles.is-side')
    // then: 열이 하나다
    expect(rule).toMatch(/grid-template-columns:\s*1fr\s*(;|$)/)
  })

  it.each(['left', 'right', 'top', 'bottom'])('끌어 놓을 %s 가장자리를 타일에 표시하는 규칙이 있다', (edge) => {
    // when: 그 가장자리의 놓기 표시 규칙을 찾는다
    const rules = rulesMatching(css, new RegExp(`\\.report-tile\\.is-drop-${edge}\\b`))
    // then: 규칙이 하나 이상 있다
    expect(rules.length).toBeGreaterThan(0)
  })

  it('한 줄 배치에서 차트 타일은 설정 패널을 차트 아래에 쌓는다', () => {
    // when: 차트 타일 안 규칙을 읽는다
    const rule = ruleOf(css, '.report-tiles.is-side .report-chart-wrap')
    // then: 열이 하나다
    expect(rule).toMatch(/grid-template-columns:\s*1fr\s*(;|$)/)
  })
})
