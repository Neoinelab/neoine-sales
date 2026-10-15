import { useState, type FormEvent } from 'react'
import { useUploadAttachment } from '../../../data/attachments'
import { MAX_FILE_DESCRIPTION } from '../../../shared/model/constants'
import { validateUpload } from '../../../shared/model/fileRules'
import type { OnExists } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { charCount, errorKind, messageOf } from './detailHelpers'

interface UploadFormProps {
  dealCode: string
  onResult: (message: string) => void
}

/** 파일 업로드 폼: 파일 + 설명(100자, 글자수 표시). 화면에서 먼저 규칙을 검사하고, 같은 이름이면 교체/건너뛰기를 묻는다. */
export function UploadForm({ dealCode, onResult }: UploadFormProps) {
  const upload = useUploadAttachment()
  const [file, setFile] = useState<File | null>(null)
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState<string | null>(null)
  const [inputKey, setInputKey] = useState(0)
  const count = charCount(description)

  async function send(onExists: OnExists) {
    if (file === null) return
    setError(null)
    try {
      const result = await upload.mutateAsync({ dealCode, input: { file, description, onExists } })
      setConflict(null)
      if (result.outcome === 'skipped') return
      onResult(`${result.outcome === 'replaced' ? '교체' : '업로드'}되었습니다: ${file.name}`)
      setFile(null)
      setDescription('')
      setInputKey((k) => k + 1)
    } catch (caught) {
      if (errorKind(caught) === 'file-exists') setConflict(file.name)
      else setError(messageOf(caught))
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

  return (
    <>
      <form aria-label="파일 업로드" className="dd-upload" onSubmit={submit} noValidate>
        <label className="field">
          <span>파일</span>
          <input
            key={inputKey}
            type="file"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null)
              setError(null)
            }}
          />
        </label>
        <label className="field">
          <span>설명</span>
          <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <span className={count > MAX_FILE_DESCRIPTION ? 'dd-count over' : 'dd-count'}>
          {count}/{MAX_FILE_DESCRIPTION}
        </span>
        <button type="submit" className="primary" disabled={upload.isPending}>
          업로드
        </button>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {conflict !== null && (
        <ConfirmDialog
          title="같은 이름의 파일"
          message={`같은 이름의 파일이 이미 있습니다: ${conflict}`}
          confirmLabel="교체"
          cancelLabel="건너뛰기"
          busy={upload.isPending}
          onConfirm={() => void send('replace')}
          onCancel={() => setConflict(null)}
        />
      )}
    </>
  )
}
