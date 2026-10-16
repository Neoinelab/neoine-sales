/** Deal 쓰기: 등록·수정·단일 필드 변경·삭제. 검증과 연락처 계획을 모두 끝낸 뒤에만 저장소를 바꾼다. */

import { compactDate } from '../../shared/model/dates'
import { canDeleteDeal } from '../../shared/model/permissions'
import type { Deal, DealInput, DealPatch } from '../../shared/model/types'
import { forbidden, validation } from '../errors'
import { requireUser, requireWrite, viewerOf, write, clone, type MockContext } from './context'
import { commitContact, planContact, type ContactPlan } from './contactPlan'
import { commitDealChange, planDealChange } from './dealChange'
import { providedKeys, validateCustomerDraft, validateDealFields, validatePartnerDraft } from './dealValidation'
import { logDealDiff, logHistory } from './historyLog'
import { dealDetail, findDeal } from './views'

const CODE_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

/** `YYYYMMDD-XXXX`. 기존 code와 겹치면 다시 뽑는다. */
export function newDealCode(ctx: MockContext): string {
  const prefix = compactDate(ctx.clock.today())
  const used = new Set(ctx.store.data.deals.map((d) => d.code))
  for (;;) {
    let suffix = ''
    for (let i = 0; i < 4; i += 1) suffix += CODE_CHARS[Math.floor(ctx.random() * CODE_CHARS.length)] ?? 'A'
    const code = `${prefix}-${suffix}`
    if (!used.has(code)) return code
  }
}

function createDeal(ctx: MockContext, input: DealInput) {
  const user = requireWrite(ctx)
  validateDealFields(ctx, input, () => true)
  validateCustomerDraft(input.customer)
  if (input.partner) validatePartnerDraft(input.partner)
  const customerPlan = planContact(ctx, 'customer', input.customer)
  const partnerPlan = input.partner ? planContact(ctx, 'partner', input.partner) : null

  const customerId = commitContact(ctx, customerPlan, user.id)
  const partnerId = partnerPlan ? commitContact(ctx, partnerPlan, user.id) : null
  const now = ctx.clock.now()
  const deal: Deal = {
    code: newDealCode(ctx),
    name: input.name.trim(),
    ownerId: input.ownerId,
    vendor: input.vendor.trim(),
    solution: input.solution.trim(),
    users: input.users,
    statusKey: input.statusKey,
    forecastKey: input.forecastKey,
    revenueAmount: input.revenueAmount,
    revenueDate: input.revenueDate,
    customerContactId: customerId,
    partnerLinks: partnerId ? [{ contactId: partnerId, active: true, linkedAt: now, unlinkedAt: null }] : [],
    quote: clone(input.quote),
    poc: clone(input.poc),
    procurement: input.procurement.trim(),
    bant: clone(input.bant),
    createdAt: now,
    updatedAt: now,
  }
  ctx.store.data.deals.push(deal)
  logHistory(ctx, deal.code, user.id, 'created', 'Deal 등록', '', 'Deal 등록')
  return dealDetail(ctx, deal)
}

const SCALAR_KEYS = [
  'name', 'ownerId', 'vendor', 'solution', 'users', 'statusKey', 'forecastKey',
  'revenueAmount', 'revenueDate', 'quote', 'poc', 'procurement', 'bant',
] as const satisfies readonly (keyof DealPatch)[]

function updateDeal(ctx: MockContext, code: string, patch: DealPatch) {
  const user = requireWrite(ctx)
  const deal = findDeal(ctx.store.data, code)
  const provided = providedKeys(patch)
  const after: Deal = { ...clone(deal) }
  for (const key of SCALAR_KEYS) {
    if (patch[key] !== undefined) Object.assign(after, { [key]: clone(patch[key]) })
  }
  if (typeof patch.name === 'string') after.name = patch.name.trim()
  if (typeof patch.vendor === 'string') after.vendor = patch.vendor.trim()
  if (typeof patch.solution === 'string') after.solution = patch.solution.trim()
  if (typeof patch.procurement === 'string') after.procurement = patch.procurement.trim()
  validateDealFields(ctx, after, provided)

  let customerPlan: ContactPlan | null = null
  let partnerPlan: ContactPlan | null = null
  if (patch.customer) {
    validateCustomerDraft(patch.customer)
    customerPlan = planContact(ctx, 'customer', patch.customer)
  }
  if (patch.partner) {
    validatePartnerDraft(patch.partner)
    partnerPlan = planContact(ctx, 'partner', patch.partner)
  }

  const before = clone(deal)
  const now = ctx.clock.now()
  if (customerPlan) after.customerContactId = commitContact(ctx, customerPlan, user.id)
  if (patch.partner === null || partnerPlan) {
    const partnerId = partnerPlan ? commitContact(ctx, partnerPlan, user.id) : null
    const active = after.partnerLinks.find((l) => l.active)
    if (active?.contactId !== partnerId) {
      if (active) Object.assign(active, { active: false, unlinkedAt: now })
      if (partnerId) after.partnerLinks.push({ contactId: partnerId, active: true, linkedAt: now, unlinkedAt: null })
    }
  }
  // 연락처 갱신이 이 Deal의 updatedAt을 이미 올렸을 수 있으므로 저장소 값을 이어받는다.
  after.updatedAt = deal.updatedAt
  Object.assign(deal, after)
  if (logDealDiff(ctx, before, deal, user.id) > 0) deal.updatedAt = now
  return dealDetail(ctx, deal)
}

export function dealsWriteApi(ctx: MockContext) {
  return {
    create: (input: DealInput) => write(ctx, () => createDeal(ctx, input)),
    update: (code: string, patch: DealPatch) => write(ctx, () => updateDeal(ctx, code, patch)),
    applyChange: (code: string, request: Parameters<typeof planDealChange>[2]) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const deal = findDeal(ctx.store.data, code)
        const outcome = planDealChange(ctx, deal, request)
        commitDealChange(ctx, deal, outcome, user.id)
        return { deal: dealDetail(ctx, deal), coChanged: outcome.coChanged, notice: outcome.notice }
      }),
    remove: (code: string, confirmCode: string) =>
      write(ctx, () => {
        const user = requireUser(ctx)
        const { data } = ctx.store
        const deal = findDeal(data, code)
        if (!canDeleteDeal(viewerOf(user), deal.ownerId)) throw forbidden('본인 Deal 또는 admin만 삭제할 수 있습니다.')
        if (confirmCode !== code) throw validation('Deal code가 일치하지 않습니다.')
        data.deals.splice(data.deals.indexOf(deal), 1)
        data.history = data.history.filter((h) => h.dealCode !== code)
        data.actions = data.actions.filter((a) => a.dealCode !== code)
        data.attachments = data.attachments.filter((a) => a.dealCode !== code)
      }),
  }
}
