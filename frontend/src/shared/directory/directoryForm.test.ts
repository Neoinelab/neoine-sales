import { describe, expect, it } from 'vitest'
import { DIRECTORY_INPUT, DIRECTORY_SAVED } from '../../test/directoryFixtures'
import {
  BIND_PASSWORD_MASK,
  DEFAULT_DIRECTORY_FORM,
  DEFAULT_PORTS,
  changeEndpointField,
  changeSecurity,
  formFromDirectory,
  inputFromForm,
  validateForm,
} from './directoryForm'

const REQUIRED = '바인드 비밀번호를 입력하세요'
/** 저장된 설정으로 채운 설정 화면 폼(테스트마다 새로 만든다). */
const savedForm = () => formFromDirectory(DIRECTORY_SAVED)

describe('기본값과 상수', () => {
  it('기본 폼은 SSL 636 포트, 기본 필터, 연결 제한 5초로 시작한다', () => {
    // when·then: 기본 폼의 값이 기본 포트·보안 연결·필터·제한 시간과 같다
    expect(DEFAULT_DIRECTORY_FORM).toMatchObject({
      host: '',
      port: '636',
      security: 'ssl',
      bindAccount: '',
      bindPassword: '',
      userFilter: '(&(objectClass=user)(sAMAccountName={login_id}))',
      connectTimeoutSeconds: '5',
    })
  })

  it('새 폼은 바인드 비밀번호를 직접 입력해야 하는 상태다', () => {
    // when·then: 기본 폼의 비밀번호는 비어 있고 입력한 것으로 표시되어 있다
    expect(DEFAULT_DIRECTORY_FORM.bindPasswordTouched).toBe(true)
    expect(DEFAULT_DIRECTORY_FORM.bindPassword).toBe('')
  })

  it('보안 연결마다 기본 포트를 안다', () => {
    // when·then: 기본 포트 표가 none 389, ssl 636, starttls 389다
    expect(DEFAULT_PORTS).toEqual({ none: 389, ssl: 636, starttls: 389 })
  })

  it('마스크는 고정된 별표 8개다', () => {
    // when·then: 마스크 문자열이 별표 8개다
    expect(BIND_PASSWORD_MASK).toBe('********')
  })
})

describe('changeSecurity: 방식을 바꾸면 기본 포트도 바뀐다', () => {
  it.each([
    ['ssl', '636', 'none', '389'],
    ['ssl', '636', 'starttls', '389'],
    ['none', '389', 'ssl', '636'],
    ['starttls', '389', 'ssl', '636'],
    ['none', '389', 'starttls', '389'],
  ] as const)('%s:%s에서 %s(으)로 바꾸면 포트가 %s(으)로 바뀐다', (from, port, to, expected) => {
    // given: 기본 폼의 보안 연결과 포트가 정해져 있다
    const values = { ...DEFAULT_DIRECTORY_FORM, security: from, port }

    // when: 보안 연결을 바꾼다
    const next = changeSecurity(values, to)

    // then: 보안 연결이 바뀌고 포트가 그 방식의 기본 포트가 된다
    expect(next.security).toBe(to)
    expect(next.port).toBe(expected)
  })

  it('포트가 비어 있으면 새 방식의 기본 포트를 채운다', () => {
    // when: 포트가 빈 폼의 보안 연결을 바꾼다
    const next = changeSecurity({ ...DEFAULT_DIRECTORY_FORM, port: '' }, 'none')

    // then: 포트가 389다
    expect(next.port).toBe('389')
  })

  it.each(['none', 'starttls', 'ssl'] as const)('사용자가 입력한 포트는 %s(으)로 바꿔도 유지한다', (to) => {
    // when: 사용자가 3269를 입력한 폼의 보안 연결을 바꾼다
    const next = changeSecurity({ ...DEFAULT_DIRECTORY_FORM, security: 'ssl', port: '3269' }, to)

    // then: 포트는 3269 그대로이고 보안 연결만 바뀐다
    expect(next.port).toBe('3269')
    expect(next.security).toBe(to)
  })

  it('다른 값은 바꾸지 않고 입력 객체도 변경하지 않는다', () => {
    // given: 호스트·계정을 입력한 폼과 그 복사본이 있다
    const values = { ...DEFAULT_DIRECTORY_FORM, host: 'dc1.corp.test', bindAccount: 'svc' }
    const before = { ...values }

    // when: 보안 연결을 바꾼다
    const next = changeSecurity(values, 'none')

    // then: 원본은 그대로이고 호스트·계정·필터는 유지된다
    expect(values).toEqual(before)
    expect(next.host).toBe('dc1.corp.test')
    expect(next.bindAccount).toBe('svc')
    expect(next.userFilter).toBe(values.userFilter)
  })
})

