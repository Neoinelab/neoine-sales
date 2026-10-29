import type { DirectorySettings, DirectorySettingsInput } from '../shared/model/types'

/** 바인드 비밀번호 더미 값(실제 비밀번호가 아니다). 화면·요청·응답에 어떻게 다뤄지는지 검사하는 데 쓴다. */
export const BIND_PASSWORD = 'Svc-Dummy-pw-1!'

/** 게이트웨이에 넘기는 AD 설정 입력 7개(비밀번호 포함). */
export const DIRECTORY_INPUT: DirectorySettingsInput = {
  host: 'dc1.corp.test',
  port: 636,
  security: 'ssl',
  bindAccount: 'CORP\\svc-sales',
  bindPassword: BIND_PASSWORD,
  userFilter: '(sAMAccountName={login_id})',
  connectTimeoutSeconds: 5,
}

/** 서버가 돌려주는 저장된 AD 설정(비밀번호는 없고 저장 상태만 있다). */
export const DIRECTORY_SAVED: DirectorySettings = {
  host: 'dc1.corp.test',
  port: 636,
  security: 'ssl',
  bindAccount: 'CORP\\svc-sales',
  bindCredentialStatus: 'ok',
  userFilter: '(sAMAccountName={login_id})',
  connectTimeoutSeconds: 5,
  baseDn: 'dc=corp,dc=test',
  revision: 3,
  updatedAt: '2026-10-15T09:00:00+09:00',
  updatedBy: null,
}
