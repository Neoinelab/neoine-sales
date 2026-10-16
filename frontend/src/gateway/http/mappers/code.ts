import type { Schemas } from '../../../shared/api/client'
import type { Code, CodeSet, CodeWithUsage, ForecastOutcome } from '../../../shared/model/types'
import { malformedResponse } from '../request'

const OUTCOMES: readonly ForecastOutcome[] = ['open', 'won', 'lost']

function toOutcome(value: string): ForecastOutcome {
  const found = OUTCOMES.find((outcome) => outcome === value)
  if (!found) throw malformedResponse()
  return found
}

export function toCode(row: Schemas['CodeResponse']): Code {
  return {
    id: row.id,
    kind: row.kind,
    key: row.key,
    name: row.name,
    order: row.order,
    locked: row.locked,
    outcome: toOutcome(row.outcome),
    probabilityHint: row.probability_hint,
  }
}

export function toCodeWithUsage(row: Schemas['CodeUsageResponse']): CodeWithUsage {
  return { ...toCode(row), usageCount: row.usage_count }
}

export function toCodeSet(set: Schemas['CodeSetResponse']): CodeSet {
  return { statuses: set.statuses.map(toCode), forecasts: set.forecasts.map(toCode) }
}
