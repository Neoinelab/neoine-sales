import { useId, useState } from 'react'
import { useSaveStorage, useStorageSettings, useTestStorage } from '../../../data/settings'
import { directoryErrorMessage } from '../../../shared/directory/messages'
import { formatDateTime } from '../../../shared/format'
import { userLabel } from '../../../shared/model/period'
import type { StorageSettings } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { TextField } from '../../../shared/ui/fields'
import { Notice } from '../../../shared/ui/Notice'

type Result = { kind: 'success' | 'error'; text: string } | null

function StorageForm({ saved }: { saved: StorageSettings | null }) {
  const save = useSaveStorage()
  const test = useTestStorage()
  const [path, setPath] = useState(saved?.path ?? '')
  const [result, setResult] = useState<Result>(null)
  const busy = save.isPending || test.isPending

  function run(action: 'test' | 'save') {
    setResult(null)
    const onError = (error: unknown) => setResult({ kind: 'error', text: directoryErrorMessage(error) })
    if (action === 'test') {
      test.mutate(path, { onSuccess: () => setResult({ kind: 'success', text: '쓰기 테스트에 성공했습니다.' }), onError })
    } else {
      save.mutate(path, { onSuccess: () => setResult({ kind: 'success', text: '저장했습니다' }), onError })
    }
  }

  return (
    <form
      noValidate
      className="admin-card"
      aria-label="파일 저장 위치 변경"
      onSubmit={(e) => {
        e.preventDefault()
        run('save')
      }}
    >
      {result && (
        <Notice kind={result.kind} onClose={() => setResult(null)}>
          {result.text}
        </Notice>
      )}
      <TextField label="저장 경로" name="storage_path" value={path} onChange={setPath} />
      <p className="hint">서버의 절대 경로를 입력하세요. 예: /var/lib/neoine-sales/files</p>
      <div className="actions">
        <button type="button" disabled={busy} onClick={() => run('test')}>
          쓰기 테스트
        </button>
        <button type="submit" className="primary" disabled={busy}>
          저장
        </button>
      </div>
    </form>
  )
}

/** 외부연동 ②: Deal 첨부 파일이 저장되는 위치(FL-06, 5.8). 바꿔도 기존 파일은 자동으로 옮겨지지 않는다. */
export function StorageSection() {
  const titleId = useId()
  const settings = useStorageSettings()
  const saved = settings.data
  return (
    <section className="admin-card" aria-labelledby={titleId}>
      <header>
        <h3 id={titleId}>파일 저장 위치</h3>
        <p className="hint">첨부 파일이 저장되는 서버 디렉터리입니다.</p>
        {saved && (
          <>
            <p>{`현재 위치: ${saved.path}`}</p>
            <p className="hint">{`마지막 수정: ${saved.updatedBy ? userLabel(saved.updatedBy) : '-'} · ${formatDateTime(saved.updatedAt)}`}</p>
          </>
        )}
        {saved === null && <p className="hint">아직 저장 위치가 설정되지 않았습니다.</p>}
        <p className="admin-note">위치를 바꿔도 기존 파일 이동은 관리자가 수작업으로 처리합니다. 기존 파일은 자동으로 옮겨지지 않습니다.</p>
      </header>
      <ErrorBanner error={settings.error} />
      {settings.isPending && <p className="hint">불러오는 중…</p>}
      {settings.isSuccess && <StorageForm saved={saved ?? null} />}
    </section>
  )
}