describe('formFromDirectory: 저장된 비밀번호는 마스크로만 보인다', () => {
  it('저장된 설정이면 마스크를 보이되 비밀번호를 입력한 것으로 표시하지 않는다', () => {
    // when: 저장된 설정으로 폼을 만든다
    const form = savedForm()

    // then: 저장된 값과 마스크를 담고 입력 표시는 꺼져 있다
    expect(form).toMatchObject({
      host: 'dc1.corp.test',
      port: '636',
      security: 'ssl',
      bindAccount: 'CORP\\svc-sales',
      bindPassword: BIND_PASSWORD_MASK,
      bindPasswordTouched: false,
      userFilter: '(sAMAccountName={login_id})',
      connectTimeoutSeconds: '5',
    })
  })

  it('저장된 비밀번호를 읽을 수 없으면 새 비밀번호를 요구한다(빈 칸)', () => {
    // when: 읽을 수 없는 상태의 저장 설정으로 폼을 만든다
    const form = formFromDirectory({ ...DIRECTORY_SAVED, bindCredentialStatus: 'unreadable' })

    // then: 비밀번호 칸이 비고 입력한 것으로 표시된다
    expect(form.bindPassword).toBe('')
    expect(form.bindPasswordTouched).toBe(true)
  })

  it('Base DN은 편집할 값에 싣지 않는다(읽기 전용)', () => {
    // when: 저장된 설정으로 폼을 만든다
    const form = savedForm()

    // then: 폼 값에 Base DN이 없다
    expect(Object.values(form)).not.toContain('dc=corp,dc=test')
    expect('baseDn' in form).toBe(false)
  })
})

