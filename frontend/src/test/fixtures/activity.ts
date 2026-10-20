/** 시드 Action과 Deal History 생성. Action은 Deal마다 가장 최근 것부터 SPACING일 간격으로 과거로 만든다. */

import { addDays } from '../../shared/model/dates'
import { AMOUNT_LABEL, formatThousandWon } from '../../shared/model/money'
import { withWa } from '../../shared/model/text'
import type { Code, Contact, Deal, HistoryCategory } from '../../shared/model/types'
import { nextSeq, takeId, type ActionRecord, type HistoryRecord } from '../fake/store'
import { findSeedContact } from './contacts'
import { ACTION_SPACING, actionHour, type DealSpec } from './dealSpecs'
import { DEFAULT_ACTION_TYPE_NAMES, seedActionTypeId } from '../fake/seed/actionTypes'
import type { SeedEnv } from '../fake/seed/env'

type ActionType = (typeof DEFAULT_ACTION_TYPE_NAMES)[number]

const PROGRESS: Record<ActionType, readonly string[]> = {
  통화: ['담당자와 통화로 일정 협의', '요구사항 전화 확인', '예산 집행 시기 전화 확인'],
  미팅: ['고객사 방문 미팅 진행', '화상 미팅으로 요구사항 정리', '의사결정자 미팅'],
  이메일: ['소개 자료 이메일 발송', '질의 회신 이메일 전달', '견적 자료 이메일 발송'],
  데모: ['제품 데모 진행', '현업 대상 시연', '기술 담당자 대상 데모'],
  제안: ['제안서 전달', '수정 제안서 전달', '범위 조정안 제안'],
  협상: ['가격 협상 진행', '조건 조율', '납기 및 지원 범위 협의'],
  계약: ['계약서 초안 검토', '계약 조건 최종 확인', '계약 체결 절차 안내'],
  기타: ['내부 검토 진행', '사내 공유 및 방향 논의', '경쟁사 동향 조사'],
}

const NEXT: Record<ActionType, readonly string[]> = {
  통화: ['회의 일정 확정', '자료 회신 확인', '예산 담당자 연결'],
  미팅: ['미팅 결과 정리 후 공유', '후속 미팅 일정 확정', '기술 검토 요청'],
  이메일: ['회신 확인', '자료 보완 전달', '견적 재송부'],
  데모: ['데모 피드백 수렴', 'POC 범위 확정', '후속 기술 질의 대응'],
  제안: ['제안 검토 결과 확인', '가격 조정안 준비', '임원 보고 자료 지원'],
  협상: ['최종 가격 확정', '조건 합의서 작성', '계약 일정 협의'],
  계약: ['날인본 수령', '발주서 확인', '납품 일정 조율'],
  기타: ['담당자 의견 수렴', '내부 승인 대기', '후속 일정 확인'],
}

const FORECAST_LEAN = { won: 'commit', lost: 'best' } as const

interface Names {
  status(key: string): string
  forecast(key: string): string
  user(id: string): string
  contact(id: string): string
}

function namesOf(codes: readonly Code[], userNames: ReadonlyMap<string, string>, contacts: readonly Contact[]): Names {
  const nameOf = (kind: Code['kind']) => (key: string) => codes.find((c) => c.kind === kind && c.key === key)?.name ?? key
  return {
    status: nameOf('status'),
    forecast: nameOf('forecast'),
    user: (id) => userNames.get(id) ?? id,
    contact: (id) => {
      const c = contacts.find((x) => x.id === id)
      return c ? `${c.company} ${c.name}` : id
    },
  }
}

interface Draft {
  type: ActionType
  progress: string
  nextAction: string
  statusKey: string
  forecastKey: string
}

/** i=0이 가장 최근. 종결 Deal의 마지막 Action은 계약/협상 결과를 담는다. */
function draftOf(spec: DealSpec, i: number, statusKeys: readonly string[]): Draft {
  const back = i === 0 ? 0 : 1 + Math.floor((i - 1) / 2)
  const statusKey = statusKeys[Math.max(0, statusKeys.indexOf(spec.status) - back)] ?? spec.status
  const lean = FORECAST_LEAN[spec.forecast as keyof typeof FORECAST_LEAN]
  const forecastKey = i === 0 || lean === undefined ? spec.forecast : lean
  const type = DEFAULT_ACTION_TYPE_NAMES[(spec.no + i * 3) % DEFAULT_ACTION_TYPE_NAMES.length] ?? '기타'
  const pick = (pool: readonly string[]) => pool[(spec.no + i) % pool.length] ?? ''
  const base = { type, progress: `${spec.solution} ${pick(PROGRESS[type])}`, nextAction: pick(NEXT[type]), statusKey, forecastKey }
  if (i === 0 && spec.forecast === 'won') return { ...base, type: '계약', progress: '계약 체결 및 매출 확정', nextAction: '납품 및 검수 일정 확인' }
  if (i === 0 && spec.forecast === 'lost') return { ...base, type: '협상', progress: '경쟁사 가격 제시로 검토 보류', nextAction: '사후 피드백 요청' }
  if (spec.no === 1 && i === 0) return { ...base, type: '협상', progress: '최종 가격 협의', nextAction: '계약서 초안 검토' }
  if (spec.no === 1 && i === 1) return { ...base, type: '이메일', progress: '임원 보고용 ROI 자료 전달', nextAction: '최종 가격 협의 일정 확정' }
  return base
}

