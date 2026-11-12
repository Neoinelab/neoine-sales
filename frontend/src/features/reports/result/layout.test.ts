import { describe, expect, it } from 'vitest'
import type { ReportLayout } from '../../../shared/model/reportTypes'
import { DEFAULT_LAYOUT, describePlacement, dropEdge, keyToEdge, placeTile, sameLayout, visibleTiles } from './layout'

/** 결과 배치 순수 규칙: 놓는 위치 판정, 타일 놓기, 키보드 대응, 보이는 타일, 안내 문구. */

const RECT = { left: 100, top: 50, width: 200, height: 100 }
const at = (fx: number, fy: number) => ({ x: RECT.left + fx * RECT.width, y: RECT.top + fy * RECT.height })

const layout = (over: Partial<ReportLayout> = {}): ReportLayout => ({ view: 'both', order: ['table', 'chart'], arrange: 'stacked', ...over })

describe('기본 배치', () => {
  // 테스트 코드: RS-085
  it('기본 배치는 표+차트, 표가 먼저, 두 줄이다', () => {
    // when: 기본 배치를 읽는다
    const actual = DEFAULT_LAYOUT
    // then: 기본 배치 값이 명세와 같다
    expect(actual).toEqual({ view: 'both', order: ['table', 'chart'], arrange: 'stacked' })
  })
})

