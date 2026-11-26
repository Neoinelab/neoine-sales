import { useEffect, useRef, useState } from 'react'
import type { DirectoryTestResult } from '../../gateway/types'
import type { DirectorySettingsInput, DirectoryTestInput } from '../model/types'
import { ErrorBanner } from '../ui/ErrorBanner'
import { TextField } from '../ui/fields'
import { Modal } from '../ui/Modal'
import { directoryErrorMessage } from './messages'
import './directory.css'

interface Props {
  input: DirectorySettingsInput
  test: (input: DirectoryTestInput) => Promise<DirectoryTestResult>
  onSuccess: (result: DirectoryTestResult) => void
  onClose: () => void
}

export function DirectoryTestDialog({ input, test, onSuccess, onClose }: Props) {
  const [account, setAccount] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const closed = useRef(false)
  useEffect(() => {
    closed.current = false
    return () => { closed.current = true }
  }, [])
  function close() {
    closed.current = true
    setAccount('')
    setPassword('')
    onClose()
  }
  async function submit() {
    if (busy) return
    if (!account.trim() || !password) {
      setError('바인드 계정과 비밀번호를 입력하세요.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const result = await test({ ...input, bindAccount: account, bindPassword: password })
      if (!closed.current) { onSuccess(result); close() }
    } catch (failure) {
      if (!closed.current) setError(failure)
    } finally {
      setAccount('')
      setPassword('')
      setBusy(false)
    }
  }
  return <Modal title="AD 연결 테스트" onClose={close}>
    <form className="directory-test-form" onSubmit={(event) => { event.preventDefault(); void submit() }}>
      <p className="hint">아이디만 입력하면 회사 AD 도메인이 자동으로 붙습니다. 계정과 비밀번호는 연결 테스트에만 사용됩니다.</p>
      <ErrorBanner error={error} format={(value) => typeof value === 'string' ? value : directoryErrorMessage(value)} />
      <TextField label="바인드 계정" name="bind_account" autoComplete="off" value={account} onChange={setAccount} />
      <TextField label="바인드 비밀번호" name="bind_password" type="password" autoComplete="new-password" value={password} onChange={setPassword} />
      <div className="modal-actions">
        <button type="button" onClick={close}>취소</button>
        <button type="submit" className="primary" disabled={busy}>{busy ? '테스트 중…' : '테스트 실행'}</button>
      </div>
    </form>
  </Modal>
}
