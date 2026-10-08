import type { Schemas } from '../../shared/api/client'

export type DealStage = Schemas['DealStage']

/** 파이프라인 표시 순서(API의 단계 순서와 같다). */
export const DEAL_STAGES: readonly DealStage[] = [
  'prospecting',
  'introduction',
  'poc_preparation',
  'poc_completed',
  'technical_evaluation',
  'price_negotiation',
  'contract_completed',
  'lost',
]

/** 단계 코드 → 한글 표시. 생성 타입과 묶여 있어 단계가 추가되면 typecheck가 실패한다. */
export const STAGE_LABEL: Record<DealStage, string> = {
  prospecting: '기회발굴',
  introduction: '제품소개',
  poc_preparation: 'POC준비',
  poc_completed: 'POC완료',
  technical_evaluation: '기술평가',
  price_negotiation: '가격협상',
  contract_completed: '계약완료',
  lost: '실주',
}