describe('dropEdge: 가로 바깥 20%만 left/right, 가운데 60%는 세로 절반으로 top/bottom', () => {
  // 테스트 코드: RS-086
  it.each([
    ['left', 0.1, 0.5],
    ['right', 0.9, 0.5],
    ['top', 0.5, 0.1],
    ['bottom', 0.5, 0.9],
  ] as const)('%s 가장자리 근처의 점은 그 가장자리로 판정한다', (edge, fx, fy) => {
    // when: 타일 안의 비율 위치(가로 fx, 세로 fy)를 놓은 가장자리로 판정한다
    const actual = dropEdge(RECT, at(fx, fy))
    // then: 점의 상대 위치로 가장자리를 고른다
    expect(actual).toBe(edge)
  })

  // 테스트 코드: RS-086
  it('가로 바깥 20%는 세로 위치와 무관하게 왼쪽·오른쪽이다', () => {
    // when: 세로 위치를 바꿔 가며 왼쪽 10%와 오른쪽 90% 점을 판정한다
    const ys = [0, 0.1, 0.5, 0.9, 1]
    const leftEdges = ys.map((fy) => dropEdge(RECT, at(0.1, fy)))
    const rightEdges = ys.map((fy) => dropEdge(RECT, at(0.9, fy)))
    // then: 왼쪽 10%는 left, 오른쪽 90%는 right다
    expect(leftEdges).toEqual(ys.map(() => 'left'))
    expect(rightEdges).toEqual(ys.map(() => 'right'))
  })

  // 테스트 코드: RS-086
  it('가운데 60%는 세로 절반에서 위·아래로 나눈다(정확히 절반은 아래)', () => {
    // when: 가운데 구역 세로 0.49·0.5 위치를 판정한다
    const actual = dropEdge(RECT, at(0.5, 0.49))
    const actual2 = dropEdge(RECT, at(0.5, 0.5))
    const actual3 = dropEdge(RECT, at(0.5, 0.51))
    const actual4 = dropEdge(RECT, at(0.3, 0.2))
    const actual5 = dropEdge(RECT, at(0.7, 0.8))
    // then: 절반 위는 top, 절반부터는 bottom이다
    expect(actual).toBe('top')
    expect(actual2).toBe('bottom')
    expect(actual3).toBe('bottom')
    expect(actual4).toBe('top')
    expect(actual5).toBe('bottom')
  })

  // 테스트 코드: RS-086
  it('정확히 20%·80%는 가운데 구역이고 그 바깥은 왼쪽·오른쪽이다', () => {
    // when: 가로 20%·80% 경계 위치를 판정한다
    const actual = dropEdge(RECT, at(0.2, 0.2))
    const actual2 = dropEdge(RECT, at(0.2, 0.8))
    const actual3 = dropEdge(RECT, at(0.8, 0.2))
    const actual4 = dropEdge(RECT, at(0.8, 0.8))
    const actual5 = dropEdge(RECT, at(0.19, 0.5))
    const actual6 = dropEdge(RECT, at(0.81, 0.5))
    // then: 경계값은 상하 판정이고 0.19·0.81은 좌우 판정이다
    expect(actual).toBe('top')
    expect(actual2).toBe('bottom')
    expect(actual3).toBe('top')
    expect(actual4).toBe('bottom')
    expect(actual5).toBe('left')
    expect(actual6).toBe('right')
  })

  // 테스트 코드: RS-086
  it('넓은 타일에서도 같은 비율로 판정한다', () => {
    // given: 1200x300 타일
    const wide = { left: 0, top: 0, width: 1200, height: 300 }
    // when: 1200x300 타일의 (300,240)과 (300,210) 위치를 판정한다
    const actual = dropEdge(wide, { x: 300, y: 240 })
    const actual2 = dropEdge(wide, { x: 300, y: 210 })
    const actual3 = dropEdge(wide, { x: 300, y: 60 })
    const actual4 = dropEdge(wide, { x: 120, y: 240 })
    const actual5 = dropEdge(wide, { x: 1140, y: 150 })
    const actual6 = dropEdge(wide, { x: 600, y: 30 })
    // then: 가로 25%·세로 70~80%는 bottom이고 바깥 띠는 left/right다
    expect(actual).toBe('bottom')
    expect(actual2).toBe('bottom') // y = 70%
    expect(actual3).toBe('top')
    expect(actual4).toBe('left') // x = 10%
    expect(actual5).toBe('right') // x = 95%
    expect(actual6).toBe('top')
  })

  // 테스트 코드: RS-086
  it('좁고 긴 타일에서도 같은 비율을 쓴다', () => {
    // given: 300x900 타일
    const tall = { left: 0, top: 0, width: 300, height: 900 }
    // when: 300x900 타일의 (30,450)과 (285,450) 위치를 판정한다
    const actual = dropEdge(tall, { x: 30, y: 450 })
    const actual2 = dropEdge(tall, { x: 285, y: 450 })
    const actual3 = dropEdge(tall, { x: 75, y: 720 })
    const actual4 = dropEdge(tall, { x: 75, y: 630 })
    const actual5 = dropEdge(tall, { x: 150, y: 100 })
    // then: 비율이 같다
    expect(actual).toBe('left') // x = 10%
    expect(actual2).toBe('right') // x = 95%
    expect(actual3).toBe('bottom') // x = 25%, y = 80%
    expect(actual4).toBe('bottom') // y = 70%
    expect(actual5).toBe('top')
  })

  // 테스트 코드: RS-086
  it('사각형 밖의 점은 가장자리로 자른 뒤 판정한다', () => {
    // when: 사각형 왼쪽·오른쪽 바깥 점 (0,100)과 (1000,100)을 판정한다
    const actual = dropEdge(RECT, { x: 0, y: 100 })
    const actual2 = dropEdge(RECT, { x: 1000, y: 100 })
    const actual3 = dropEdge(RECT, { x: 1000, y: -500 })
    const actual4 = dropEdge(RECT, { x: 0, y: 1000 })
    const actual5 = dropEdge(RECT, { x: 200, y: -500 })
    const actual6 = dropEdge(RECT, { x: 200, y: 1000 })
    // then: 밖의 좌표도 가장 가까운 가장자리로 판정한다
    expect(actual).toBe('left')
    expect(actual2).toBe('right')
    expect(actual3).toBe('right')
    expect(actual4).toBe('left')
    expect(actual5).toBe('top')
    expect(actual6).toBe('bottom')
  })

  // 테스트 코드: RS-086
  it('크기가 0인 사각형도 오류 없이 판정한다', () => {
    // when: 너비·높이가 0인 사각형 위의 점을 판정한다
    const actual = dropEdge({ left: 10, top: 10, width: 0, height: 0 }, { x: 50, y: 50 })
    const actual2 = dropEdge({ left: 10, top: 10, width: 100, height: 0 }, { x: 60, y: 50 })
    const actual3 = dropEdge({ left: 10, top: 10, width: 0, height: 100 }, { x: 10, y: 90 })
    // then: 예외 없이 값을 돌려준다
    expect(actual).toBe('left')
    expect(actual2).toBe('top')
    expect(actual3).toBe('left')
  })
})

