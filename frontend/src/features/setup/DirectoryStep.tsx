import { useRef, useState } from 'react'
import { useSaveSetupDirectory, useTestSetupDirectory } from '../../data/setup'
import { DEFAULT_DIRECTORY_FORM, inputFromForm, validateForm, type DirectoryFormValues } from '../../shared/directory/directoryForm'
import { DirectoryFields } from '../../shared/directory/DirectoryFields'
import { directoryErrorMessage } from '../../shared/directory/messages'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { Notice } from '../../shared/ui/Notice'

/** 1단계(AD 연동): 연결 테스트에 성공한 뒤에만 AD 서버를 등록한다. 입력이 바뀌면 성공이 무효가 된다. 실패해도 입력 값은 유지한다. */
export function DirectoryStep({ onSaved, onBack }: { onSaved: () => void; onBack: () => void }) {
  const [values, setValues] = useState<DirectoryFormValues>(DEFAULT_DIRECTORY_FORM)
  const save = useSaveSetupDirectory()
  const test = useTestSetupDirectory()
  const [invalid, setInvalid] = useState<string | null>(null)
  /** 마지막 연결 테스트가 성공한 상태(null이면 성공 전·무효). */
  const [baseDn, setBaseDn] = useState<string | null>(null)
  const [noticeOpen, setNoticeOpen] = useState(true)
  /** 입력이 바뀔 때마다 오르는 번호. 요청 때의 번호와 다르면 늦게 온 응답은 지금 입력의 결과가 아니다. */
  const inputVersion = useRef(0)
  const busy = save.isPending || test.isPending

  function change(next: DirectoryFormValues) {
    inputVersion.current += 1
    setValues(next)
    setBaseDn(null)
  }

  function runTest() {
    const problem = validateForm(values, 'setup')
    setInvalid(problem)
    save.reset()
    setBaseDn(null)
    if (problem !== null) return
    const sent = inputVersion.current
    test.mutate(inputFromForm(values), {
      onSuccess: (result) => {
        if (sent !== inputVersion.current) return
        setBaseDn(result.baseDn)
        setNoticeOpen(true)
      },
      onError: () => {
        if (sent !== inputVersion.current) test.reset()
      },
    })
  }

  return (
    <form
      className="setup-card"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        if (baseDn === null) return
        const problem = validateForm(values, 'setup')
        setInvalid(problem)
        if (problem !== null) return
        test.reset()
        save.mutate(inputFromForm(values), { onSuccess: onSaved, onError: () => setBaseDn(null) })
      }}
    >
      <h2>AD 서버 등록</h2>
      <p className="hint">로그인에 사용할 회사 AD 서버를 등록합니다.</p>
      <ErrorBanner error={invalid ?? save.error ?? test.error} format={(e) => (typeof e === 'string' ? e : directoryErrorMessage(e))} />
      {baseDn !== null ? (
        noticeOpen && (
          <Notice kind="success" onClose={() => setNoticeOpen(false)}>
            연결 테스트에 성공했습니다. Base DN: {baseDn}
          </Notice>
        )
      ) : (
        <p className="hint">연결 테스트에 성공해야 AD 서버를 등록할 수 있습니다.</p>
      )}
      <DirectoryFields values={values} onChange={change} />
      <div className="actions">
        <button type="button" onClick={onBack}>
          인증 방식 다시 선택
        </button>
        <button type="button" disabled={busy} onClick={runTest}>
          연결 테스트
        </button>
        <button type="submit" className="primary" disabled={busy || baseDn === null}>
          AD 서버 등록
        </button>
      </div>
    </form>
  )
}
