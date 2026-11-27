import { useState, type FormEvent } from 'react'
import { usePermissions } from '../../data/auth'
import { useContractAttachments, useDownloadContractAttachment, useRemoveContractAttachment, useUploadContractAttachment } from '../../data/licenseContracts'
import { formatDateTime } from '../../shared/format'
import { MAX_FILE_DESCRIPTION } from '../../shared/model/constants'
import { validateUpload } from '../../shared/model/fileRules'
import { canDeleteAttachment } from '../../shared/model/permissions'
import { userLabel } from '../../shared/model/period'
import type { ContractAttachment, OnExists } from '../../shared/model/types'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { charCount, errorKind, formatBytes, messageOf, saveBlob } from '../deals/detail/detailHelpers'
import '../deals/detail/detail.css'

interface ContractAttachmentsProps {
  contractId: number
}

const NO_PERMISSION = '본인이 올린 파일만 삭제할 수 있습니다.'

/** 계약 첨부 파일. Deal 상세 첨부와 같은 모양·규칙·문구이며 서버(게이트웨이)에 저장한다. 조회·다운로드는 모든 역할, 업로드는 sales/admin. */
export function ContractAttachments({ contractId }: ContractAttachmentsProps) {
  const { me, canWrite } = usePermissions()
  const list = useContractAttachments(contractId)
  const upload = useUploadContractAttachment()
  const remove = useRemoveContractAttachment()
  const download = useDownloadContractAttachment()
  const [file, setFile] = useState<File | null>(null)
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState<string | null>(null)
  const [inputKey, setInputKey] = useState(0)
  const [target, setTarget] = useState<ContractAttachment | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const items = list.data ?? []
  const count = charCount(description.trim())
  const viewer = me ? { id: me.id, role: me.role } : null
  const conflicting = conflict === null ? undefined : items.find((a) => a.fileName.normalize('NFC') === conflict.normalize('NFC'))
  const canReplace = conflicting === undefined || (viewer !== null && canDeleteAttachment(viewer, conflicting.uploadedBy))

  async function send(onExists: Exclude<OnExists, 'skip'>) {
    if (file === null) return
    setError(null)
    try {
      const result = await upload.mutateAsync({ contractId, input: { file, description, onExists } })
      setConflict(null)
      if (result.outcome === 'skipped') return
      setNotice(`${result.outcome === 'replaced' ? '교체' : '업로드'}되었습니다: ${file.name}`)
      setFile(null)
      setDescription('')
      setInputKey((k) => k + 1)
    } catch (caught) {
      if (errorKind(caught) === 'file-exists') setConflict(file.name)
      else {
        // 교체 중 오류(403 등)가 대화상자 뒤에 숨지 않게 대화상자를 닫고 알림으로 보인다.
        setConflict(null)
        setError(messageOf(caught))
      }
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    const rule = validateUpload(file, description)
    if (rule) {
      setError(rule.message)
      return
    }
    void send('ask')
  }

  async function save(item: ContractAttachment) {
    setError(null)
    try {
      const downloaded = await download.mutateAsync(item.id)
      saveBlob(downloaded.fileName, downloaded.blob)
    } catch (caught) {
      setError(messageOf(caught))
    }
  }

  async function confirmDelete() {
    if (!target) return
    setError(null)
    try {
      await remove.mutateAsync({ contractId, attachmentId: target.id })
      setNotice(`삭제되었습니다: ${target.fileName}`)
    } catch (caught) {
      setError(messageOf(caught))
    }
    setTarget(null)
  }

  return (
    <section aria-labelledby="contract-files" className="contract-files">
      <h3 id="contract-files">첨부 파일</h3>
      {canWrite && (
        <form aria-label="파일 업로드" className="contract-upload" onSubmit={submit} noValidate>
          <label className="field">
            <span>설명</span>
            <input type="text" value={description} disabled={upload.isPending} onChange={(e) => setDescription(e.target.value)} />
          </label>
          <span className={count > MAX_FILE_DESCRIPTION ? 'dd-count over' : 'dd-count'}>
            {count}/{MAX_FILE_DESCRIPTION}
          </span>
          <label className="field">
            <span>파일</span>
            <input
              key={inputKey}
              type="file"
              disabled={upload.isPending}
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null)
                setError(null)
              }}
            />
          </label>
          <button type="submit" className="primary" disabled={upload.isPending}>
            업로드
          </button>
        </form>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <ErrorBanner error={list.error} format={messageOf} />
      {notice && (
        <p role="status" className="hint">
          {notice}
        </p>
      )}
      {list.isPending && <p className="hint">불러오는 중…</p>}
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
                const allowed = viewer !== null && canDeleteAttachment(viewer, a.uploadedBy)
                return (
                  <tr key={a.id}>
                    <td>
                      <button type="button" className="dd-link" onClick={() => void save(a)}>
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
      {conflict !== null && (
        <ConfirmDialog
          title="같은 이름의 파일"
          message={`같은 이름의 파일이 이미 있습니다: ${conflict}`}
          confirmLabel="덮어쓰기"
          confirmDisabled={!canReplace}
          cancelLabel="취소"
          busy={upload.isPending}
          onConfirm={() => void send('replace')}
          onCancel={() => setConflict(null)}
        >
          {!canReplace && <p className="hint">본인이 올린 파일만 교체할 수 있습니다.</p>}
        </ConfirmDialog>
      )}
      {target && (
        <ConfirmDialog
          title="첨부 파일 삭제"
          message={`"${target.fileName}" 파일을 삭제합니다.`}
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