describe('placeTile', () => {
  // 테스트 코드: RS-086
  it('표를 차트 오른쪽에 놓으면 차트 → 표 한 줄이다', () => {
    // when: 표를 차트 오른쪽에 놓는다
    const actual = placeTile(layout(), 'table', 'chart', 'right')
    // then: 차트 → 표, 한 줄이다
    expect(actual).toEqual(layout({ order: ['chart', 'table'], arrange: 'side_by_side' }))
  })

  // 테스트 코드: RS-086
  it('표를 차트 아래에 놓으면 차트 → 표 두 줄이다', () => {
    // when: 표를 차트 아래에 놓는다
    const actual = placeTile(layout(), 'table', 'chart', 'bottom')
    // then: 차트 → 표, 두 줄이다
    expect(actual).toEqual(layout({ order: ['chart', 'table'], arrange: 'stacked' }))
  })

  // 테스트 코드: RS-086
  it('표를 차트 왼쪽에 놓으면 표 → 차트 한 줄이다', () => {
    // when: 표를 차트 왼쪽에 놓는다
    const actual = placeTile(layout(), 'table', 'chart', 'left')
    // then: 표 → 차트, 한 줄이다
    expect(actual).toEqual(layout({ order: ['table', 'chart'], arrange: 'side_by_side' }))
  })

  // 테스트 코드: RS-086
  it('표를 차트 위에 놓으면 표 → 차트 두 줄이다', () => {
    // when: 차트가 먼저인 배치에서 표를 차트 위에 놓는다
    const actual = placeTile(layout({ order: ['chart', 'table'] }), 'table', 'chart', 'top')
    // then: 표 → 차트, 두 줄이다
    expect(actual).toEqual(layout({ order: ['table', 'chart'], arrange: 'stacked' }))
  })

  // 테스트 코드: RS-086
  it.each([
    ['right', ['table', 'chart'], 'side_by_side'],
    ['left', ['chart', 'table'], 'side_by_side'],
    ['bottom', ['table', 'chart'], 'stacked'],
    ['top', ['chart', 'table'], 'stacked'],
  ] as const)('차트를 표의 %s에 놓으면 순서와 줄이 정해진다', (edge, order, arrange) => {
    // when: 차트를 표의 가장자리(오른쪽·왼쪽·아래·위)에 놓는다
    const actual = placeTile(layout(), 'chart', 'table', edge)
    // then: 가장자리에 맞는 순서와 줄이다
    expect(actual).toEqual(layout({ order: [...order], arrange }))
  })

  // 테스트 코드: RS-087
  it('자기 위에 놓으면 같은 객체를 돌려준다', () => {
    // given: 기본 배치
    const before = layout()

    // when: 차트를 차트 자신의 오른쪽에 놓는다
    const actual = placeTile(before, 'chart', 'chart', 'right')
    // then: 같은 객체다
    expect(actual).toBe(before)
  })

  // 테스트 코드: RS-086
  it('보기 방식을 유지하고 받은 배치는 바꾸지 않는다', () => {
    // given: 차트 보기의 얼린 배치
    const before = Object.freeze(layout({ view: 'chart' }))

    // when: 타일을 놓는다
    const after = placeTile(before, 'table', 'chart', 'right')

    // then: 보기가 그대로이고 원본 배치는 바뀌지 않는다
    expect(after.view).toBe('chart')
    expect(before).toEqual(layout({ view: 'chart' }))
  })
})

describe('keyToEdge', () => {
  // 테스트 코드: RS-088
  it.each([
    ['ArrowRight', 'right'],
    ['ArrowLeft', 'left'],
    ['ArrowDown', 'bottom'],
    ['ArrowUp', 'top'],
  ] as const)('%s 키는 %s 가장자리로 바꾼다', (key, edge) => {
    // when: 화살표 키를 가장자리로 바꾼다
    const actual = keyToEdge(key)
    // then: 화살표 키가 가장자리로 대응된다
    expect(actual).toBe(edge)
  })

  // 테스트 코드: RS-088
  it.each(['Enter', ' ', 'a', 'Tab', 'Escape', ''])('%j 키는 대응이 없다', (key) => {
    // when: Enter·공백·문자 등 화살표가 아닌 키를 가장자리로 바꾼다
    const actual = keyToEdge(key)
    // then: 화살표가 아닌 키는 null이다
    expect(actual).toBeNull()
  })
})

