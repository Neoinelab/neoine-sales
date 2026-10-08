import { describe, expect, it } from 'vitest'
import { DEAL_STAGES, STAGE_LABEL } from './stages'

describe('deal stages', () => {
  it('has a Korean label for every stage in pipeline order', () => {
    expect(DEAL_STAGES).toEqual([
      'prospecting',
      'introduction',
      'poc_preparation',
      'poc_completed',
      'technical_evaluation',
      'price_negotiation',
      'contract_completed',
      'lost',
    ])
    expect(DEAL_STAGES.map((stage) => STAGE_LABEL[stage])).toEqual([
      '기회발굴',
      '제품소개',
      'POC준비',
      'POC완료',
      '기술평가',
      '가격협상',
      '계약완료',
      '실주',
    ])
  })

  it('has no label for anything but the eight stages', () => {
    expect(Object.keys(STAGE_LABEL).sort()).toEqual([...DEAL_STAGES].sort())
  })
})
