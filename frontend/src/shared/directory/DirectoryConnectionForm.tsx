import { useRef, useState } from 'react'
import type { DirectoryTestResult } from '../../gateway/types'
import type { DirectorySaveInput, DirectorySettings, DirectoryTestInput } from '../model/types'
import { ErrorBanner } from '../ui/ErrorBanner'
import { DirectoryFields } from './DirectoryFields'
import { DirectoryTestDialog } from './DirectoryTestDialog'
import { DEFAULT_DIRECTORY_FORM, formFromDirectory, inputFromForm, validateForm, type DirectoryFormValues } from './directoryForm'
import { directoryErrorMessage } from './messages'

interface Props {
  saved?: DirectorySettings | null
  setup?: boolean
  save: (input: DirectorySaveInput) => Promise<unknown>
  test: (input: DirectoryTestInput) => Promise<DirectoryTestResult>
  onBack?: () => void
}

export function DirectoryConnectionForm({ saved, setup = false, save, test, onBack }: Props) {
  const [values, setValues] = useState(() => saved ? formFromDirectory(saved) : DEFAULT_DIRECTORY_FORM)
  const [proof, setProof] = useState<DirectoryTestResult | null>(null)
  const [dialog, setDialog] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [notice, setNotice] = useState('')
  const version = useRef(0)
  const testedVersion = useRef(0)
  function change(next: DirectoryFormValues) {
    version.current += 1
    setValues(next)
    setProof(null)
    setNotice('')
  }
  async function submit() {
    if (!proof || busy) return
    setBusy(true)
    setError(null)
    try {
      await save({ ...inputFromForm(values), testToken: proof.testToken })
      setNotice('저장했습니다.')
      setProof(null)
    } catch (failure) {
      setError(failure)
      setProof(null)
    } finally {
      setBusy(false)
    }
  }
  return <>
    <form className={setup ? 'setup-card' : 'admin-grid'} noValidate onSubmit={(event) => { event.preventDefault(); void submit() }}>
      {setup && <><h2>AD 서버 등록</h2><p className="hint">로그인에 사용할 회사 AD 서버를 등록합니다.</p></>}
      <div className="wide"><ErrorBanner error={error} format={(value) => typeof value === 'string' ? value : directoryErrorMessage(value)} /></div>
      {notice && <p className="wide hint" role="status">{notice}</p>}
      <div className={setup ? undefined : 'wide admin-grid'}><DirectoryFields values={values} onChange={change} /></div>
      <p className="wide hint">{proof ? `연결 테스트에 성공했습니다. Base DN: ${proof.baseDn ?? '-'}` : '연결 테스트에 성공해야 AD 서버를 저장할 수 있습니다.'}</p>
      {saved && <p className="wide hint">Base DN(AD에서 자동 확인): <code>{saved.baseDn}</code></p>}
      <div className="wide actions">
        {onBack && <button type="button" onClick={onBack}>인증 방식 다시 선택</button>}
        <button type="button" disabled={busy || dialog} onClick={() => {
          const invalid = validateForm(values)
          setError(invalid)
          setNotice('')
          setProof(null)
          if (!invalid) { testedVersion.current = version.current; setDialog(true) }
        }}>연결 테스트</button>
        <button type="submit" className="primary" disabled={busy || !proof}>{setup ? 'AD 서버 등록' : '저장'}</button>
      </div>
    </form>
    {dialog && <DirectoryTestDialog input={inputFromForm(values)} test={test} onClose={() => setDialog(false)} onSuccess={(result) => {
      if (testedVersion.current === version.current) setProof(result)
    }} />}
  </>
}
