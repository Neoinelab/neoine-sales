import { useId, useState } from 'react'
import type { Solution, Vendor } from '../../../shared/model/types'
import { TextField } from '../../../shared/ui/fields'
import { InlineNameEdit } from './InlineNameEdit'

interface Props {
  vendor: Vendor
  editingId: string | null
  busy: boolean
  onEdit: (id: string | null) => void
  onRenameVendor: (vendor: Vendor, name: string) => void
  onDeleteVendor: (vendor: Vendor) => void
  onAddSolution: (vendor: Vendor, name: string, done: () => void) => void
  onRenameSolution: (solution: Solution, name: string) => void
  onDeleteSolution: (solution: Solution) => void
}

/** Vendor 하나의 카드: 이름·사용 수·수정·삭제, 소속 Solution 표, Solution 추가 입력. */
export function VendorCard(props: Props) {
  const { vendor, editingId, busy, onEdit, onRenameVendor, onDeleteVendor } = props
  const { onAddSolution, onRenameSolution, onDeleteSolution } = props
  const titleId = useId()
  const [name, setName] = useState('')
  const editingVendor = editingId === vendor.id
  return (
    <section className="admin-card" aria-labelledby={titleId}>
      <header>
        <h3 id={titleId}>{vendor.name}</h3>
        {editingVendor && (
          <InlineNameEdit
            label="Vendor 이름"
            initial={vendor.name}
            busy={busy}
            onSave={(next) => onRenameVendor(vendor, next)}
            onCancel={() => onEdit(null)}
          />
        )}
        <span className="stat">{`Deal ${vendor.usageCount}건`}</span>
        <div className="row-actions">
          <button type="button" className="small" disabled={editingVendor} onClick={() => onEdit(vendor.id)}>
            Vendor 이름 수정
          </button>
          <button type="button" className="small" disabled={busy} onClick={() => onDeleteVendor(vendor)}>
            Vendor 삭제
          </button>
        </div>
      </header>
      {vendor.solutions.length === 0 ? (
        <p className="hint">Solution이 없습니다.</p>
      ) : (
        <div className="table-wrap">
          <table aria-label={`${vendor.name} Solution 목록`}>
            <thead>
              <tr>
                <th>이름</th>
                <th>사용</th>
                <th>작업</th>
              </tr>
            </thead>
            <tbody>
              {vendor.solutions.map((solution) => (
                <tr key={solution.id}>
                  <td>
                    {editingId === solution.id ? (
                      <InlineNameEdit
                        label="Solution 이름"
                        initial={solution.name}
                        busy={busy}
                        onSave={(next) => onRenameSolution(solution, next)}
                        onCancel={() => onEdit(null)}
                      />
                    ) : (
                      solution.name
                    )}
                  </td>
                  <td className="stat">{`Deal ${solution.usageCount}건`}</td>
                  <td>
                    <div className="row-actions">
                      <button type="button" className="small" disabled={editingId === solution.id} onClick={() => onEdit(solution.id)}>
                        이름 수정
                      </button>
                      <button type="button" className="small" disabled={busy} onClick={() => onDeleteSolution(solution)}>
                        삭제
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form
        className="admin-form-row"
        aria-label={`${vendor.name} Solution 추가`}
        onSubmit={(e) => {
          e.preventDefault()
          onAddSolution(vendor, name, () => setName(''))
        }}
      >
        <TextField label="새 Solution 이름" name={`new_solution_${vendor.id}`} value={name} onChange={setName} />
        <button type="submit" className="primary" disabled={busy}>
          Solution 추가
        </button>
      </form>
    </section>
  )
}
