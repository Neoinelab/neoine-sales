/**
 * Status⇄Forecast 동기화 순수 규칙(A-0 계약, 구현은 A-1). 계획 7장 / PRD 6.7.
 * UI(useSyncedChange)와 게이트웨이(deals.applyChange, actions.create)가 같은 함수를 쓴다.
 *
 * 전역 불변식: Status `contract_completed` ⇔ Forecast `won`. (key 기준, 이름이 바뀌어도 동일)
 *
 * 규칙표 (current = 변경 전 값):
 * | 변경 요청                | 현재                        | 결과 kind                                                     |
 * | Status → 계약완료        | Status가 계약완료가 아님     | needRevenue, patch {status: 계약완료, forecast: won}          |
 * | Forecast → Won           | Forecast가 Won이 아님        | needRevenue, patch {forecast: won, status: 계약완료}          |
 * | Forecast → Lost          | Forecast가 Won이 아님        | independent, patch {forecast: lost} (Status 유지)             |
 * | Forecast → Won 아닌 값   | Forecast가 Won               | askStatus: 계약완료 제외 Status 중 선택 필수(기본 null)        |
 * | Forecast → Won 아닌 값   | Forecast가 Lost              | askStatus: 계약완료 제외 Status 중 선택, defaultKey=현재 Status |
 * | Status → 이전 단계       | Status가 계약완료            | askForecast: Won 제외 Forecast 중 선택 필수                    |
 * | 그 외(값이 같은 변경 포함)| —                           | independent (같은 값이면 patch는 빈 객체)                      |
 * 되돌릴 때 매출금액·매출일 등 나머지 값은 그대로 둔다. Won 이후에도 잠금은 없다.
 * 판정 순서: ① 값이 현재와 같으면 independent{} ② 위 표의 위에서부터 첫 일치.
 * Forecast 현재 Lost → Won은 표의 2번째 줄(needRevenue)이다.
 */

import { FORECAST_LOST, FORECAST_WON, STATUS_CONTRACT_COMPLETED } from './constants'
import { withGa, withRo } from './text'
import type { CodeSet } from './types'
import { isValidAmount } from './money'

export interface SyncState {
  statusKey: string
  forecastKey: string
}

/** Status 또는 Forecast의 변경 요청(둘 다 key). */
export type SyncChange =
  | { field: 'statusKey'; value: string }
  | { field: 'forecastKey'; value: string }

/** 확정된 값만 담는 부분 갱신. */
export interface SyncPatch {
  statusKey?: string
  forecastKey?: string
}

export type SyncPlan =
  /** 그 외 독립 변경: patch를 그대로 적용. */
  | { kind: 'independent'; patch: SyncPatch }
  /** R09: Won/계약완료 전환. 두 값이 함께 바뀌고 실제 매출금액·매출일 입력이 필수. notice는 안내 문구. */
  | {
      kind: 'needRevenue'
      patch: SyncPatch
      notice: string
      /**
       * (A-1 추가, 선택) 사용자가 직접 요청한 필드. `planChange`는 항상 채운다. 있으면 나머지 한 필드만 coChanged가 되고,
       * 없으면(직접 만든 plan) 값이 바뀌는 두 필드가 모두 coChanged다.
       */
      requested?: 'statusKey' | 'forecastKey'
    }
  /**
   * R10: 종결 Deal의 Forecast 변경. Forecast는 patch.forecastKey로 확정이고 Status를 options에서 골라야 한다.
   * defaultKey가 null이면 기본 선택이 없다(확인 버튼 비활성). prompt는 ChoiceDialog 본문.
   */
  | {
      kind: 'askStatus'
      options: string[]
      defaultKey: string | null
      patch: { forecastKey: string }
      prompt: string
    }
  /** R10: 계약완료에서 이전 단계로. Status는 patch.statusKey로 확정이고 Forecast를 options(Won 제외)에서 골라야 한다. */
  | { kind: 'askForecast'; options: string[]; patch: { statusKey: string }; prompt: string }

