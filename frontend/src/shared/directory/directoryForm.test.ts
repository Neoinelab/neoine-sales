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
  it('starts with SSL on 636, the default filter and a 5 second connect timeout', () => {
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

  it('treats a new form as one where the bind password still has to be typed', () => {
    expect(DEFAULT_DIRECTORY_FORM.bindPasswordTouched).toBe(true)
    expect(DEFAULT_DIRECTORY_FORM.bindPassword).toBe('')
  })

  it('knows the default port of each security mode', () => {
    expect(DEFAULT_PORTS).toEqual({ none: 389, ssl: 636, starttls: 389 })
  })

  it('uses a fixed eight-asterisk mask', () => {
    expect(BIND_PASSWORD_MASK).toBe('********')
  })
})

describe('changeSecurity (AC8: 방식을 바꾸면 기본 포트도 바뀐다)', () => {
  it.each([
    ['ssl', '636', 'none', '389'],
    ['ssl', '636', 'starttls', '389'],
    ['none', '389', 'ssl', '636'],
    ['starttls', '389', 'ssl', '636'],
    ['none', '389', 'starttls', '389'],
  ] as const)('from %s:%s to %s switches the port to %s', (from, port, to, expected) => {
    const values = { ...DEFAULT_DIRECTORY_FORM, security: from, port }

    const next = changeSecurity(values, to)

    expect(next.security).toBe(to)
    expect(next.port).toBe(expected)
  })

  it('fills the new default port when the port is empty', () => {
    const next = changeSecurity({ ...DEFAULT_DIRECTORY_FORM, port: '' }, 'none')

    expect(next.port).toBe('389')
  })

  it.each(['none', 'starttls', 'ssl'] as const)('keeps a port the user typed when switching to %s', (to) => {
    const next = changeSecurity({ ...DEFAULT_DIRECTORY_FORM, security: 'ssl', port: '3269' }, to)

    expect(next.port).toBe('3269')
    expect(next.security).toBe(to)
  })

  it('does not change anything else and does not mutate its input', () => {
    const values = { ...DEFAULT_DIRECTORY_FORM, host: 'dc1.corp.test', bindAccount: 'svc' }
    const before = { ...values }

    const next = changeSecurity(values, 'none')

    expect(values).toEqual(before)
    expect(next.host).toBe('dc1.corp.test')
    expect(next.bindAccount).toBe('svc')
    expect(next.userFilter).toBe(values.userFilter)
  })
})

