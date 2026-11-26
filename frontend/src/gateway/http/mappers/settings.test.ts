import { describe, expect, it } from 'vitest'
import type { Schemas } from '../../../shared/api/client'
import { DIRECTORY_INPUT } from '../../../test/directoryFixtures'
import { toDirectoryRequest, toDirectorySettings } from './settings'

describe('toDirectoryRequest', () => {
  // 입력 7칸을 snake_case 요청 본문으로 바꾼다.
  // 테스트 코드: IN-082
  it('converts the seven fields to the snake_case request', () => {
    // when: 요청 본문으로 바꾼다 (전제: AD 설정 입력 7칸)
    const result = toDirectoryRequest(DIRECTORY_INPUT)
    // then: 7개 키가 snake_case로 담긴다
    expect(result).toEqual({
      host: 'dc1.corp.test',
      port: 636,
      security: 'ssl',
      user_filter: '(sAMAccountName={login_id})',
      connect_timeout_seconds: 5,
    })
  })

  // 저장된 비밀번호를 유지하면 bind_password 키를 빼고 보낸다.
  // 테스트 코드: IN-082
  it('leaves the bind_password key out when the stored password is kept', () => {
    // when: 요청 본문으로 바꾼다 (전제: 바인드 비밀번호 null인 입력)
    const request = toDirectoryRequest(DIRECTORY_INPUT)

    // then: bind_password 키가 없고 나머지 6개만 있다
    expect(request).not.toHaveProperty('bind_password')
    expect(Object.keys(request).sort()).toEqual(
      ['connect_timeout_seconds', 'host', 'port', 'security', 'user_filter'].sort(),
    )
  })

  // 폐지된 필드는 절대 보내지 않는다.
  // 테스트 코드: IN-082
  it('never sends the removed fields', () => {
    // when: 요청 본문으로 바꾼다 (전제: AD 설정 입력)
    const request = toDirectoryRequest(DIRECTORY_INPUT)

    // then: 폐지된 키가 없다
    for (const removed of ['server_urls', 'use_starttls', 'ca_cert_pem', 'bind_template', 'base_dn', 'display_name_attribute', 'email_attribute', 'receive_timeout_seconds']) {
      expect(request).not.toHaveProperty(removed)
    }
  })

  // 보안 연결 방식(none·ssl·starttls)은 그대로 요청에 담는다.
  it.each(['none', 'ssl', 'starttls'] as const)('passes the %s security mode through', (security) => {
    // when: 보안 연결 방식을 바꿔 요청 본문으로 바꾼다
    const result = toDirectoryRequest({ ...DIRECTORY_INPUT, security })
    // then: security 값이 그대로 담긴다
    expect(result).toMatchObject({ security })
  })
})

describe('toDirectorySettings', () => {
  const ROW = {
    host: 'dc1.corp.test',
    port: 389,
    security: 'starttls',
    bind_credential_status: 'unreadable',
    user_filter: '(x={login_id})',
    connect_timeout_seconds: 9,
    base_dn: 'ou=staff,dc=corp,dc=test',
    revision: 2,
    updated_at: '2026-10-15T10:00:00+09:00',
    updated_by: null,
  } as unknown as Schemas['DirectorySettingsResponse']

  // 응답을 camelCase로 바꾸고 읽기 전용 Base DN을 유지한다.
  // 테스트 코드: IN-080
  it('converts the response to camelCase and keeps the read-only Base DN', () => {
    // when: 화면 값으로 바꾼다 (전제: 서버의 AD 설정 응답)
    const result = toDirectorySettings(ROW)
    // then: camelCase 값과 baseDn이 있다
    expect(result).toEqual({
      host: 'dc1.corp.test',
      port: 389,
      security: 'starttls',
      userFilter: '(x={login_id})',
      connectTimeoutSeconds: 9,
      baseDn: 'ou=staff,dc=corp,dc=test',
      revision: 2,
      updatedAt: '2026-10-15T10:00:00+09:00',
      updatedBy: null,
    })
  })
})