/** 사용자가 대화상자에서 고른/입력한 값. 해당 kind가 아니면 무시된다. */
export interface SyncResolution {
  /** needRevenue: 실제 매출금액(1 이상 정수). */
  revenueAmount?: number
  /** needRevenue: 실제 매출일('YYYY-MM-DD'). */
  revenueDate?: string
  /** askStatus: 선택한 Status key. */
  statusKey?: string
  /** askForecast: 선택한 Forecast key. */
  forecastKey?: string
}

/** 함께 바뀐 값(알림·History 표시용). 사용자가 직접 요청한 필드는 포함하지 않는다. */
export interface CoChange {
  field: 'statusKey' | 'forecastKey'
  from: string
  to: string
}

/** 확정 결과. UI는 이 값을 즉시 저장(목록/상세) 또는 draft에 반영(폼)한다. */
export interface SyncApplied {
  /** 최종 Status/Forecast 변경분(요청 + 함께 바뀐 값). */
  patch: SyncPatch
  /** needRevenue였을 때의 실제 값, 아니면 null. */
  revenue: { amount: number; date: string } | null
  coChanged: CoChange[]
  /**
   * 적용 후 알림 문구. 함께 바뀐 값이 없으면 null.
   * 예) "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다." (코드 이름 사용)
   */
  notice: string | null
}

export type SyncFinalize =
  | { ok: true; applied: SyncApplied }
  | {
      ok: false
      /** 422 문구: 'revenue'="Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.",
       *  'choice'="함께 바꿀 값을 선택하세요." */
      reason: 'revenue' | 'choice'
      message: string
    }

/** 변경 요청을 평가해 어떤 후속 입력이 필요한지 계획한다. 부수효과 없음. */
export function planChange(current: SyncState, change: SyncChange, codes: CodeSet): SyncPlan {
  const currentValue = change.field === 'statusKey' ? current.statusKey : current.forecastKey
  if (currentValue === change.value) return { kind: 'independent', patch: {} }

  if (change.field === 'statusKey') {
    if (change.value === STATUS_CONTRACT_COMPLETED) {
      return {
        kind: 'needRevenue',
        patch: { statusKey: STATUS_CONTRACT_COMPLETED, forecastKey: FORECAST_WON },
        notice: revenueNotice(codes),
        requested: 'statusKey',
      }
    }
    if (current.statusKey === STATUS_CONTRACT_COMPLETED) {
      const options = codes.forecasts.filter((c) => c.key !== FORECAST_WON).map((c) => c.key)
      return {
        kind: 'askForecast',
        options,
        patch: { statusKey: change.value },
        prompt: `Status를 '${statusName(codes, change.value)}'${josa(statusName(codes, change.value))} 바꾸면 ${withGa(statusName(codes, current.statusKey))} 해제됩니다. Forecast를 어떤 값으로 바꿀까요?`,
      }
    }
    return { kind: 'independent', patch: { statusKey: change.value } }
  }

  if (change.value === FORECAST_WON) {
    return {
      kind: 'needRevenue',
      patch: { statusKey: STATUS_CONTRACT_COMPLETED, forecastKey: FORECAST_WON },
      notice: revenueNotice(codes),
      requested: 'forecastKey',
    }
  }
  if (current.forecastKey === FORECAST_WON || current.forecastKey === FORECAST_LOST) {
    const options = codes.statuses.filter((c) => c.key !== STATUS_CONTRACT_COMPLETED).map((c) => c.key)
    const wasWon = current.forecastKey === FORECAST_WON
    const target = forecastName(codes, change.value)
    return {
      kind: 'askStatus',
      options,
      defaultKey: wasWon || !options.includes(current.statusKey) ? null : current.statusKey,
      patch: { forecastKey: change.value },
      prompt: wasWon
        ? `Forecast를 '${target}'(으)로 바꾸면 ${forecastName(codes, FORECAST_WON)} 상태가 해제되어 Status를 ${withRo(statusName(codes, STATUS_CONTRACT_COMPLETED))} 둘 수 없습니다. 어떤 Status로 바꿀까요?`
        : `Forecast를 '${target}'(으)로 바꾸면 ${forecastName(codes, FORECAST_LOST)} 상태가 해제됩니다. Status를 어떤 값으로 둘까요?`,
    }
  }
  return { kind: 'independent', patch: { forecastKey: change.value } }
}

