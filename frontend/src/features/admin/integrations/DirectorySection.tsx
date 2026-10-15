import { useId, useState } from 'react'
import { useDirectorySettings, useSaveDirectory, useTestDirectory } from '../../../data/settings'
import {
  DEFAULT_DIRECTORY_FORM,
  formFromDirectory,
  inputFromForm,
  type DirectoryFormValues,
} from '../../../shared/directory/directoryForm'
import { DirectoryFields } from '../../../shared/directory/DirectoryFields'
import { directoryErrorMessage } from '../../../shared/directory/messages'
import { formatDateTime } from '../../../shared/format'
import { userLabel } from '../../../shared/model/period'
import type { DirectorySettings } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { Notice } from '../../../shared/ui/Notice'

type Result = { kind: 'success' | 'error'; text: string } | null

function DirectoryForm({ saved }: { saved: DirectorySettings | null }) {
  const save = useSaveDirectory()
  const test = useTestDirectory()
  const [values, setValues] = useState<DirectoryFormValues>(() => (saved ? formFromDirectory(saved) : DEFAULT_DIRECTORY_FORM))
  const [result, setResult] = useState<Result>(null)
  const busy = save.isPending || test.isPending

  function run(action: 'test' | 'save') {
    setResult(null)
    const input = inputFromForm(values)
    const onError = (error: unknown) => setResult({ kind: 'error', text: directoryErrorMessage(error) })
    if (action === 'test') {
      test.mutate(input, { onSuccess: () => setResult({ kind: 'success', text: '연결 테스트에 성공했습니다.' }), onError })
    } else {
      save.mutate(input, { onSuccess: () => setResult({ kind: 'success', text: '저장했습니다' }), onError })
    }
  }

  return (
    <form
      noValidate
      className="admin-grid"
      onSubmit={(e) => {
        e.preventDefault()
        run('save')
      }}
    >
      {result && (
        <div className="wide">
          <Notice kind={result.kind} onClose={() => setResult(null)}>
            {result.text}
          </Notice>
        </div>
      )}
      <div className="wide admin-grid">
        <DirectoryFields values={values} onChange={(patch) => setValues((prev) => ({ ...prev, ...patch }))} />
      </div>
      <div className="wide actions">
        <button type="button" disabled={busy} onClick={() => run('test')}>
          연결 테스트
        </button>
        <button type="submit" className="primary" disabled={busy}>
          저장
        </button>
      </div>
    </form>
  )
}

/** 외부연동 ①: 로그인에 쓰는 AD(LDAP) 서버 설정. 저장하면 설정 버전이 올라가고 마지막 수정자·시각이 갱신된다. */
export function DirectorySection() {
  const titleId = useId()
  const settings = useDirectorySettings()
  const saved = settings.data
  return (
    <section className="admin-card" aria-labelledby={titleId}>
      <header>
        <h3 id={titleId}>AD(LDAP) 서버 설정</h3>
        {saved && (
          <>
            <p className="hint">{`마지막 수정: ${saved.updatedBy ? userLabel(saved.updatedBy) : '-'} · ${formatDateTime(saved.updatedAt)}`}</p>
            <p className="hint">{`설정 버전 ${saved.revision}`}</p>
          </>
        )}
        {saved === null && <p className="hint">아직 AD 서버가 등록되지 않았습니다.</p>}
      </header>
      <ErrorBanner error={settings.error} format={directoryErrorMessage} />
      {settings.isPending && <p className="hint">불러오는 중…</p>}
      {settings.isSuccess && <DirectoryForm saved={saved ?? null} />}
    </section>
  )
}