describe('formFromDirectory (AC4: 저장된 비밀번호는 마스크로만 보인다)', () => {
  it('shows the mask without marking the password as edited when the credential is stored', () => {
    expect(savedForm()).toMatchObject({
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

  it('asks for a new password (empty field) when the stored one cannot be read', () => {
    const form = formFromDirectory({ ...DIRECTORY_SAVED, bindCredentialStatus: 'unreadable' })

    expect(form.bindPassword).toBe('')
    expect(form.bindPasswordTouched).toBe(true)
  })

  it('never carries the Base DN into the editable values (it is read-only)', () => {
    expect(Object.values(savedForm())).not.toContain('dc=corp,dc=test')
    expect('baseDn' in savedForm()).toBe(false)
  })
})

describe('inputFromForm', () => {
  it('sends null as the bind password while the mask is untouched', () => {
    expect(inputFromForm(savedForm())).toEqual({ ...DIRECTORY_INPUT, bindPassword: null })
  })

  it('sends what was typed once the password is edited', () => {
    const edited = { ...savedForm(), bindPassword: 'New-pw-2!', bindPasswordTouched: true }

    expect(inputFromForm(edited).bindPassword).toBe('New-pw-2!')
  })

  it('sends the mask text as a real password when the user typed it themselves', () => {
    const typed = { ...savedForm(), bindPassword: BIND_PASSWORD_MASK, bindPasswordTouched: true }

    expect(inputFromForm(typed).bindPassword).toBe(BIND_PASSWORD_MASK)
  })

  it('never decides by comparing the text with the mask', () => {
    const edited = { ...savedForm(), bindPassword: 'x', bindPasswordTouched: false }

    expect(inputFromForm(edited).bindPassword).toBeNull()
  })

  it('parses the port and the timeout into numbers', () => {
    const input = inputFromForm({ ...DEFAULT_DIRECTORY_FORM, port: '3269', connectTimeoutSeconds: '8' })

    expect(input.port).toBe(3269)
    expect(input.connectTimeoutSeconds).toBe(8)
  })

  it('has exactly the seven input fields', () => {
    expect(Object.keys(inputFromForm(savedForm())).sort()).toEqual(
      ['bindAccount', 'bindPassword', 'connectTimeoutSeconds', 'host', 'port', 'security', 'userFilter'].sort(),
    )
  })

  it('round-trips a saved setting through the form (without touching the password)', () => {
    expect(inputFromForm(formFromDirectory(DIRECTORY_SAVED))).toEqual({ ...DIRECTORY_INPUT, bindPassword: null })
  })
})

describe('changeEndpointField (AC4: 서버·계정을 바꾸면 비밀번호를 다시 입력한다)', () => {
  it.each([
    ['host', 'dc9.corp.test'],
    ['port', '3269'],
    ['security', 'starttls'],
    ['bindAccount', 'CORP\\other'],
  ] as const)('clears the mask and asks to retype when %s changes', (field, value) => {
    const next = changeEndpointField(savedForm(), field, value)

    expect(next[field]).toBe(value)
    expect(next.bindPassword).toBe('')
    expect(next.bindPasswordTouched).toBe(true)
    expect(next.retypeBindPassword).toBe(true)
  })

  it('does not touch the password when the value is the same as the saved one', () => {
    const next = changeEndpointField(savedForm(), 'host', 'dc1.corp.test')

    expect(next.bindPassword).toBe(BIND_PASSWORD_MASK)
    expect(next.bindPasswordTouched).toBe(false)
    expect(next.retypeBindPassword).toBe(false)
  })

  it('keeps a password the user already typed', () => {
    const typed = { ...savedForm(), bindPassword: 'New-pw-2!', bindPasswordTouched: true }

    const next = changeEndpointField(typed, 'host', 'dc9.corp.test')

    expect(next.bindPassword).toBe('New-pw-2!')
    expect(next.retypeBindPassword).toBe(false)
  })

  it('does nothing special for a form without a saved setting (setup, first registration)', () => {
    const typed = { ...DEFAULT_DIRECTORY_FORM, bindPassword: 'typed-pw-1!' }

    const next = changeEndpointField(typed, 'host', 'dc9.corp.test')

    expect(next.host).toBe('dc9.corp.test')
    expect(next.bindPassword).toBe('typed-pw-1!')
    expect(next.retypeBindPassword).toBe(false)
  })

  it('switches the default port together with the security mode', () => {
    expect(changeEndpointField(savedForm(), 'security', 'starttls').port).toBe('389')
  })

  it('does not mutate its input', () => {
    const before = { ...savedForm() }

    changeEndpointField(savedForm(), 'host', 'dc9.corp.test')

    expect(savedForm()).toEqual(before)
  })
})

describe('validateForm (AC4)', () => {
  it.each(['setup', 'settings'] as const)('asks for the bind password when it is empty (%s)', (mode) => {
    expect(validateForm({ ...DEFAULT_DIRECTORY_FORM, bindPassword: '' }, mode)).toBe(REQUIRED)
  })

  it('treats a blank password as empty', () => {
    expect(validateForm({ ...DEFAULT_DIRECTORY_FORM, bindPassword: '   ' }, 'setup')).toBe(REQUIRED)
  })

  it('asks again when the stored password is unreadable and nothing was typed', () => {
    const form = formFromDirectory({ ...DIRECTORY_SAVED, bindCredentialStatus: 'unreadable' })

    expect(validateForm(form, 'settings')).toBe(REQUIRED)
  })

  it('asks again after the endpoint changed and the field was cleared', () => {
    const changed = changeEndpointField(savedForm(), 'host', 'dc9.corp.test')

    expect(validateForm(changed, 'settings')).toBe(REQUIRED)
  })

  it('accepts the untouched mask (the stored password is kept)', () => {
    expect(validateForm(savedForm(), 'settings')).toBeNull()
  })

  it('accepts a typed password', () => {
    expect(validateForm({ ...DEFAULT_DIRECTORY_FORM, bindPassword: 'pw-1' }, 'setup')).toBeNull()
  })
})
