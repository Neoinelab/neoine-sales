import { describe, expect, it } from 'vitest'
import type { BantLabel } from '../../../shared/model/types'
import { bantSummary } from './bantSummary'

function label(id: number, category: BantLabel['category'], name: string): BantLabel {
  return { id, category, name, isDefault: false, createdBy: null, createdAt: '2026-10-01T09:00:00+09:00' }
}

const LABELS: BantLabel[] = [
  label(1, 'budget', '단독 예산 확보'),
  label(2, 'authority', 'CEO 보고 완료'),
  label(3, 'need', '컴플라이언스'),
  label(4, 'timeline', '금년 구매'),
]

describe('bantSummary', () => {
  it('lists only chosen categories in B A N T order', () => {
    const result = bantSummary({ timeline: 4, budget: 1, authority: null, need: null }, LABELS)

    expect(result).toEqual([
      { category: 'budget', categoryName: 'Budget', abbr: 'B', labelName: '단독 예산 확보' },
      { category: 'timeline', categoryName: 'Timeline', abbr: 'T', labelName: '금년 구매' },
    ])
  })

  it('returns an empty list when nothing is chosen', () => {
    expect(bantSummary({ budget: null, authority: null, need: null, timeline: null }, LABELS)).toEqual([])
  })

  it('skips ids whose label is unknown', () => {
    const result = bantSummary({ budget: 99, authority: 2, need: null, timeline: null }, LABELS)

    expect(result.map((item: { abbr?: string; category?: string }) => item.category)).toEqual(['authority'])
  })

  it('uses the label of the matching category only', () => {
    // 2은 Authority Label이므로 Budget 자리에 있어도 이름을 빌리지 않는다.
    const result = bantSummary({ budget: 2, authority: null, need: null, timeline: null }, LABELS)

    expect(result).toEqual([])
  })

  it('returns all four items in order when every category is chosen', () => {
    const result = bantSummary({ budget: 1, authority: 2, need: 3, timeline: 4 }, LABELS)

    expect(result.map((item: { abbr?: string; category?: string }) => item.abbr)).toEqual(['B', 'A', 'N', 'T'])
  })
})
