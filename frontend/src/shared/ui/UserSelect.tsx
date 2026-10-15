import { useUserOptions } from '../../data/users'
import { userLabel } from '../model/period'
import type { UserRef } from '../model/types'
import { SelectField } from './fields'
import './ui.css'

interface UserSelectProps {
  label: string
  name: string
  /** 선택한 사용자 id. 선택 전에는 빈 문자열. */
  value: string
  onChange: (value: string) => void
  required?: boolean
  /** 수정 폼의 기존 값. 후보에 없어도(퇴사자 등) 보이지만 퇴사자는 새로 고를 수 없다. */
  current?: UserRef
  /** 필터용: 퇴사자도 후보에 넣고 첫 항목을 '전체'로 한다(sales만으로 제한하지 않음). */
  includeResigned?: boolean
  error?: string
}

/** 사용자 선택. 기본은 재직 sales만(Owner 후보), 표시는 퇴사자면 "이름(퇴사)". */
export function UserSelect({ label, name, value, onChange, required, current, includeResigned = false, error }: UserSelectProps) {
  const options = useUserOptions(includeResigned ? { includeResigned: true } : { role: 'sales' })
  const users = [...(options.data ?? [])]
  if (current && !users.some((u) => u.id === current.id)) users.push(current)

  return (
    <>
      <SelectField label={label} name={name} value={value} onChange={onChange} required={required}>
        <option value="">{includeResigned ? '전체' : '선택하세요'}</option>
        {users.map((u) => (
          <option key={u.id} value={u.id} disabled={u.status === 'resigned' && !includeResigned}>
            {userLabel(u)}
          </option>
        ))}
      </SelectField>
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
    </>
  )
}
