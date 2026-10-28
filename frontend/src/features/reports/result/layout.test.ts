import { describe, expect, it } from 'vitest'
import type { ReportLayout } from '../../../shared/model/reportTypes'
import { DEFAULT_LAYOUT, describePlacement, dropEdge, keyToEdge, placeTile, sameLayout, visibleTiles } from './layout'

/** 결과 배치 순수 규칙(AC9, AC11, AC12, AC13): 놓는 위치 판정, 타일 놓기, 키보드 대응, 보이는 타일, 안내 문구. */

const RECT = { left: 100, top: 50, width: 200, height: 100 }
const at = (fx: number, fy: number) => ({ x: RECT.left + fx * RECT.width, y: RECT.top + fy * RECT.height })

const layout = (over: Partial<ReportLayout> = {}): ReportLayout => ({ view: 'both', order: ['table', 'chart'], arrange: 'stacked', ...over })

describe('기본 배치', () => {
  it('is both views, the table first and two rows', () => {
    expect(DEFAULT_LAYOUT).toEqual({ view: 'both', order: ['table', 'chart'], arrange: 'stacked' })
  })
})

describe('dropEdge (D6)', () => {
  it.each([
    ['left', 0.1, 0.5],
    ['right', 0.9, 0.5],
    ['top', 0.5, 0.1],
    ['bottom', 0.5, 0.9],
  ] as const)('picks %s for a point near that edge', (edge, fx, fy) => {
    expect(dropEdge(RECT, at(fx, fy))).toBe(edge)
  })

  it('picks the edge with the smallest normalized distance, not the smallest pixel distance', () => {
    // 가로 200, 세로 100: 왼쪽까지 정규화 0.2(40px), 위까지 정규화 0.3(30px) → 픽셀로는 위가 가깝지만 정규화로는 왼쪽
    expect(dropEdge(RECT, { x: RECT.left + 40, y: RECT.top + 30 })).toBe('left')
  })

  it('prefers left when every edge is equally far (the exact center)', () => {
    expect(dropEdge(RECT, at(0.5, 0.5))).toBe('left')
  })

  it('breaks diagonal ties in the order left, right, top, bottom', () => {
    expect(dropEdge(RECT, at(0.25, 0.25))).toBe('left') // 왼쪽 = 위
    expect(dropEdge(RECT, at(0.25, 0.75))).toBe('left') // 왼쪽 = 아래
    expect(dropEdge(RECT, at(0.75, 0.25))).toBe('right') // 오른쪽 = 위
    expect(dropEdge(RECT, at(0.75, 0.75))).toBe('right') // 오른쪽 = 아래
  })

  it('clamps a point outside the rectangle to its border before measuring', () => {
    expect(dropEdge(RECT, { x: 0, y: 100 })).toBe('left')
    expect(dropEdge(RECT, { x: 1000, y: 100 })).toBe('right')
    expect(dropEdge(RECT, { x: 200, y: -500 })).toBe('top')
    expect(dropEdge(RECT, { x: 200, y: 1000 })).toBe('bottom')
    expect(dropEdge(RECT, { x: 1000, y: -500 })).toBe('right') // 오른쪽 = 위 = 0 → 동률은 오른쪽
    expect(dropEdge(RECT, { x: 0, y: 1000 })).toBe('left') // 왼쪽 = 아래 = 0 → 동률은 왼쪽
  })
})

