import { SelectField, TextField } from '../ui/fields'
import {
  blurBindPassword,
  changeEndpointField,
  focusBindPassword,
  typeBindPassword,
  type DirectoryFormValues,
} from './directoryForm'

interface Props {
  values: DirectoryFormValues
  onChange: (next: DirectoryFormValues) => void
}

const SECURITY_WARNINGS = {
  none: '보안 연결 없음: 비밀번호가 암호화되지 않은 채 전송됩니다. 신뢰하는 내부망에서만 쓰세요.',
  ssl: 'SSL: 연결은 암호화되지만 서버 인증서를 검증하지 않습니다.',
  starttls: 'StartTLS: 연결은 암호화되지만 서버 인증서를 검증하지 않습니다.',
} as const

/** AD 서버 설정 입력 칸 7개. 최초 설정 마법사와 설정 화면이 함께 쓴다(상태는 호출한 화면이 쥔다). */
export function DirectoryFields({ values, onChange }: Props) {
  const { saved } = values
  const typed = values.bindPassword.trim() !== ''
  const patch = (change: Partial<DirectoryFormValues>) => onChange({ ...values, ...change })
  return (
    <>
      <TextField
        autoComplete="off"
        label="호스트"
        name="host"
        required
        value={values.host}
        onChange={(host) => onChange(changeEndpointField(values, 'host', host))}
      />
      <TextField
        autoComplete="off"
        label="포트"
        name="port"
        type="number"
        required
        value={values.port}
        onChange={(port) => onChange(changeEndpointField(values, 'port', port))}
      />
      <div>
        <SelectField
          label="보안 연결"
          name="security"
          required
          value={values.security}
          onChange={(security) => onChange(changeEndpointField(values, 'security', security))}
        >
          <option value="none">없음</option>
          <option value="ssl">SSL</option>
          <option value="starttls">StartTLS</option>
        </SelectField>
        <p className="hint">{SECURITY_WARNINGS[values.security]}</p>
      </div>
      <TextField
        autoComplete="off"
        label="바인드 계정"
        name="bind_account"
        required
        value={values.bindAccount}
        onChange={(bindAccount) => onChange(changeEndpointField(values, 'bindAccount', bindAccount))}
      />
      <div>
        <label className="field">
          <span>바인드 비밀번호</span>
          <input
            name="bind_password"
            type="password"
            autoComplete="new-password"
            value={values.bindPassword}
            onFocus={() => onChange(focusBindPassword(values))}
            onBlur={() => onChange(blurBindPassword(values))}
            onChange={(e) => onChange(typeBindPassword(values, e.target.value))}
          />
        </label>
        {values.retypeBindPassword && !typed && (
          <p className="hint">서버나 바인드 계정을 바꿨으므로 비밀번호를 다시 입력하세요.</p>
        )}
        {saved?.unreadable && !typed && (
          <p className="hint">저장된 바인드 비밀번호를 읽을 수 없습니다. 다시 입력하세요.</p>
        )}
        {saved !== null && !saved.unreadable && !values.retypeBindPassword && (
          <p className="hint">그대로 두면 저장된 비밀번호를 씁니다.</p>
        )}
      </div>
      <TextField
        autoComplete="off"
        label="사용자 검색 필터"
        name="user_filter"
        required
        value={values.userFilter}
        onChange={(userFilter) => patch({ userFilter })}
      />
      <TextField
        autoComplete="off"
        label="연결 제한 시간(초)"
        name="connect_timeout_seconds"
        type="number"
        required
        value={values.connectTimeoutSeconds}
        onChange={(connectTimeoutSeconds) => patch({ connectTimeoutSeconds })}
      />
    </>
  )
}