describe('inputFromForm', () => {
  it('마스크를 건드리지 않았으면 바인드 비밀번호로 null을 보낸다', () => {
    // when: 저장된 설정으로 만든 폼을 입력 형태로 바꾼다
    const result = inputFromForm(savedForm())

    // then: 바인드 비밀번호가 null이고 나머지 값은 저장된 입력과 같다
    expect(result).toEqual({ ...DIRECTORY_INPUT, bindPassword: null })
  })

  it('비밀번호를 고치면 입력한 값을 보낸다', () => {
    // given: 저장된 설정에서 비밀번호를 고친 폼
    const edited = { ...savedForm(), bindPassword: 'New-pw-2!', bindPasswordTouched: true }

    // when: 비밀번호를 고친 폼을 입력 형태로 바꾼다
    const result = inputFromForm(edited).bindPassword

    // then: 입력한 비밀번호가 담긴다
    expect(result).toBe('New-pw-2!')
  })

  it('사용자가 마스크 문자열을 직접 입력했으면 실제 비밀번호로 보낸다', () => {
    // given: 마스크 문자열을 입력해 편집 표시를 켠 폼
    const typed = { ...savedForm(), bindPassword: BIND_PASSWORD_MASK, bindPasswordTouched: true }

    // when: 마스크와 같은 문자열을 입력한 폼을 입력 형태로 바꾼다
    const result = inputFromForm(typed).bindPassword

    // then: 마스크 문자열이 비밀번호로 담긴다
    expect(result).toBe(BIND_PASSWORD_MASK)
  })

  it('텍스트가 마스크와 같은지로 판단하지 않는다', () => {
    // given: 값 x가 있어도 편집 표시는 꺼진 폼
    const edited = { ...savedForm(), bindPassword: 'x', bindPasswordTouched: false }

    // when: 비밀번호 칸에 값이 있지만 편집 표시가 꺼진 폼을 입력 형태로 바꾼다
    const result = inputFromForm(edited).bindPassword

    // then: 비밀번호가 null이다
    expect(result).toBeNull()
  })

  it('포트와 제한 시간을 숫자로 바꾼다', () => {
    // when: 문자열 포트·제한 시간 폼을 입력 형태로 바꾼다
    const input = inputFromForm({ ...DEFAULT_DIRECTORY_FORM, port: '3269', connectTimeoutSeconds: '8' })

    // then: 포트·제한 시간이 숫자다
    expect(input.port).toBe(3269)
    expect(input.connectTimeoutSeconds).toBe(8)
  })

  it('입력 형태는 정확히 일곱 개 필드다', () => {
    // when: 저장된 설정으로 만든 폼을 입력 형태로 바꾼다
    const result = Object.keys(inputFromForm(savedForm())).sort()

    // then: 키가 host·port·security·bindAccount·bindPassword·userFilter·connectTimeoutSeconds 일곱 개뿐이다
    expect(result).toEqual(
      ['bindAccount', 'bindPassword', 'connectTimeoutSeconds', 'host', 'port', 'security', 'userFilter'].sort(),
    )
  })

  it('저장된 설정은 폼을 거쳐 같은 입력으로 돌아온다(비밀번호는 건드리지 않음)', () => {
    // when: 저장된 설정을 폼으로 만들었다가 입력 형태로 바꾼다
    const result = inputFromForm(formFromDirectory(DIRECTORY_SAVED))

    // then: 저장된 입력과 같고 비밀번호만 null이다
    expect(result).toEqual({ ...DIRECTORY_INPUT, bindPassword: null })
  })
})

describe('changeEndpointField: 서버·계정을 바꾸면 비밀번호를 다시 입력한다', () => {
  it.each([
    ['host', 'dc9.corp.test'],
    ['port', '3269'],
    ['security', 'starttls'],
    ['bindAccount', 'CORP\\other'],
  ] as const)('%s이(가) 바뀌면 마스크를 지우고 다시 입력을 요구한다', (field, value) => {
    // given: 저장된 설정으로 만든 폼
    const saved = savedForm()

    // when: 서버·계정 필드 하나를 바꾼다
    const next = changeEndpointField(saved, field, value)

    // then: 값이 바뀌고 비밀번호가 비며 다시 입력 표시가 켜진다
    expect(next[field]).toBe(value)
    expect(next.bindPassword).toBe('')
    expect(next.bindPasswordTouched).toBe(true)
    expect(next.retypeBindPassword).toBe(true)
  })

  it('저장된 값과 같게 바꾸면 비밀번호를 건드리지 않는다', () => {
    // given: 저장된 설정으로 만든 폼
    const saved = savedForm()

    // when: 호스트를 저장된 값과 같게 바꾼다
    const next = changeEndpointField(saved, 'host', 'dc1.corp.test')

    // then: 마스크와 입력 표시가 그대로다
    expect(next.bindPassword).toBe(BIND_PASSWORD_MASK)
    expect(next.bindPasswordTouched).toBe(false)
    expect(next.retypeBindPassword).toBe(false)
  })

  it('이미 입력한 비밀번호는 유지한다', () => {
    // given: 비밀번호를 직접 입력한 폼
    const typed = { ...savedForm(), bindPassword: 'New-pw-2!', bindPasswordTouched: true }

    // when: 비밀번호를 입력한 뒤 호스트를 바꾼다
    const next = changeEndpointField(typed, 'host', 'dc9.corp.test')

    // then: 입력한 비밀번호가 그대로고 다시 입력 표시는 꺼져 있다
    expect(next.bindPassword).toBe('New-pw-2!')
    expect(next.retypeBindPassword).toBe(false)
  })

  it('저장된 설정이 없는 폼(최초 설정)은 비밀번호를 건드리지 않는다', () => {
    // given: 저장된 설정 없이 비밀번호를 입력한 폼
    const typed = { ...DEFAULT_DIRECTORY_FORM, bindPassword: 'typed-pw-1!' }

    // when: 호스트를 바꾼다
    const next = changeEndpointField(typed, 'host', 'dc9.corp.test')

    // then: 호스트만 바뀌고 입력한 비밀번호는 유지된다
    expect(next.host).toBe('dc9.corp.test')
    expect(next.bindPassword).toBe('typed-pw-1!')
    expect(next.retypeBindPassword).toBe(false)
  })

  it('보안 연결을 바꾸면 기본 포트도 함께 바꾼다', () => {
    // when: 저장된 폼의 보안 연결을 starttls로 바꾼다
    const result = changeEndpointField(savedForm(), 'security', 'starttls').port

    // then: 포트가 389다
    expect(result).toBe('389')
  })

  it('입력 객체를 변경하지 않는다', () => {
    // given: 저장된 설정으로 만든 폼의 복사본이 있다
    const before = { ...savedForm() }

    // when: 호스트를 바꾼다
    changeEndpointField(savedForm(), 'host', 'dc9.corp.test')

    // then: 저장된 폼이 호출 전과 같다
    expect(savedForm()).toEqual(before)
  })
})

