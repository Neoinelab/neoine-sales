import { useId } from 'react'
import type { ReportAggregate, ReportCatalog, ReportField, ReportFormat } from '../../../shared/model/reportTypes'
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
  index: number
  count: number
  messages: readonly Message[]
  onPatch: (patch: Partial<Omit<DesignerColumn, 'uid' | 'field'>>) => void
  onMove: (to: number) => void
}

const label = (catalog: ReportCatalog, key: ReportAggregate): string => catalog.aggregates.find((a) => a.key === key)?.label ?? key

/** 선택한 컬럼의 표시 이름·포맷·앞 N자·그룹핑·집계, 앞/뒤 이동. 선택지는 모두 카탈로그에서 온다. */
export function ColumnSettings({ column, field, catalog, hasGroup, index, count, messages, onPatch, onMove }: ColumnSettingsProps) {
  const ids = { label: useId(), format: useId(), prefix: useId(), aggregate: useId() }
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

  return (
    <section className="report-settings" aria-label={`컬럼 설정: ${columnName(column, catalog)}`}>
      <div className="report-settings-grid">
        <div className="field">
          <label htmlFor={ids.label}>표시 이름</label>
          <input
            id={ids.label}
            type="text"
            maxLength={catalog.limits.labelMax}
            value={column.label}
            placeholder={field.label}
            onChange={(e) => onPatch({ label: e.target.value })}
            {...own(['label'])}
          />
          {shown('label')}
        </div>
        {field.formats.length > 0 && (
          <div className="field">
            <label htmlFor={ids.format}>포맷</label>
            <select id={ids.format} value={column.format ?? ''} onChange={(e) => onPatch({ format: e.target.value as ReportFormat })} {...own(['format'])}>
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
            {shown('format')}
            {column.format === 'percent_share' && <p className="field-hint">구성비는 그룹핑한 결과의 합계·건수에서만 계산됩니다</p>}
          </div>
        )}
        <div className="field">
          <label className="report-check">
            <input type="checkbox" checked={column.prefixOn} onChange={(e) => onPatch({ prefixOn: e.target.checked })} />
            앞 N자만 보기
          </label>
          <label htmlFor={ids.prefix}>앞 N자의 N</label>
          <input
            id={ids.prefix}
            type="number"
            min={1}
            max={catalog.limits.prefixMax}
            disabled={!column.prefixOn}
            value={column.prefixLength ?? ''}
            onChange={(e) => onPatch({ prefixLength: e.target.value === '' ? null : Number(e.target.value) })}
            {...own(['prefix_length'])}
          />
          {shown('prefix_length')}
        </div>
        <div className="field">
          <label className="report-check">
            <input type="checkbox" checked={column.group} disabled={!field.groupable} onChange={(e) => onPatch({ group: e.target.checked })} {...own(['group'])} />
            그룹핑
          </label>
          {shown('group')}
        </div>
        <div className="field">
          <label htmlFor={ids.aggregate}>집계</label>
          <select
            id={ids.aggregate}
            value={column.aggregate ?? ''}
            disabled={!aggregateOn}
            onChange={(e) => onPatch({ aggregate: e.target.value === '' ? null : (e.target.value as ReportAggregate) })}
            {...own(['aggregate'])}
          >
            {column.aggregate === null && <option value="">{aggregateOn ? '집계 선택' : '—'}</option>}
            {choices.map((key) => (
              <option key={key} value={key}>
                {label(catalog, key)}
              </option>
            ))}
          </select>
          {!hasGroup && <span className="field-hint">(그룹핑이 있을 때)</span>}
          {shown('aggregate')}
        </div>
      </div>
      <div className="report-settings-move">
        <button type="button" disabled={index === 0} onClick={() => onMove(index - 1)}>
          앞으로
        </button>
        <button type="button" disabled={index === count - 1} onClick={() => onMove(index + 1)}>
          뒤로
        </button>
      </div>
    </section>
  )
}