describe('placeTile (AC12)', () => {
  it('puts the table right of the chart: chart then table in one row', () => {
    expect(placeTile(layout(), 'table', 'chart', 'right')).toEqual(layout({ order: ['chart', 'table'], arrange: 'side_by_side' }))
  })

  it('puts the table below the chart: chart then table in two rows', () => {
    expect(placeTile(layout(), 'table', 'chart', 'bottom')).toEqual(layout({ order: ['chart', 'table'], arrange: 'stacked' }))
  })

  it('puts the table left of the chart: table then chart in one row', () => {
    expect(placeTile(layout(), 'table', 'chart', 'left')).toEqual(layout({ order: ['table', 'chart'], arrange: 'side_by_side' }))
  })

  it('puts the table above the chart: table then chart in two rows', () => {
    expect(placeTile(layout({ order: ['chart', 'table'] }), 'table', 'chart', 'top')).toEqual(layout({ order: ['table', 'chart'], arrange: 'stacked' }))
  })

  it.each([
    ['right', ['table', 'chart'], 'side_by_side'],
    ['left', ['chart', 'table'], 'side_by_side'],
    ['bottom', ['table', 'chart'], 'stacked'],
    ['top', ['chart', 'table'], 'stacked'],
  ] as const)('puts the chart %s of the table', (edge, order, arrange) => {
    expect(placeTile(layout(), 'chart', 'table', edge)).toEqual(layout({ order: [...order], arrange }))
  })

  it('returns the same object when a tile is dropped on itself', () => {
    const before = layout()

    expect(placeTile(before, 'chart', 'chart', 'right')).toBe(before)
  })

  it('keeps the view and does not change the given layout', () => {
    const before = Object.freeze(layout({ view: 'chart' }))

    const after = placeTile(before, 'table', 'chart', 'right')

    expect(after.view).toBe('chart')
    expect(before).toEqual(layout({ view: 'chart' }))
  })
})

describe('keyToEdge (AC13)', () => {
  it.each([
    ['ArrowRight', 'right'],
    ['ArrowLeft', 'left'],
    ['ArrowDown', 'bottom'],
    ['ArrowUp', 'top'],
  ] as const)('maps %s to %s', (key, edge) => {
    expect(keyToEdge(key)).toBe(edge)
  })

  it.each(['Enter', ' ', 'a', 'Tab', 'Escape', ''])('maps %j to nothing', (key) => {
    expect(keyToEdge(key)).toBeNull()
  })
})

describe('visibleTiles (AC9, AC11)', () => {
  it('shows both tiles in the layout order', () => {
    expect(visibleTiles(layout(), true)).toEqual(['table', 'chart'])
    expect(visibleTiles(layout({ order: ['chart', 'table'] }), true)).toEqual(['chart', 'table'])
  })

  it('shows only the chart for the chart view and only the table for the table view', () => {
    expect(visibleTiles(layout({ view: 'chart', order: ['chart', 'table'] }), true)).toEqual(['chart'])
    expect(visibleTiles(layout({ view: 'table' }), true)).toEqual(['table'])
  })

  it('shows the table only when there is no chart to show, whatever the view says', () => {
    expect(visibleTiles(layout({ view: 'both' }), false)).toEqual(['table'])
    expect(visibleTiles(layout({ view: 'chart' }), false)).toEqual(['table'])
    expect(visibleTiles(layout({ view: 'table' }), false)).toEqual(['table'])
  })
})

describe('sameLayout', () => {
  it('is true for equal values in different objects', () => {
    expect(sameLayout(layout(), { view: 'both', order: ['table', 'chart'], arrange: 'stacked' })).toBe(true)
  })

  it.each([
    ['view', layout({ view: 'table' })],
    ['order', layout({ order: ['chart', 'table'] })],
    ['arrange', layout({ arrange: 'side_by_side' })],
  ])('is false when %s differs', (_name, other) => {
    expect(sameLayout(layout(), other)).toBe(false)
  })
})

describe('describePlacement (AC13)', () => {
  it('describes a drop in the words of the accessible announcement', () => {
    expect(describePlacement('table', 'chart', 'right')).toBe('표를 차트 오른쪽에 놓았습니다(한 줄)')
    expect(describePlacement('table', 'chart', 'left')).toBe('표를 차트 왼쪽에 놓았습니다(한 줄)')
    expect(describePlacement('table', 'chart', 'bottom')).toBe('표를 차트 아래에 놓았습니다(두 줄)')
    expect(describePlacement('table', 'chart', 'top')).toBe('표를 차트 위에 놓았습니다(두 줄)')
    expect(describePlacement('chart', 'table', 'right')).toBe('차트를 표 오른쪽에 놓았습니다(한 줄)')
  })
})
