import { useState } from 'react'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import type { ReportCatalog, ReportField, ReportFieldType } from '../../../shared/model/reportTypes'

const KIND_LABEL: Record<ReportFieldType, string> = {
  text: '텍스트',
  code: '코드',
  user: '사용자',
  number: '숫자',
  date: '날짜',
  datetime: '시각',
}

interface FieldPanelProps {
  catalog: ReportCatalog
  /** 컬럼에 이미 들어 있는 필드 key(흐리게 보인다. 같은 필드를 또 넣을 수는 있으나 확인 대화상자에서 "추가"를 눌러야 한다). */
  usedFields: ReadonlySet<string>
  columnsFull: boolean
  conditionsFull: boolean
  onAddColumn: (field: ReportField) => void
  onAddCondition: (field: ReportField) => void
}

/** 왼쪽 필드 목록: 표시 이름 검색, Deal / Deal Actions 두 묶음, 컬럼·조건 추가 버튼. */
export function FieldPanel({ catalog, usedFields, columnsFull, conditionsFull, onAddColumn, onAddCondition }: FieldPanelProps) {
  const [search, setSearch] = useState('')
  const [duplicate, setDuplicate] = useState<ReportField | null>(null)
  const requestAdd = (field: ReportField) => {
    if (usedFields.has(field.key)) setDuplicate(field)
    else onAddColumn(field)
  }
  const needle = search.trim().toLowerCase()
  const matches = (field: ReportField) => needle === '' || field.label.toLowerCase().includes(needle)
  const groups = catalog.entities
    .map((entity) => ({ entity, fields: catalog.fields.filter((f) => f.entity === entity.key && matches(f)) }))
    .filter((g) => g.fields.length > 0)

  // 확인 대화상자는 aside 밖(형제)에 둔다: sticky aside가 쌓임 범위를 만들어 그 안의 Modal 배경이 상단 바 등을 덮지 못한다
  return (
    <>
      <aside className="report-fields" aria-label="필드 목록">
        <input type="search" aria-label="필드 검색" placeholder="필드 검색" value={search} onChange={(e) => setSearch(e.target.value)} />
        {groups.length === 0 && <p className="hint">일치하는 필드가 없습니다.</p>}
        {groups.map(({ entity, fields }) => (
          <div key={entity.key} role="group" aria-label={entity.label} className={`report-field-group group-${entity.key}`}>
            <h2>{entity.label}</h2>
            <ul>
              {fields.map((field) => (
                <li key={field.key} className={usedFields.has(field.key) ? 'is-used' : undefined}>
                  <button type="button" className="report-field-add" aria-label={`${field.label} 컬럼에 추가`} disabled={columnsFull} onClick={() => requestAdd(field)}>
                    {field.label}
                  </button>
                  <span className="report-kind">{KIND_LABEL[field.type]}</span>
                  {field.filterable && (
                    <button type="button" className="report-field-condition" aria-label={`${field.label} 조건 추가`} disabled={conditionsFull} onClick={() => onAddCondition(field)}>
                      +조건
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </aside>
      {duplicate && (
        <ConfirmDialog
          title="같은 필드 추가"
          message={`'${duplicate.label}'은(는) 이미 컬럼에 있습니다. 한 번 더 추가할까요?`}
          confirmLabel="추가"
          onConfirm={() => {
            onAddColumn(duplicate)
            setDuplicate(null)
          }}
          onCancel={() => setDuplicate(null)}
        />
      )}
    </>
  )
}