describe('validateForm', () => {
  it.each(['setup', 'settings'] as const)('바인드 비밀번호가 비어 있으면 입력을 요구한다 (%s)', (mode) => {
    // when: 비밀번호가 빈 폼을 검증한다
    const result = validateForm({ ...DEFAULT_DIRECTORY_FORM, bindPassword: '' }, mode)

    // then: 비밀번호 입력 요구 문구다
    expect(result).toBe(REQUIRED)
  })

  it('공백만 있는 비밀번호는 빈 것으로 본다', () => {
    // when: 공백 비밀번호 폼을 검증한다
    const result = validateForm({ ...DEFAULT_DIRECTORY_FORM, bindPassword: '   ' }, 'setup')

    // then: 비밀번호 입력 요구 문구다
    expect(result).toBe(REQUIRED)
  })

  it('저장된 비밀번호를 읽을 수 없고 입력도 없으면 다시 요구한다', () => {
    const form = formFromDirectory({ ...DIRECTORY_SAVED, bindCredentialStatus: 'unreadable' })

    // when: 읽을 수 없는 저장 설정으로 만든 폼을 검증한다
    const result = validateForm(form, 'settings')

    // then: 비밀번호 입력 요구 문구다
    expect(result).toBe(REQUIRED)
  })

  it('서버가 바뀌어 칸이 비워졌으면 다시 요구한다', () => {
    // given: 저장된 폼의 호스트를 바꿔 비밀번호 칸이 비워진 상태
    const changed = changeEndpointField(savedForm(), 'host', 'dc9.corp.test')

    // when: 호스트를 바꿔 비워진 폼을 검증한다
    const result = validateForm(changed, 'settings')

    // then: 비밀번호 입력 요구 문구다
    expect(result).toBe(REQUIRED)
  })

  it('건드리지 않은 마스크는 받아들인다(저장된 비밀번호 유지)', () => {
    // when: 저장된 폼을 검증한다
    const result = validateForm(savedForm(), 'settings')

    // then: 오류가 없다(null)다
    expect(result).toBeNull()
  })

  it('입력한 비밀번호는 받아들인다', () => {
    // when: 비밀번호를 입력한 폼을 검증한다
    const result = validateForm({ ...DEFAULT_DIRECTORY_FORM, bindPassword: 'pw-1' }, 'setup')

    // then: 오류가 없다(null)다
    expect(result).toBeNull()
  })
})
