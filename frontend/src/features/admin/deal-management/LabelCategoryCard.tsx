import { useId, useState } from 'react'
import { formatDateTime } from '../../../shared/format'
import { BANT_CATEGORY_NAMES, type BantCategory } from '../../../shared/model/constants'
import { userLabel } from '../../../shared/model/period'
import type { BantLabelWithUsage } from '../../../shared/model/types'
import { TextField } from '../../../shared/ui/fields'
import { InlineNameEdit } from './InlineNameEdit'

interface Props {
  category: BantCategory
  labels: readonly BantLabelWithUsage[]
  editingId: number | null
  busy: boolean
  onAdd: (name: string, done: () => void) => void
  onEdit: (id: number | null) => void
  onRename: (label: BantLabelWithUsage, name: string) => void
  onDelete: (label: BantLabelWithUsage) => void
}

/** BANT 구분 하나(Budget 등)의 Label 목록과 추가 입력. 기본 Label은 배지로 구분하고 사용 Deal 수·만든 사람을 보여준다. */
export function LabelCategoryCard({ category, labels, editingId, busy, onAdd, onEdit, onRename, onDelete }: Props) {
  const titleId = useId()
  const [name, setName] = useState('')
  return (
    <section className="admin-card" aria-labelledby={titleId}>
      <header>
        <h3 id={titleId}>{BANT_CATEGORY_NAMES[category]}</h3>
      </header>
      <div className="table-wrap">
        <table aria-label={`${BANT_CATEGORY_NAMES[category]} Label 목록`}>
          <thead>
            <tr>
              <th>이름</th>
              <th>사용</th>
              <th>만든 사용자·시각</th>
              <th>작업</th>
            </tr>
          </thead>
          <tbody>
            {labels.map((label) => (
              <tr key={label.id}>
                <td>
                  {editingId === label.id ? (
                    <InlineNameEdit
                      label="Label 이름"
                      initial={label.name}
                      busy={busy}
                      onSave={(next) => onRename(label, next)}
                      onCancel={() => onEdit(null)}
                    />
                  ) : (
                    <>
                      {label.name} {label.isDefault && <span className="badge">기본</span>}
                    </>
                  )}
                </td>
                <td className="stat">{`Deal ${label.usageCount}건`}</td>
                <td>{label.createdBy ? `${userLabel(label.createdBy)} · ${formatDateTime(label.createdAt)}` : '시스템'}</td>
                <td>
                  <div className="row-actions">
                    <button type="button" className="small" disabled={editingId === label.id} onClick={() => onEdit(label.id)}>
                      이름 수정
                    </button>
                    <button type="button" className="small" disabled={busy} onClick={() => onDelete(label)}>
                      삭제
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {labels.length === 0 && (
              <tr>
                <td colSpan={4} className="empty">
                  등록된 Label이 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <form
        className="admin-form-row"
        aria-label={`${BANT_CATEGORY_NAMES[category]} Label 추가`}
        onSubmit={(e) => {
          e.preventDefault()
          onAdd(name, () => setName(''))
        }}
      >
        <TextField label="새 Label 이름" name={`new_label_${category}`} value={name} onChange={setName} />
        <button type="submit" className="primary" disabled={busy}>
          추가
        </button>
      </form>
    </section>
  )
}
