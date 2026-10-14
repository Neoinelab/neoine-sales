import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { SelectField } from '../../shared/ui/fields'
import { useMe } from '../auth/hooks'
import { useUserOptions, type UserRef } from './options'

interface Props {
  label: string
  name: string
  /** 선택한 사용자 id(UUID). 선택 전에는 빈 문자열. */
  value: string
  onChange: (value: string) => void
  required?: boolean
  /** 수정 폼의 기존 값. 후보 목록에 없어도(퇴사자 등) 라벨로 보이지만, 퇴사자는 새로 고를 수 없다. */
  current?: UserRef
  /** 검색 필터용: 퇴사자도 후보에 넣고, 첫 항목을 '전체'로 한다. */
  includeResigned?: boolean
}

/** 사용자 선택(GET /api/v1/user-options). 표시는 서버가 만든 label만 쓴다. */
export function UserSelect({ label, name, value, onChange, required, current, includeResigned = false }: Props) {
  const options = useUserOptions(includeResigned)
  const me = useMe()
  const items: { id: string; label: string; disabled: boolean }[] = (options.data?.items ?? []).map((u) => ({
    id: u.id,
    label: u.label,
    disabled: u.resigned && !includeResigned,
  }))
  const has = (id: string) => items.some((i) => i.id === id)
  if (current && !has(current.id)) {
    items.push({ id: current.id, label: current.label, disabled: current.resigned && !includeResigned })
  }
  // 후보 수 제한(limit)에 밀려 로그인 사용자가 목록에 없어도 자동 선택값이 보이게 한다.
  if (me.data && value === me.data.user_id && !has(value)) {
    items.push({ id: value, label: me.data.name, disabled: false })
  }

  return (
    <>
      <SelectField label={label} name={name} value={value} onChange={onChange} required={required}>
        <option value="">{includeResigned ? '전체' : '선택하세요'}</option>
        {items.map((u) => (
          <option key={u.id} value={u.id} disabled={u.disabled}>
            {u.label}
          </option>
        ))}
      </SelectField>
      <ErrorBanner error={options.error} />
    </>
  )
}
