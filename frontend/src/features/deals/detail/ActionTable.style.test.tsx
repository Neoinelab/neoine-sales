import { readFileSync } from 'node:fs'
import { within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { bodyRows, openActionsTab } from '../../../test/actionDetail'
import { ruleOf } from '../../../test/cssRule'

// vitest는 frontend/ 에서 실행된다.
const detailCss = readFileSync('src/features/deals/detail/detail.css', 'utf8')

/** 이 요소에 걸리는 규칙(선택자가 요소와 맞는 것)의 선언을 이어 붙인다. 선언 순서·우선순위는 보지 않는다. */
function declarationsFor(element: Element): string {
  const bodies: string[] = []
  for (const m of detailCss.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
    const matched = (m[1] ?? '').split(',').some((selector) => {
      try {
        return element.matches(selector.trim())
      } catch {
        return false
      }
    })
    if (matched) bodies.push(m[2] ?? '')
  }
  return bodies.join(';')
}

describe('Action 목록 표 칸 폭 (정적 점검)', () => {
  // 진행사항·Next Action 칸은 최소 40em이고 최대 폭 제한이 없으며, 짧은 칸은 줄바꿈하지 않는다.
  // 테스트 코드: AC-142
  it('gives progress and next action cells min-width 40em without a max-width and keeps the short cells on one line', async () => {
    // given: Actions 탭의 첫 행(열 순서: 수행일·유형·진행사항·Next Action·Due Date·상태)
    const { table } = await openActionsTab()
    const cells = within(bodyRows(table)[0]!).getAllByRole('cell')

    // when·then: 진행사항·Next Action 칸에 걸리는 규칙은 min-width 40em이고 max-width가 없다
    for (const index of [2, 3]) {
      const css = declarationsFor(cells[index]!)
      expect(css).toMatch(/min-width:\s*40em/)
      expect(css).not.toMatch(/max-width/)
    }
    // then: 수행일·유형·Due Date·상태 칸에 걸리는 규칙은 줄바꿈하지 않는다
    for (const index of [0, 1, 4, 5]) {
      expect(declarationsFor(cells[index]!)).toMatch(/white-space:\s*nowrap/)
    }
  })

  // 다른 표의 공통 `.dd-table td.wrap` 규칙(최대 280px)은 그대로다.
  // 테스트 코드: AC-142
  it('keeps the shared wrap rule at 280px for the other tables', () => {
    // when: 공통 규칙을 읽는다
    const rule = ruleOf(detailCss, '.dd-table td.wrap')
    // then: 최대 폭 280px이 남아 있다
    expect(rule).toMatch(/max-width:\s*280px/)
  })
})
