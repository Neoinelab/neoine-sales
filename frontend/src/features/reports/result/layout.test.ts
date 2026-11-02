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

describe('dropEdge (D6): 가로 바깥 20%만 left/right, 가운데 60%는 세로 절반으로 top/bottom', () => {
  it.each([
    ['left', 0.1, 0.5],
    ['right', 0.9, 0.5],
    ['top', 0.5, 0.1],
    ['bottom', 0.5, 0.9],
  ] as const)('picks %s for a point near that edge', (edge, fx, fy) => {
    expect(dropEdge(RECT, at(fx, fy))).toBe(edge)
  })

  it('picks left or right in the outer 20% whatever the vertical position', () => {
    for (const fy of [0, 0.1, 0.5, 0.9, 1]) {
      expect(dropEdge(RECT, at(0.1, fy))).toBe('left')
      expect(dropEdge(RECT, at(0.9, fy))).toBe('right')
    }
  })

  it('splits the middle 60% at the vertical half: top above, bottom from the half', () => {
    expect(dropEdge(RECT, at(0.5, 0.49))).toBe('top')
    expect(dropEdge(RECT, at(0.5, 0.5))).toBe('bottom')
    expect(dropEdge(RECT, at(0.5, 0.51))).toBe('bottom')
    expect(dropEdge(RECT, at(0.3, 0.2))).toBe('top')
    expect(dropEdge(RECT, at(0.7, 0.8))).toBe('bottom')
  })

  it('treats exactly 20% and 80% as the middle zone and just outside as left/right', () => {
    expect(dropEdge(RECT, at(0.2, 0.2))).toBe('top')
    expect(dropEdge(RECT, at(0.2, 0.8))).toBe('bottom')
    expect(dropEdge(RECT, at(0.8, 0.2))).toBe('top')
    expect(dropEdge(RECT, at(0.8, 0.8))).toBe('bottom')
    expect(dropEdge(RECT, at(0.19, 0.5))).toBe('left')
    expect(dropEdge(RECT, at(0.81, 0.5))).toBe('right')
  })

  it('on a wide 1200x300 tile, x=25% and y=70..80% is bottom (it used to be left at 70%)', () => {
    const wide = { left: 0, top: 0, width: 1200, height: 300 }
    expect(dropEdge(wide, { x: 300, y: 240 })).toBe('bottom')
    expect(dropEdge(wide, { x: 300, y: 210 })).toBe('bottom') // y = 70%
    expect(dropEdge(wide, { x: 300, y: 60 })).toBe('top')
    expect(dropEdge(wide, { x: 120, y: 240 })).toBe('left') // x = 10%
    expect(dropEdge(wide, { x: 1140, y: 150 })).toBe('right') // x = 95%
    expect(dropEdge(wide, { x: 600, y: 30 })).toBe('top')
  })

  it('uses the same ratios on a narrow 300x900 tile', () => {
    const tall = { left: 0, top: 0, width: 300, height: 900 }
    expect(dropEdge(tall, { x: 30, y: 450 })).toBe('left') // x = 10%
    expect(dropEdge(tall, { x: 285, y: 450 })).toBe('right') // x = 95%
    expect(dropEdge(tall, { x: 75, y: 720 })).toBe('bottom') // x = 25%, y = 80%
    expect(dropEdge(tall, { x: 75, y: 630 })).toBe('bottom') // y = 70%
    expect(dropEdge(tall, { x: 150, y: 100 })).toBe('top')
  })

  it('clamps a point outside the rectangle to its border before judging', () => {
    expect(dropEdge(RECT, { x: 0, y: 100 })).toBe('left')
    expect(dropEdge(RECT, { x: 1000, y: 100 })).toBe('right')
    expect(dropEdge(RECT, { x: 1000, y: -500 })).toBe('right')
    expect(dropEdge(RECT, { x: 0, y: 1000 })).toBe('left')
    expect(dropEdge(RECT, { x: 200, y: -500 })).toBe('top')
    expect(dropEdge(RECT, { x: 200, y: 1000 })).toBe('bottom')
  })

  it('works for zero-size rectangles without throwing', () => {
    expect(dropEdge({ left: 10, top: 10, width: 0, height: 0 }, { x: 50, y: 50 })).toBe('left')
    expect(dropEdge({ left: 10, top: 10, width: 100, height: 0 }, { x: 60, y: 50 })).toBe('top')
    expect(dropEdge({ left: 10, top: 10, width: 0, height: 100 }, { x: 10, y: 90 })).toBe('left')
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
