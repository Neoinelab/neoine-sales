import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { ruleOf } from '../../../test/cssRule'

// vitest는 frontend/ 에서 실행된다. jsdom은 CSS를 계산하지 못하므로 선언을 문자열로 점검한다.
const css = readFileSync('src/features/deals/list/list.css', 'utf8')

describe('빠른 조건 줄 스타일 (정적 점검)', () => {
  it('빠른 조건 줄은 전체 폭에 줄바꿈되는 flex 줄이다', () => {
    // when: 규칙을 읽는다
    const rule = ruleOf(css, '.deal-filter-actions')
    // then: 전체 폭 flex이고 줄바꿈된다
    expect(rule).toContain('grid-column: 1 / -1')
    expect(rule).toContain('display: flex')
    expect(rule).toContain('flex-wrap: wrap')
  })

  it('체크박스 세 개를 한 줄에 둔다', () => {
    // when: 플래그 줄 규칙이 줄바꿈하지 않는다
    const actual = ruleOf(css, '.deal-filter-flags')
    // then: 체크박스 줄이 줄바꿈하지 않는다
    expect(actual).toContain('flex-wrap: nowrap')
  })

  it('버튼을 오른쪽 끝으로 민다', () => {
    // when: 버튼 묶음 규칙의 왼쪽 여백이 auto이다
    const actual = ruleOf(css, '.deal-filter-actions .filter-buttons')
    // then: 버튼 묶음의 왼쪽 여백이 auto이다
    expect(actual).toContain('margin-left: auto')
  })

  it('오류 영역은 전체 폭으로 보이고 비어 있으면 숨긴다', () => {
    // when: 오류 영역 규칙과 빈 상태 규칙을 확인한다
    const actual1 = ruleOf(css, '.deal-filter-errors')
    const actual2 = ruleOf(css, '.deal-filter-errors:empty')
    // then: 오류 영역은 전체 폭이고 비면 display: none이다
    expect(actual1).toContain('grid-column: 1 / -1')
    expect(actual2).toContain('display: none')
  })
})

describe('Deal 이름 칸의 경고 배지 (정적 점검, 2026-10-26)', () => {
  it('기한초과·미업데이트 배지는 Deal 이름 오른쪽 같은 줄에 놓인다', () => {
    // when: Deal 이름 칸 규칙을 읽는다
    const rule = ruleOf(css, '.deal-name')
    // then: 가로 flex이고 세로 쌓기·grid가 아니며 가운데 정렬이다
    expect(rule).toMatch(/display:\s*flex/)
    expect(rule).not.toMatch(/display:\s*grid/)
    expect(rule).not.toMatch(/flex-direction:\s*column/)
    expect(rule).toMatch(/align-items:\s*center/)
  })
})
