import { useState } from 'react'
import { useAttachments, useDownloadAttachment, useRemoveAttachment } from '../../../data/attachments'
import { formatDateTime } from '../../../shared/format'
import { canDeleteAttachment } from '../../../shared/model/permissions'
import { userLabel } from '../../../shared/model/period'
import type { Attachment, Me } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { Notice } from '../../../shared/ui/Notice'
import { formatBytes, messageOf, saveBlob } from './detailHelpers'
import { UploadForm } from './UploadForm'
import './detail.css'

interface AttachmentsPanelProps {
  dealCode: string
  me: Me | null
  canWrite: boolean
}

const NO_PERMISSION = '본인이 올린 파일만 삭제할 수 있습니다.'

/** 첨부 파일 영역(탭 밖). 모든 역할이 조회·다운로드, 업로드는 sales/admin, 삭제는 권한 규칙(permissions)대로. */
export function AttachmentsPanel({ dealCode, me, canWrite }: AttachmentsPanelProps) {
  const list = useAttachments(dealCode)
  const download = useDownloadAttachment()
  const remove = useRemoveAttachment()
  const [target, setTarget] = useState<Attachment | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const items = list.data ?? []

  async function save(id: string) {
    setError(null)
    try {
      const file = await download.mutateAsync(id)
      saveBlob(file.fileName, file.blob)
    } catch (caught) {
      setError(caught)
    }
  }

  async function confirmDelete() {
    if (!target) return
    setError(null)
    try {
      await remove.mutateAsync({ dealCode, attachmentId: target.id })
      setNotice(`삭제되었습니다: ${target.fileName}`)
    } catch (caught) {
      setError(caught)
    }
    setTarget(null)
  }

  return (
    <section aria-labelledby="dd-files" className="dd-card">
      <h2 id="dd-files">첨부 파일</h2>
      {canWrite && <UploadForm dealCode={dealCode} me={me} existing={items} onResult={setNotice} />}
      {notice && (
        <Notice kind="success" onClose={() => setNotice(null)}>
          {notice}
        </Notice>
      )}
      <ErrorBanner error={error} format={messageOf} />
      <ErrorBanner error={list.error} format={messageOf} />
      {list.isPending && <p role="status">불러오는 중…</p>}
      {list.isSuccess && items.length === 0 && <p className="hint">첨부된 파일이 없습니다.</p>}
      {items.length > 0 && (
        <div className="dd-scroll">
          <table className="dd-table" aria-label="첨부 파일 목록">
            <thead>
              <tr>
                <th>파일명</th>
                <th>설명</th>
                <th>크기</th>
                <th>업로드한 사용자</th>
                <th>업로드 시각</th>
                {canWrite && <th>관리</th>}
              </tr>
            </thead>
            <tbody>
              {items.map((a) => {
                const allowed = me !== null && canDeleteAttachment({ id: me.id, role: me.role }, a.uploadedBy)
                return (
                  <tr key={a.id}>
                    <td>
                      <button type="button" className="dd-link" onClick={() => void save(a.id)}>
                        {a.fileName}
                      </button>
                    </td>
                    <td className="wrap">{a.description || '—'}</td>
                    <td className="num">{formatBytes(a.size)}</td>
                    <td>{userLabel(a.uploadedBy)}</td>
                    <td>{formatDateTime(a.uploadedAt)}</td>
                    {canWrite && (
                      <td>
                        <button
                          type="button"
                          className="dd-small"
                          aria-label={`${a.fileName} 삭제`}
                          disabled={!allowed}
                          title={allowed ? undefined : NO_PERMISSION}
                          onClick={() => setTarget(a)}
                        >
                          삭제
                        </button>
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      {target && (
        <ConfirmDialog
          title="첨부 파일 삭제"
          message={`"${target.fileName}" 파일을 삭제합니다. 삭제는 Deal History에 기록됩니다.`}
          confirmLabel="삭제"
          danger
          busy={remove.isPending}
          onConfirm={() => void confirmDelete()}
          onCancel={() => setTarget(null)}
        />
      )}
    </section>
  )
}