function statusName(codes: CodeSet, key: string): string {
  return codes.statuses.find((c) => c.key === key)?.name ?? key
}

function forecastName(codes: CodeSet, key: string): string {
  return codes.forecasts.find((c) => c.key === key)?.name ?? key
}

function revenueNotice(codes: CodeSet): string {
  const s = statusName(codes, STATUS_CONTRACT_COMPLETED)
  const f = forecastName(codes, FORECAST_WON)
  return `Status가 '${s}'${josa(s)}, Forecast가 '${f}'${josa(f)} 함께 변경됩니다. 실제 매출금액과 매출일을 입력해야 저장할 수 있습니다.`
}

function josa(name: string): string {
  return withRo(name).slice(name.length)
}

/**
 * 계획 + 사용자 답을 검증해 최종 변경분을 만든다.
 * - needRevenue: revenueAmount가 1 이상 정수이고 revenueDate가 비어 있지 않아야 한다. 아니면 reason 'revenue'.
 * - askStatus/askForecast: 선택 값이 options에 있어야 한다. 아니면 reason 'choice'.
 * - independent: resolution 무시.
 */
export function finalizePlan(
  current: SyncState,
  plan: SyncPlan,
  resolution: SyncResolution | undefined,
  codes: CodeSet,
): SyncFinalize {
  let patch: SyncPatch = plan.patch
  let revenue: SyncApplied['revenue'] = null

  if (plan.kind === 'needRevenue') {
    const amount = resolution?.revenueAmount
    const date = resolution?.revenueDate?.trim()
    if (!isValidAmount(amount) || !date) {
      return { ok: false, reason: 'revenue', message: REVENUE_REQUIRED_MESSAGE }
    }
    revenue = { amount, date }
  } else if (plan.kind === 'askStatus') {
    const statusKey = resolution?.statusKey
    if (statusKey === undefined || !plan.options.includes(statusKey)) {
      return { ok: false, reason: 'choice', message: CHOICE_REQUIRED_MESSAGE }
    }
    patch = { ...plan.patch, statusKey }
  } else if (plan.kind === 'askForecast') {
    const forecastKey = resolution?.forecastKey
    if (forecastKey === undefined || !plan.options.includes(forecastKey)) {
      return { ok: false, reason: 'choice', message: CHOICE_REQUIRED_MESSAGE }
    }
    patch = { ...plan.patch, forecastKey }
  }

  const coChanged = coChangesOf(current, patch, plan)
  return { ok: true, applied: { patch, revenue, coChanged, notice: noticeOf(coChanged, patch, plan, codes) } }
}

export const REVENUE_REQUIRED_MESSAGE = 'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.'
export const CHOICE_REQUIRED_MESSAGE = '함께 바꿀 값을 선택하세요.'

/** 사용자가 직접 요청한 필드(plan.requested)를 뺀, 값이 실제로 바뀌는 필드. */
function coChangesOf(current: SyncState, patch: SyncPatch, plan: SyncPlan): CoChange[] {
  const requested = requestedField(plan)
  const out: CoChange[] = []
  if (patch.statusKey !== undefined && patch.statusKey !== current.statusKey && requested !== 'statusKey') {
    out.push({ field: 'statusKey', from: current.statusKey, to: patch.statusKey })
  }
  if (patch.forecastKey !== undefined && patch.forecastKey !== current.forecastKey && requested !== 'forecastKey') {
    out.push({ field: 'forecastKey', from: current.forecastKey, to: patch.forecastKey })
  }
  return out
}

