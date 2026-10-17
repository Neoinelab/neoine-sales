import { BANT_CATEGORIES, BANT_CATEGORY_NAMES } from '../../../shared/model/constants'
import type { BantCategory, BantLabel, DealRow } from '../../../shared/model/types'

export interface BantSummaryItem {
  category: BantCategory
  categoryName: string
  abbr: 'B' | 'A' | 'N' | 'T'
  labelName: string
}

const ABBR: Record<BantCategory, BantSummaryItem['abbr']> = { budget: 'B', authority: 'A', need: 'N', timeline: 'T' }

/** 목록 BANT 칸용: 선택된 구분만 B→A→N→T 순서로. 이름을 못 찾은 id(다른 구분 Label 포함)는 제외한다. */
export function bantSummary(bant: DealRow['bant'], labels: readonly BantLabel[]): BantSummaryItem[] {
  const items: BantSummaryItem[] = []
  for (const category of BANT_CATEGORIES) {
    const id = bant[category]
    if (id === null) continue
    const label = labels.find((l) => l.id === id && l.category === category)
    if (!label) continue
    items.push({ category, categoryName: BANT_CATEGORY_NAMES[category], abbr: ABBR[category], labelName: label.name })
  }
  return items
}
