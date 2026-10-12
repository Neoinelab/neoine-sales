import { useState } from 'react'
import type { Schemas } from '../../shared/api/client'
import { TextField } from '../../shared/ui/fields'

interface Props {
  submitLabel: string
  pending: boolean
  /** 요청을 보낸다. 실패하면 reject해야 비밀번호 칸이 비워진다. */
  onSubmit: (credentials: Schemas['LoginRequest']) => Promise<unknown>
}

/** AD 아이디·비밀번호 입력. 비밀번호는 이 컴포넌트의 상태에만 있고 실패하면 비운다. */
export function CredentialsForm({ submitLabel, pending, onSubmit }: Props) {
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit({ login_id: loginId.trim(), password }).catch(() => setPassword(''))
      }}
    >
      <TextField label="AD 아이디" name="login_id" required value={loginId} onChange={setLoginId} />
      <TextField label="비밀번호" name="password" type="password" required value={password} onChange={setPassword} />
      <button type="submit" className="primary" disabled={pending}>
        {submitLabel}
      </button>
    </form>
  )
}