/** 계획의 patch만으로는 요청 필드를 알 수 없는 kind를 위해, 계획 단계의 요청 필드를 판별한다. */
function requestedField(plan: SyncPlan): 'statusKey' | 'forecastKey' | null {
  if (plan.kind === 'askStatus') return 'forecastKey'
  if (plan.kind === 'askForecast') return 'statusKey'
  if (plan.kind === 'needRevenue') return plan.requested ?? null
  // independent의 patch는 요청한 한 필드뿐이다.
  return plan.patch.statusKey !== undefined ? 'statusKey' : 'forecastKey'
}

/**
 * 알림 문구. 함께 바뀐 값이 없으면 null. needRevenue는 쌍으로 바뀌므로 Status·Forecast를 모두 말하고,
 * 그 외에는 함께 바뀐 필드만 말한다.
 */
function noticeOf(coChanged: CoChange[], patch: SyncPatch, plan: SyncPlan, codes: CodeSet): string | null {
  if (coChanged.length === 0) return null
  const parts: string[] = []
  const wantStatus = plan.kind === 'needRevenue' ? patch.statusKey : coChanged.find((c) => c.field === 'statusKey')?.to
  const wantForecast = plan.kind === 'needRevenue' ? patch.forecastKey : coChanged.find((c) => c.field === 'forecastKey')?.to
  if (wantStatus !== undefined) {
    const name = statusName(codes, wantStatus)
    parts.push(`Status가 '${name}'${josa(name)}`)
  }
  if (wantForecast !== undefined) {
    const name = forecastName(codes, wantForecast)
    parts.push(`Forecast가 '${name}'${josa(name)}`)
  }
  return `${parts.join(', ')} 함께 변경되었습니다.`
}

/** 불변식(계약완료 ⇔ Won) 검사. Deal 등록/수정 입력 검증과 시드 검증에 쓴다. */
export function isSyncConsistent(state: SyncState): boolean {
  return (state.statusKey === STATUS_CONTRACT_COMPLETED) === (state.forecastKey === FORECAST_WON)
}

/** 한 번에 보내는 두 변경이 서로 맞지 않을 때의 문구(서버 `SYNC_CONFLICT_MESSAGE`와 같다). */
export const SYNC_CONFLICT_MESSAGE = '먼저 바꾼 값과 맞지 않는 변경입니다. 먼저 바꾼 값을 되돌린 뒤 다시 선택하세요.'

/**
 * 두 번째 변경(applied)이 첫 변경이 직접 요청한 필드의 값을 바꾸는가. before는 첫 변경 적용 후 상태(S1).
 * 서버 `finalize_sequence`의 충돌 판정과 같다.
 */
export function overridesRequested(first: SyncChange, before: SyncState, applied: SyncApplied): boolean {
  const kept = before[first.field]
  return (applied.patch[first.field] ?? kept) !== kept
}

/**
 * 대화상자를 열기 전에 알 수 있는 확정적 충돌. state는 첫 변경 적용 후 상태(S1), plan은 그 상태에서의 두 번째 변경 계획.
 * 사용자의 선택에 따라 달라질 수 있으면(선택지에 첫 값이 있으면) false다.
 */
export function certainlyOverrides(first: SyncChange, state: SyncState, plan: SyncPlan): boolean {
  const current = state[first.field]
  const fixed = (plan.patch as SyncPatch)[first.field]
  if (fixed !== undefined) return fixed !== current
  if (plan.kind === 'askStatus' && first.field === 'statusKey') return !plan.options.includes(current)
  if (plan.kind === 'askForecast' && first.field === 'forecastKey') return !plan.options.includes(current)
  return false
}
