import { useId } from 'react'
import type { ReportChartKind } from '../../../shared/model/reportTypes'
import { CHART_FAMILIES, CHART_KINDS, kindRule, type ChartKindRule } from './chartKinds'

interface KindPickerProps {
  kind: ReportChartKind
  /** 지금 설계의 그룹핑 컬럼 수. */
  groupCount: number
  onChange: (kind: ReportChartKind) => void
}

/** 지금 그룹핑 수로 쓸 수 없는 이유(쓸 수 있으면 undefined). */
function reasonOf(rule: ChartKindRule, groupCount: number): string | undefined {
  if (groupCount < rule.minGroups) return '그룹핑한 결과로 만들 수 있습니다'
  if (groupCount > rule.maxGroups) return `그룹핑 컬럼이 ${rule.maxGroups}개 이하일 때 쓸 수 있습니다`
  return undefined
}

/** Excel "차트 삽입"처럼 2단 선택: 분류(라디오) → 하위 종류(버튼). 분류를 바꾸면 그 분류의 첫 번째로 쓸 수 있는 종류가 된다. */
export function KindPicker({ kind, groupCount, onChange }: KindPickerProps) {
  const name = useId()
  const family = kindRule(kind).family
  const inFamily = (key: string): ChartKindRule[] => CHART_KINDS.filter((k) => k.family === key)
  return (
    <div className="report-kind-picker">
      <div className="report-families" role="radiogroup" aria-label="차트 분류">
        {CHART_FAMILIES.map((f) => {
          const members = inFamily(f.key)
          const usable = members.find((m) => reasonOf(m, groupCount) === undefined)
          const reason = usable ? undefined : reasonOf(members[0]!, groupCount)
          return (
            <label key={f.key} className="report-check">
              <input type="radio" name={name} checked={f.key === family} disabled={!usable} title={reason} onChange={() => usable && onChange(usable.key)} />
              {f.label}
            </label>
          )
        })}
      </div>
      <div className="report-kinds" role="group" aria-label="하위 종류">
        {inFamily(family).map((k) => {
          const reason = reasonOf(k, groupCount)
          return (
            <button key={k.key} type="button" aria-pressed={kind === k.key} disabled={reason !== undefined} title={reason} onClick={() => onChange(k.key)}>
              {k.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