describe('visibleTiles', () => {
  // 테스트 코드: RS-085
  it('두 타일을 배치 순서대로 보인다', () => {
    // when: 표가 먼저인 배치와 차트가 먼저인 배치에서 보일 타일을 구한다
    const actual = visibleTiles(layout(), true)
    const actual2 = visibleTiles(layout({ order: ['chart', 'table'] }), true)
    // then: 저장된 순서대로 둘 다 보인다
    expect(actual).toEqual(['table', 'chart'])
    expect(actual2).toEqual(['chart', 'table'])
  })

  // 테스트 코드: RS-085
  it('차트 보기는 차트만, 표 보기는 표만 보인다', () => {
    // when: 차트 보기와 표 보기에서 보일 타일을 구한다
    const actual = visibleTiles(layout({ view: 'chart', order: ['chart', 'table'] }), true)
    const actual2 = visibleTiles(layout({ view: 'table' }), true)
    // then: 보기 방식에 맞는 타일만 보인다
    expect(actual).toEqual(['chart'])
    expect(actual2).toEqual(['table'])
  })

  // 테스트 코드: RS-093
  it('보여 줄 차트가 없으면 보기와 무관하게 표만 보인다', () => {
    // when: 차트를 쓸 수 없는 상태에서 보기별 보일 타일을 구한다
    const actual = visibleTiles(layout({ view: 'both' }), false)
    const actual2 = visibleTiles(layout({ view: 'chart' }), false)
    const actual3 = visibleTiles(layout({ view: 'table' }), false)
    // then: 표 타일만 보인다
    expect(actual).toEqual(['table'])
    expect(actual2).toEqual(['table'])
    expect(actual3).toEqual(['table'])
  })
})

describe('sameLayout', () => {
  it('값이 같으면 다른 객체여도 같다', () => {
    // when: 값이 같은 다른 배치 객체와 비교한다
    const actual = sameLayout(layout(), { view: 'both', order: ['table', 'chart'], arrange: 'stacked' })
    // then: 같다고 판정한다
    expect(actual).toBe(true)
  })

  it.each([
    ['view', layout({ view: 'table' })],
    ['order', layout({ order: ['chart', 'table'] })],
    ['arrange', layout({ arrange: 'side_by_side' })],
  ])('%s이 다르면 다르다', (_name, other) => {
    // when: 보기·순서·줄이 하나씩 다른 배치와 비교한다
    const actual = sameLayout(layout(), other)
    // then: 다르다고 판정한다
    expect(actual).toBe(false)
  })
})

describe('describePlacement', () => {
  // 테스트 코드: RS-088
  it('놓기를 접근성 안내 문구로 설명한다', () => {
    // when: 표를 차트 오른쪽·왼쪽에 놓는 동작의 안내 문구를 만든다
    const actual = describePlacement('table', 'chart', 'right')
    const actual2 = describePlacement('table', 'chart', 'left')
    const actual3 = describePlacement('table', 'chart', 'bottom')
    const actual4 = describePlacement('table', 'chart', 'top')
    const actual5 = describePlacement('chart', 'table', 'right')
    // then: 방향별로 "<타일>을 <타일> <방향> 놓았습니다(<줄>)" 문구다
    expect(actual).toBe('표를 차트 오른쪽에 놓았습니다(한 줄)')
    expect(actual2).toBe('표를 차트 왼쪽에 놓았습니다(한 줄)')
    expect(actual3).toBe('표를 차트 아래에 놓았습니다(두 줄)')
    expect(actual4).toBe('표를 차트 위에 놓았습니다(두 줄)')
    expect(actual5).toBe('차트를 표 오른쪽에 놓았습니다(한 줄)')
  })
})
