import { useState } from 'react'
import type { Schemas } from '../../shared/api/client'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { SelectField, TextField } from '../../shared/ui/fields'
import { useAddUser } from './hooks'

/** 로그인을 허용할 AD 계정을 역할과 함께 등록한다(비밀번호는 AD가 확인한다). */
export function AddUserForm() {
  const add = useAddUser()
  const [loginId, setLoginId] = useState('')
  const [role, setRole] = useState<Schemas['Role']>('sales')
  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault()
        const id = loginId.trim()
        if (!id) return
        add.mutate({ login_id: id, role }, { onSuccess: () => setLoginId('') })
      }}
    >
      <ErrorBanner error={add.error} />
      <TextField label="AD 아이디" name="login_id" value={loginId} onChange={setLoginId} />
      <SelectField label="역할" name="role" value={role} onChange={(v) => setRole(v as Schemas['Role'])}>
        <option value="admin">admin</option>
        <option value="sales">sales</option>
        <option value="user">user</option>
      </SelectField>
      <button type="submit" className="primary" disabled={add.isPending}>
        추가
      </button>
    </form>
  )
}
