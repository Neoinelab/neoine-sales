import { useState } from 'react'
import { useCreateVendor, useRemoveVendor, useRenameVendor, useVendors } from '../../../data/vendors'
import type { Vendor } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { TextField } from '../../../shared/ui/fields'
import { InlineNameEdit } from './InlineNameEdit'

/** Vendor 관리: 이름순 단일 표, 추가·이름 수정·삭제. 사용 중인 Vendor의 삭제 거절(409)은 서버 문구를 그대로 보인다. */
export function VendorManager() {
  const vendors = useVendors()
  const createVendor = useCreateVendor()
  const renameVendor = useRenameVendor()
  const removeVendor = useRemoveVendor()
  const [newName, setNewName] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deleting, setDeleting] = useState<Vendor | null>(null)
  const [error, setError] = useState<unknown>(null)
  const busy = createVendor.isPending || renameVendor.isPending || removeVendor.isPending

  function addVendor() {
    setError(null)
    createVendor.mutate(newName, { onSuccess: () => setNewName(''), onError: setError })
  }

  function confirmDelete(target: Vendor) {
    setError(null)
    removeVendor.mutate(target.id, { onError: setError, onSettled: () => setDeleting(null) })
  }

  return (
    <div className="admin-page">
      <p className="hint">
        Vendor 이름은 대소문자 구분 없이 중복될 수 없습니다. 사용 중인 Vendor는 이름을 바꿀 수 있지만 삭제할 수 없습니다.
      </p>
      <ErrorBanner error={error ?? vendors.error} />
      {vendors.isPending && <p className="hint">불러오는 중…</p>}
      {vendors.isSuccess && vendors.data.length === 0 && <p className="empty">등록된 Vendor가 없습니다.</p>}
      {vendors.isSuccess && (
        <div className="table-wrap">
          <table aria-label="Vendor 목록">
            <thead>
              <tr>
                <th>이름</th>
                <th>사용</th>
                <th>작업</th>
              </tr>
            </thead>
            <tbody>
              {vendors.data.map((vendor) => (
                <tr key={vendor.id}>
                  <td>
                    {editingId === vendor.id ? (
                      <InlineNameEdit
                        label="Vendor 이름"
                        initial={vendor.name}
                        busy={busy}
                        onSave={(name) => {
                          setError(null)
                          renameVendor.mutate({ id: vendor.id, name }, { onSuccess: () => setEditingId(null), onError: setError })
                        }}
                        onCancel={() => setEditingId(null)}
                      />
                    ) : (
                      vendor.name
                    )}
                  </td>
                  <td className="stat">{`Deal ${vendor.usageCount}건`}</td>
                  <td>
                    <div className="row-actions">
                      <button
                        type="button"
                        className="small"
                        disabled={editingId === vendor.id}
                        onClick={() => {
                          setError(null)
                          setEditingId(vendor.id)
                        }}
                      >
                        이름 수정
                      </button>
                      <button type="button" className="small" disabled={busy} onClick={() => setDeleting(vendor)}>
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
        className="admin-card"
        aria-label="Vendor 추가"
        onSubmit={(e) => {
          e.preventDefault()
          addVendor()
        }}
      >
        <div className="admin-form-row">
          <TextField label="새 Vendor 이름" name="new_vendor_name" value={newName} onChange={setNewName} />
          <button type="submit" className="primary" disabled={busy}>
            Vendor 추가
          </button>
        </div>
      </form>
      {deleting && (
        <ConfirmDialog
          title="Vendor 삭제"
          confirmLabel="삭제"
          danger
          busy={removeVendor.isPending}
          message={`'${deleting.name}' Vendor를 삭제할까요?`}
          onConfirm={() => confirmDelete(deleting)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  )
}