export interface Activity {
  actions: ActionRecord[]
  history: HistoryRecord[]
}

export function seedActivity(
  env: SeedEnv,
  specs: readonly DealSpec[],
  deals: readonly Deal[],
  codes: readonly Code[],
  contacts: readonly Contact[],
  userNames: ReadonlyMap<string, string>,
  counters: Record<string, number>,
): Activity {
  const names = namesOf(codes, userNames, contacts)
  const statusKeys = codes.filter((c) => c.kind === 'status').map((c) => c.key)
  const actions: ActionRecord[] = []
  const history: HistoryRecord[] = []
  const log = (dealCode: string, at: string, byId: string, category: HistoryCategory, target: string, before: string, after: string) => {
    history.push({ id: takeId(counters, 'hi'), seq: nextSeq(counters), dealCode, at, byId, category, target, before, after })
  }

  for (const spec of specs) {
    const deal = deals.find((d) => d.code.endsWith(`-D${String(spec.no).padStart(3, '0')}`))
    if (!deal) throw new Error(`시드 Deal 없음: ${spec.no}`)
    log(deal.code, deal.createdAt, deal.ownerId, 'created', 'Deal 등록', '', 'Deal 등록')

    let previous: Draft | null = null
    for (let i = spec.count - 1; i >= 0; i -= 1) {
      const draft = draftOf(spec, i, statusKeys)
      const ago = spec.lastAgo + ACTION_SPACING * i
      const actedAt = env.at(ago, actionHour(spec.no, i))
      actions.push({
        id: takeId(counters, 'act'),
        dealCode: deal.code,
        actedAt,
        actorId: deal.ownerId,
        typeId: seedActionTypeId(draft.type),
        progress: draft.progress,
        nextAction: draft.nextAction,
        dueDate: i === 0 ? env.date(spec.due) : addDays(actedAt.slice(0, 10), 7),
        nextActionStatus: 'open',
        nextActionClosedAt: null,
        memo: i % 3 === 0 ? `${spec.vendor} ${spec.solution} 관련 메모` : '',
        statusKey: draft.statusKey,
        forecastKey: draft.forecastKey,
      })
      const closing = i === 0 && spec.forecast === 'won'
      if (previous && previous.statusKey !== draft.statusKey) {
        log(deal.code, actedAt, deal.ownerId, 'status', 'Status', names.status(previous.statusKey), names.status(draft.statusKey))
      }
      if (previous && previous.forecastKey !== draft.forecastKey) {
        const note = closing ? ` (${withWa(`Status ${names.status(draft.statusKey)}`)} 함께 변경)` : ''
        log(deal.code, actedAt, deal.ownerId, 'forecast', 'Forecast', names.forecast(previous.forecastKey), `${names.forecast(draft.forecastKey)}${note}`)
      }
      if (closing) {
        const expected = Math.round((deal.revenueAmount * 1.1) / 1_000_000) * 1_000_000
        log(deal.code, actedAt, deal.ownerId, 'amount', AMOUNT_LABEL, formatThousandWon(expected), formatThousandWon(deal.revenueAmount))
        log(deal.code, actedAt, deal.ownerId, 'expectedClose', 'Expected Close', addDays(deal.revenueDate, 20), deal.revenueDate)
      }
      log(deal.code, actedAt, deal.ownerId, 'action', 'Action', '', `등록: ${draft.progress} / Next Action: ${draft.nextAction}`)
      previous = draft
    }

    if (spec.prevPartner && spec.partner) {
      log(deal.code, env.at(30), deal.ownerId, 'partner', '파트너', names.contact(findSeedContact(contacts, spec.prevPartner).id), names.contact(findSeedContact(contacts, spec.partner).id))
    }
  }
  return { actions, history }
}
