import { Fragment } from 'react'
import type { ReportAggregate, ReportCatalog, ReportField, ReportFormat, ReportSortDirection } from '../../../shared/model/reportTypes'
import { columnName } from './names'
import { aggregateChoices, isAggregateLocked } from './state/columnRules'
import type { DesignerColumn } from './state/designerState'
import { describe, type Message } from './state/issueView'

interface ColumnSettingsProps {
  column: DesignerColumn
  field: ReportField
  catalog: ReportCatalog
  /** 설계에 그룹 컬럼이 하나라도 있는지(집계 선택이 켜지는 조건). */
  hasGroup: boolean
  messages: readonly Message[]
  onPatch: (patch: Partial<Omit<DesignerColumn, 'uid' | 'field'>>) => void
}

/** 설정 패널이 자기 줄 아래에 보이는 위반의 part(순서대로). 이 밖의 위반은 칩 쪽에 보인다. */
export const PANEL_PARTS: readonly string[] = ['label', 'format', 'prefix_length', 'group', 'aggregate', 'sort']

const label = (catalog: ReportCatalog, key: ReportAggregate): string => catalog.aggregates.find((a) => a.key === key)?.label ?? key

/** 선택한 컬럼의 표시 이름·포맷·앞 N자·그룹핑·집계·정렬을 조건 행처럼 컬럼 이름 옆 한 줄로 보인다(위반·힌트는 줄 아래). 선택지는 모두 카탈로그에서 온다. */
export function ColumnSettings({ column, field, catalog, hasGroup, messages, onPatch }: ColumnSettingsProps) {
  const choices = aggregateChoices(field)
  const locked = isAggregateLocked(field)
  const aggregateOn = hasGroup && !column.group && !locked
  const formatLabel = (key: ReportFormat) => catalog.formats.find((f) => f.key === key)
  const own = (parts: string[]) => describe(messages, parts)
  const partMessages = (part: string) => messages.filter((m) => m.part === part)
  const shown = (part: string) =>
    partMessages(part).map((m) => (
      <p key={m.id} id={m.id} className="field-error">
        {m.text}
      </p>
    ))

  const name = columnName(column, catalog)

  return (
    <section className="report-settings" aria-label={`컬럼 설정: ${name}`}>
      <div className="report-settings-row">
        <strong className="report-settings-name">{name}</strong>
        <input
          type="text"
          aria-label="표시 이름"
          title="표시 이름"
          maxLength={catalog.limits.labelMax}
          value={column.label}
          placeholder={field.label}
          onChange={(e) => onPatch({ label: e.target.value })}
          {...own(['label'])}
        />
        {field.formats.length > 0 && (
          <select aria-label="포맷" title="포맷" value={column.format ?? ''} onChange={(e) => onPatch({ format: e.target.value as ReportFormat })} {...own(['format'])}>
            {field.formats.map((key) => {
              const info = formatLabel(key)
              return (
                <option key={key} value={key}>
                  {info?.label ?? key}
                  {info?.affectsQuery ? ' (묶음)' : ''}
                </option>
              )
            })}
          </select>
        )}
        <label className="report-check">
          <input type="checkbox" checked={column.prefixOn} onChange={(e) => onPatch({ prefixOn: e.target.checked })} />
          앞 N자만 보기
        </label>
        <input
          type="number"
          aria-label="앞 N자의 N"
          title="앞 N자의 N"
          className="report-settings-n"
          min={1}
          max={catalog.limits.prefixMax}
          disabled={!column.prefixOn}
          value={column.prefixLength ?? ''}
          onChange={(e) => onPatch({ prefixLength: e.target.value === '' ? null : Number(e.target.value) })}
          {...own(['prefix_length'])}
        />
        <label className="report-check">
          <input type="checkbox" checked={column.group} disabled={!field.groupable} onChange={(e) => onPatch({ group: e.target.checked })} {...own(['group'])} />
          그룹핑
        </label>
        <select
          aria-label="집계"
          title="집계"
          value={column.aggregate ?? ''}
          disabled={!aggregateOn}
          onChange={(e) => onPatch({ aggregate: e.target.value === '' ? null : (e.target.value as ReportAggregate) })}
          {...own(['aggregate'])}
        >
          {column.aggregate === null && !aggregateOn && <option value="">—</option>}
          {choices.map((key) => (
            <option key={key} value={key}>
              {label(catalog, key)}
            </option>
          ))}
        </select>
        {!hasGroup && <span className="field-hint">(그룹핑이 있을 때)</span>}
        <select
          aria-label="정렬"
          title="정렬"
          value={column.sort ?? ''}
          onChange={(e) => onPatch({ sort: e.target.value === '' ? null : (e.target.value as ReportSortDirection) })}
          {...own(['sort'])}
        >
          <option value="">정렬 없음</option>
          <option value="asc">오름차순</option>
          <option value="desc">내림차순</option>
        </select>
      </div>
      {column.format === 'percent_share' && <p className="field-hint">구성비는 그룹핑한 결과의 합계·건수에서만 계산됩니다</p>}
      {PANEL_PARTS.map((part) => (
        <Fragment key={part}>{shown(part)}</Fragment>
      ))}
    </section>
  )
}
