import { useId, useState } from 'react'
import { Link } from 'react-router'
import { gatewayMode } from '../../../gateway/mode'
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
import { TextField } from '../../../shared/ui/fields'
import { Notice } from '../../../shared/ui/Notice'

type Result = { kind: 'success' | 'error'; text: string } | null

/**
 * `saved`가 null이면(아직 등록 전) 설정 버전 1로 저장을 시도한다. 이 경우는 mock 모드에서만 온다:
 * 실제 서버는 설정이 없으면 버전과 관계없이 404라서 http 모드는 이 폼 대신 최초 설정 안내를 보인다(DirectorySection).
 */
function DirectoryForm({ saved }: { saved: DirectorySettings | null }) {
  const save = useSaveDirectory()
  const test = useTestDirectory()
  const [values, setValues] = useState<DirectoryFormValues>(() => (saved ? formFromDirectory(saved) : DEFAULT_DIRECTORY_FORM))
  const [password, setPassword] = useState('')
  const [result, setResult] = useState<Result>(null)
  const busy = save.isPending || test.isPending

  function run(action: 'test' | 'save') {
    setResult(null)
    const input = inputFromForm(values)
    // 비어 있으면 null(개발용 로그인 관리자는 비밀번호가 없다). 요청이 끝나면 비밀번호 칸을 비운다.
    const confirm = password === '' ? null : password
    const onError = (error: unknown) => setResult({ kind: 'error', text: directoryErrorMessage(error) })
    const onSettled = () => setPassword('')
    if (action === 'test') {
      test.mutate(
        { input, password: confirm },
        { onSuccess: () => setResult({ kind: 'success', text: '연결 테스트에 성공했습니다.' }), onError, onSettled },
      )
    } else {
      save.mutate(
        { input, password: confirm, expectedRevision: saved?.revision ?? 1 },
        { onSuccess: () => setResult({ kind: 'success', text: '저장했습니다' }), onError, onSettled },
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
          </Notice>
        </div>
      )}
      <div className="wide admin-grid">
        <DirectoryFields values={values} onChange={(patch) => setValues((prev) => ({ ...prev, ...patch }))} />
      </div>
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
  // 실제 서버는 설정이 없을 때 저장(PUT)을 항상 404로 거절한다. 최초 설정(/setup)이 등록 경로다.
  const needsSetup = settings.isSuccess && saved === null && gatewayMode() === 'http'
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
        {saved === null && !needsSetup && <p className="hint">아직 AD 서버가 등록되지 않았습니다.</p>}
      </header>
      <ErrorBanner error={settings.error} format={directoryErrorMessage} />
      {settings.isPending && <p className="hint">불러오는 중…</p>}
      {needsSetup && (
        <p>
          AD 서버가 아직 설정되지 않았습니다. 최초 설정에서 등록하세요. <Link to="/setup">최초 설정으로 이동</Link>
        </p>
      )}
      {settings.isSuccess && !needsSetup && <DirectoryForm saved={saved ?? null} />}
    </section>
  )
}
