/** Deal의 Won 진입·이탈에 따른 라이선스 계약 처리(서버 `follow_won_change`와 같다). 등록·수정·단일 변경·Action 등록이 모두 부른다. */

import { conflict } from '../errors'
import { FORECAST_WON } from '../../../shared/model/constants'
import type { SyncState } from '../../../shared/model/sync'
import { takeId, type SeedData } from '../store'
import type { MockContext } from './context'

/** 서버 `WON_EXIT_BLOCKED`, `DEAL_NOT_WON`과 같은 문구. */
export const WON_EXIT_BLOCKED =
  '발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없습니다. 계약 정보가 잘못되었다면 관리자에게 계약 삭제를 요청하세요.'
export const DEAL_NOT_WON = 'Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다.'

const ISSUED = ['issued_new', 'issued_renewal']

export function hasIssuedContract(data: SeedData, dealCode: string): boolean {
  return data.licenseContracts.some((c) => c.dealCode === dealCode && ISSUED.includes(c.status))
}

/** 발급 계약이 있는 Deal이 Won에서 벗어나면 409. 아무것도 바꾸기 전에 부른다. */
export function assertWonExitAllowed(data: SeedData, dealCode: string, before: SyncState, after: SyncState): void {
  if (before.forecastKey === FORECAST_WON && after.forecastKey !== FORECAST_WON && hasIssuedContract(data, dealCode)) {
    throw conflict(WON_EXIT_BLOCKED)
  }
}

export function contractCountOf(data: SeedData, dealCode: string): number {
  return data.licenseContracts.filter((c) => c.dealCode === dealCode).length
}

/** Deal에 속한 계약과 그 첨부를 모두 지운다(Deal 삭제, Won 이탈 때 삭제 선택). */
export function removeContractsOfDeal(data: SeedData, dealCode: string): void {
  const ids = new Set(data.licenseContracts.filter((c) => c.dealCode === dealCode).map((c) => c.id))
  data.licenseContracts = data.licenseContracts.filter((c) => !ids.has(c.id))
  data.contractAttachments = data.contractAttachments.filter((a) => !ids.has(a.contractId))
}

/**
 * before가 null이면 신규 등록이다. Won이 아니던 Deal이 Won이 되고 계약이 하나도 없으면 미발급 계약을 만든다(종료 계약만 있어도 만들지 않는다).
 * Won이던 Deal이 Won이 아니게 되면서 deleteContracts가 true일 때만 그 Deal의 계약을 지운다. 그 밖에는 아무것도 하지 않는다.
 */
export function followWonChange(
  ctx: MockContext,
  dealCode: string,
  before: SyncState | null,
  after: SyncState,
  deleteContracts: boolean | undefined,
  byId: number,
): void {
  const { data } = ctx.store
  const wasWon = before !== null && before.forecastKey === FORECAST_WON
  const isWon = after.forecastKey === FORECAST_WON
  if (!wasWon && isWon && contractCountOf(data, dealCode) === 0) {
    const now = ctx.clock.now()
    data.licenseContracts.push({
      id: takeId(data.counters, 'lc'),
      dealCode,
      status: 'not_issued',
      licenseStart: null,
      licenseEnd: null,
      term: null,
      techOwner: '',
      inspection: 'none',
      note: '',
      renewedFromId: null,
      endedAt: null,
      createdById: byId,
      updatedById: byId,
      createdAt: now,
      updatedAt: now,
    })
  } else if (wasWon && !isWon && deleteContracts === true) {
    removeContractsOfDeal(data, dealCode)
  }
}
