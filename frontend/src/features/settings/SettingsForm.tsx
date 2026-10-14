import { useState } from 'react'
import type { Schemas } from '../../shared/api/client'
import { ApiError } from '../../shared/api/problem'
import { formFromSettings, requestFromForm, type DirectoryFormValues } from '../../shared/directory/directoryForm'
import { DirectoryFields } from '../../shared/directory/DirectoryFields'
import { directoryErrorMessage, stageMessage } from '../../shared/directory/messages'
import { formatDateTime } from '../../shared/format'
import { TextField } from '../../shared/ui/fields'
import { useSaveDirectory, useTestDirectory } from './hooks'

type Notice = { kind: 'status' | 'alert'; text: string } | null

function saveErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return '다른 곳에서 설정이 변경되었습니다. 새로고침한 뒤 다시 시도하세요.'
  }
  return directoryErrorMessage(error)
}

/** 저장된 AD 설정의 편집 폼. 연결 테스트와 저장 모두 현재 관리자 비밀번호로 인증을 확인한다. */
export function SettingsForm({
  initial,
  needsPassword,
}: {
  initial: Schemas['DirectorySettingsResponse']
  /** 개발용 로그인 admin은 AD 비밀번호가 없어 false. */
  needsPassword: boolean
}) {
  const test = useTestDirectory()
  const save = useSaveDirectory()
  const [values, setValues] = useState<DirectoryFormValues>(() => formFromSettings(initial))
  const [password, setPassword] = useState('')
  const [revision, setRevision] = useState(initial.revision)
  const [meta, setMeta] = useState({ by: initial.updated_by?.label ?? null, at: initial.updated_at })
  const [notice, setNotice] = useState<Notice>(null)
  const busy = test.isPending || save.isPending
  const passwordOrNull = password === '' ? null : password

  const runTest = () => {
    if (needsPassword && !password) return
    setNotice(null)
    test.mutate(
      { ...requestFromForm(values), password: passwordOrNull },
      {
        onSuccess: (result) => {
          const stage = stageMessage(result.stage)
          setNotice({ kind: 'status', text: result.success || !stage ? result.message : `${stage} ${result.message}` })
        },
        onError: (error) => setNotice({ kind: 'alert', text: directoryErrorMessage(error) }),
        onSettled: () => setPassword(''),
      },
    )
  }

  const runSave = () => {
    if (needsPassword && !password) return
    setNotice(null)
    save.mutate(
      { ...requestFromForm(values), expected_revision: revision, password: passwordOrNull },
      {
        onSuccess: (saved) => {
          setRevision(saved.revision)
          setMeta({ by: saved.updated_by?.label ?? null, at: saved.updated_at })
          setNotice({ kind: 'status', text: '저장했습니다' })
        },
        onError: (error) => setNotice({ kind: 'alert', text: saveErrorMessage(error) }),
        onSettled: () => setPassword(''),
      },
    )
  }

  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault()
        runSave()
      }}
    >
      <p className="hint">{`마지막 수정: ${meta.by ?? '-'} · ${formatDateTime(meta.at)}`}</p>
      {notice?.kind === 'alert' && (
        <p role="alert" className="error">
          {notice.text}
        </p>
      )}
      {notice?.kind === 'status' && <p role="status">{notice.text}</p>}
      <DirectoryFields values={values} onChange={(patch) => setValues((prev) => ({ ...prev, ...patch }))} />
      <TextField
        label="현재 관리자 비밀번호(새 설정으로 인증 확인용)"
        name="password"
        type="password"
        required={needsPassword}
        value={password}
        onChange={setPassword}
      />
      <div className="row-actions">
        <button type="button" disabled={busy} onClick={runTest}>
          연결 테스트
        </button>
        <button type="submit" className="primary" disabled={busy}>
          저장
        </button>
      </div>
    </form>
  )
}
