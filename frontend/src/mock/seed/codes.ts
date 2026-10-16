import { LOCKED_KEYS, type BantCategory } from '../../shared/model/constants'
import type { Code, ForecastOutcome } from '../../shared/model/types'
import { takeId, type LabelRecord } from '../store'
import type { SeedEnv } from './env'

const STATUSES: readonly (readonly [string, string])[] = [
  ['prospecting', '기회발굴'],
  ['introduction', '제품소개'],
  ['poc_preparation', 'POC준비'],
  ['poc_completed', 'POC완료'],
  ['technical_evaluation', '기술평가'],
  ['price_negotiation', '가격협상'],
  ['contract_completed', '계약완료'],
]

const FORECASTS: readonly (readonly [string, string, ForecastOutcome, string | null])[] = [
  ['pipeline', 'Pipeline', 'open', '0–50'],
  ['best', 'Best', 'open', '51–75'],
  ['most_likely', 'Most Likely', 'open', '75–85'],
  ['commit', 'Commit', 'open', '85–100'],
  ['won', 'Won', 'won', null],
  ['lost', 'Lost', 'lost', null],
]

/** Status 7개 + Forecast 6개. 시스템 연결 코드 5개(`LOCKED_KEYS`)는 locked. */
export function seedCodes(counters: Record<string, number>): Code[] {
  const statuses: Code[] = STATUSES.map(([key, name], index) => ({
    id: takeId(counters, 'cd'),
    kind: 'status',
    key,
    name,
    order: index + 1,
    locked: (LOCKED_KEYS.status as readonly string[]).includes(key),
    outcome: 'open',
    probabilityHint: null,
  }))
  const forecasts: Code[] = FORECASTS.map(([key, name, outcome, hint], index) => ({
    id: takeId(counters, 'cd'),
    kind: 'forecast',
    key,
    name,
    order: index + 1,
    locked: (LOCKED_KEYS.forecast as readonly string[]).includes(key),
    outcome,
    probabilityHint: hint,
  }))
  return [...statuses, ...forecasts]
}

/** PRD 6.4 BANT 기본 Label. 점수는 두지 않는다. */
const LABELS: Record<BantCategory, readonly string[]> = {
  budget: ['단독 예산 확보', '풀 예산 확보', '잔여 예산 활용', '예산 작업중', '내년 예산', '예산 없음', '미확인'],
  authority: ['CEO 보고 완료', 'CISO 보고 완료', '팀장 보고 완료', '팀장 검토', '담당자 검토', '모름'],
  need: ['보안 사고 발생', 'CISO 지시', '보안 강화 요건', '컴플라이언스', '모름'],
  timeline: ['금년 구매', 'POC 후 일정수립', '기술평가만 진행', '내년구매', '미확정'],
}

export function seedLabels(env: SeedEnv, counters: Record<string, number>): LabelRecord[] {
  const out: LabelRecord[] = []
  for (const category of Object.keys(LABELS) as BantCategory[]) {
    for (const name of LABELS[category]) {
      out.push({ id: takeId(counters, 'lb'), category, name, isDefault: true, createdById: null, createdAt: env.at(300, 9) })
    }
  }
  return out
}
