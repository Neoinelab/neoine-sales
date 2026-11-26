import type { DirectorySecurity } from '../model/types'
import { SelectField, TextField } from '../ui/fields'
import { changeSecurity, type DirectoryFormValues } from './directoryForm'

interface Props {
  values: DirectoryFormValues
  onChange: (next: DirectoryFormValues) => void
}

export function DirectoryFields({ values, onChange }: Props) {
  const patch = (change: Partial<DirectoryFormValues>) => onChange({ ...values, ...change })
  return <>
    <TextField autoComplete="off" label="호스트" name="host" required value={values.host} onChange={(host) => patch({ host })} />
    <TextField label="포트" name="port" type="number" required value={values.port} onChange={(port) => patch({ port })} />
    <SelectField label="보안 연결" name="security" required value={values.security} onChange={(security) => onChange(changeSecurity(values, security as DirectorySecurity))}>
      <option value="none">없음</option><option value="ssl">SSL</option><option value="starttls">StartTLS</option>
    </SelectField>
    <p className="wide hint">{values.security === 'none'
      ? '보안 연결 없음: 비밀번호가 암호화되지 않은 채 전송됩니다. 신뢰하는 내부망에서만 쓰세요.'
      : `${values.security === 'ssl' ? 'SSL' : 'StartTLS'}: 연결은 암호화되지만 서버 인증서를 검증하지 않습니다.`}</p>
    <TextField autoComplete="off" label="사용자 검색 필터" name="user_filter" required value={values.userFilter} onChange={(userFilter) => patch({ userFilter })} />
    <TextField label="연결 제한 시간(초)" name="connect_timeout_seconds" type="number" required value={values.connectTimeoutSeconds} onChange={(connectTimeoutSeconds) => patch({ connectTimeoutSeconds })} />
  </>
}
