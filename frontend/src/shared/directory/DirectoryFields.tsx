import { CheckboxField, TextArea, TextField } from '../ui/fields'
import type { DirectoryFormValues } from './directoryForm'

interface Props {
  values: DirectoryFormValues
  onChange: (patch: Partial<DirectoryFormValues>) => void
}

/** AD 서버 설정 입력 칸 묶음. 최초 설정 마법사와 설정 화면이 함께 쓴다. */
export function DirectoryFields({ values, onChange }: Props) {
  return (
    <>
      <TextArea
        label="서버 URL(한 줄에 하나)"
        name="server_urls"
        required
        value={values.serverUrls}
        onChange={(serverUrls) => onChange({ serverUrls })}
      />
      <CheckboxField
        label="StartTLS 사용"
        name="use_starttls"
        checked={values.useStarttls}
        onChange={(useStarttls) => onChange({ useStarttls })}
      />
      <TextArea
        label="CA 인증서(PEM)"
        name="ca_cert_pem"
        value={values.caCertPem}
        onChange={(caCertPem) => onChange({ caCertPem })}
      />
      <TextField
        autoComplete="off"
        label="바인드 템플릿"
        name="bind_template"
        required
        value={values.bindTemplate}
        onChange={(bindTemplate) => onChange({ bindTemplate })}
      />
      <TextField autoComplete="off" label="Base DN" name="base_dn" required value={values.baseDn} onChange={(baseDn) => onChange({ baseDn })} />
      <TextField
        autoComplete="off"
        label="사용자 검색 필터"
        name="user_filter"
        required
        value={values.userFilter}
        onChange={(userFilter) => onChange({ userFilter })}
      />
      <TextField
        autoComplete="off"
        label="표시 이름 속성"
        name="display_name_attribute"
        required
        value={values.displayNameAttribute}
        onChange={(displayNameAttribute) => onChange({ displayNameAttribute })}
      />
      <TextField
        autoComplete="off"
        label="이메일 속성"
        name="email_attribute"
        required
        value={values.emailAttribute}
        onChange={(emailAttribute) => onChange({ emailAttribute })}
      />
      <TextField
        autoComplete="off"
        label="연결 제한 시간(초)"
        name="connect_timeout_seconds"
        type="number"
        required
        value={values.connectTimeoutSeconds}
        onChange={(connectTimeoutSeconds) => onChange({ connectTimeoutSeconds })}
      />
      <TextField
        autoComplete="off"
        label="응답 제한 시간(초)"
        name="receive_timeout_seconds"
        type="number"
        required
        value={values.receiveTimeoutSeconds}
        onChange={(receiveTimeoutSeconds) => onChange({ receiveTimeoutSeconds })}
      />
    </>
  )
}
