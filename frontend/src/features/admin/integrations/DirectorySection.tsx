import { useId, useState } from 'react'
import { useDirectorySettings, useSaveDirectory, useTestDirectory } from '../../../data/settings'
import {
  DEFAULT_DIRECTORY_FORM,
  clearTypedBindPassword,
  formFromDirectory,
  inputFromForm,
  validateForm,
  type DirectoryFormValues,
} from '../../../shared/directory/directoryForm'
import { DirectoryFields } from '../../../shared/directory/DirectoryFields'
import { directoryErrorMessage } from '../../../shared/directory/messages'
import { formatDateTime } from '../../../shared/format'
import { userLabel } from '../../../shared/model/period'
import type { DirectorySettings } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { TextField } from '../../../shared/ui/fields'
import { Notice } from '../../../shared/ui/Notice'

type Result = { kind: 'success' | 'error'; text: string; baseDn?: string | null } | null

/** 저장된 설정을 고치거나(saved 있음), 설정이 없을 때 처음 등록한다(saved null, expectedRevision null). */
function DirectoryForm({ saved }: { saved: DirectorySettings | null }) {
  const save = useSaveDirectory()
  const test = useTestDirectory()
  const [values, setValues] = useState<DirectoryFormValues>(() => (saved ? formFromDirectory(saved) : DEFAULT_DIRECTORY_FORM))
  const [password, setPassword] = useState('')
  const [result, setResult] = useState<Result>(null)
  const busy = save.isPending || test.isPending

  function run(action: 'test' | 'save') {
    setResult(null)
    const invalid = validateForm(values, 'settings')
    if (invalid) {
      setResult({ kind: 'error', text: invalid })
      return
    }
    const input = inputFromForm(values)
    // 비어 있으면 null(개발용 로그인 관리자는 비밀번호가 없다). 요청이 끝나면 비밀번호 칸들을 비운다.
    const confirm = password === '' ? null : password
    const onSettled = () => setPassword('')
    const onError = (error: unknown) => {
      setResult({ kind: 'error', text: directoryErrorMessage(error) })
      setValues(clearTypedBindPassword)
    }
    if (action === 'test') {
      test.mutate(
        { input, password: confirm },
        {
          onSuccess: (found) => {
            setResult({ kind: 'success', text: '연결 테스트에 성공했습니다.', baseDn: found.baseDn })
            setValues(clearTypedBindPassword)
          },
          onError,
          onSettled,
        },
      )
    } else {
      save.mutate(
        { input, password: confirm, expectedRevision: saved?.revision ?? null },
        {
          onSuccess: (stored) => {
            setValues(formFromDirectory(stored))
            setResult({ kind: 'success', text: '저장했습니다' })
          },
          onError,
          onSettled,
        },
      )
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
            {result.baseDn ? <span>{` Base DN: ${result.baseDn}`}</span> : null}
          </Notice>
        </div>
      )}
      <div className="wide admin-grid">
        <DirectoryFields values={values} onChange={setValues} />
      </div>
      {saved && (
        <p className="wide hint">
          {'Base DN(AD에서 자동 확인): '}
          <code>{saved.baseDn}</code>
        </p>
      )}
      <div className="wide">
        <TextField
          label="현재 관리자 비밀번호(새 설정으로 인증을 확인합니다)"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={setPassword}
        />
        <p className="hint">AD로 로그인한 관리자는 비밀번호를 입력하세요. 개발용 로그인 관리자는 비워 둡니다.</p>
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
      </header>
      <ErrorBanner error={settings.error} format={directoryErrorMessage} />
      {settings.isPending && <p className="hint">불러오는 중…</p>}
      {settings.isSuccess && saved === null && <p className="hint">AD 서버가 아직 설정되지 않았습니다. 아래에서 등록하세요.</p>}
      {settings.isSuccess && <DirectoryForm saved={saved ?? null} />}
    </section>
  )
}
