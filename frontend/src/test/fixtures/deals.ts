import { BANT_CATEGORIES } from '../../shared/model/constants'
import type { BantSelection, Code, Contact, Deal, PartnerLink, Poc, Quote } from '../../shared/model/types'
import type { LabelRecord } from '../../mock/store'
import { findSeedContact } from './contacts'
import { actionHour, createdAgo, type DealSpec } from './dealSpecs'
import type { SeedEnv } from '../../mock/seed/env'

/** 시드 Deal의 code: 등록일(YYYYMMDD) + '-D' + 3자리 번호(1~24). */
export function dealCodeOf(spec: Pick<DealSpec, 'no' | 'lastAgo' | 'count'>, env: Pick<SeedEnv, 'date'>): string {
  return `${env.date(-createdAgo(spec)).replaceAll('-', '')}-D${String(spec.no).padStart(3, '0')}`
}

function bantOf(spec: DealSpec, labels: readonly LabelRecord[]): BantSelection {
  const selection: BantSelection = { budget: null, authority: null, need: null, timeline: null }
  BANT_CATEGORIES.forEach((category, index) => {
    const name = spec.bant?.[index]
    if (name) selection[category] = labels.find((l) => l.category === category && l.name === name)?.id ?? null
  })
  return selection
}

function quoteOf(spec: DealSpec, statusIndex: number, env: SeedEnv): Quote {
  const submitted = spec.quote ?? (statusIndex >= 4 ? 'YES' : null)
  return { submitted, submittedDate: submitted === 'YES' ? env.date(-(10 + spec.no)) : null }
}

function pocOf(spec: DealSpec, statusIndex: number, env: SeedEnv): Poc {
  const state = spec.poc ?? (statusIndex >= 3 ? 'YES' : statusIndex === 2 ? 'ING' : null)
  return { state, completedDate: state === 'YES' ? env.date(-(20 + spec.no)) : null }
}

function partnerLinks(spec: DealSpec, contacts: readonly Contact[], env: SeedEnv, createdAt: string): PartnerLink[] {
  const links: PartnerLink[] = []
  if (spec.prevPartner) {
    links.push({ contactId: findSeedContact(contacts, spec.prevPartner).id, active: false, linkedAt: env.at(60), unlinkedAt: env.at(30) })
  }
  if (spec.partner) {
    links.push({
      contactId: findSeedContact(contacts, spec.partner).id,
      active: true,
      linkedAt: spec.prevPartner ? env.at(30) : createdAt,
      unlinkedAt: null,
    })
  }
  return links
}

export function seedDeals(
  env: SeedEnv,
  specs: readonly DealSpec[],
  contacts: readonly Contact[],
  labels: readonly LabelRecord[],
  codes: readonly Code[],
): Deal[] {
  const statusKeys = codes.filter((c) => c.kind === 'status').map((c) => c.key)
  return specs.map((spec) => {
    const createdAt = env.at(createdAgo(spec), 9)
    const statusIndex = statusKeys.indexOf(spec.status)
    return {
      code: dealCodeOf(spec, env),
      name: spec.name,
      ownerId: `u-${spec.owner}`,
      vendor: spec.vendor,
      solution: spec.solution,
      users: spec.users ?? null,
      statusKey: spec.status,
      forecastKey: spec.forecast,
      revenueAmount: spec.amountM * 1_000_000,
      revenueDate: env.date(spec.close),
      customerContactId: findSeedContact(contacts, spec.customer).id,
      partnerLinks: partnerLinks(spec, contacts, env, createdAt),
      quote: quoteOf(spec, statusIndex, env),
      poc: pocOf(spec, statusIndex, env),
      procurement: spec.procurement ?? '',
      bant: bantOf(spec, labels),
      createdAt,
      updatedAt: env.at(spec.lastAgo, actionHour(spec.no, 0)),
    }
  })
}
