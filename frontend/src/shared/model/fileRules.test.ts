import { describe, expect, it } from 'vitest'
import { extensionOf, validateUpload } from './fileRules'

const MB = 1024 * 1024

describe('extensionOf', () => {
  it('마지막 확장자를 소문자로 돌려준다', () => {
    expect(extensionOf('run.EXE')).toBe('exe')
    expect(extensionOf('a.tar.gz')).toBe('gz')
    expect(extensionOf('.bashrc')).toBe('')
    expect(extensionOf('noext')).toBe('')
    expect(extensionOf('trailing.')).toBe('')
  })
})

describe('validateUpload', () => {
  const ok = { name: '견적서.pdf', size: 1000 }

  it('T-FILE-01 파일이 없으면 거부한다', () => {
    expect(validateUpload(null, '')).toEqual({ code: 'no-file', message: '업로드할 파일을 선택하세요.' })
  })

  it('T-FILE-02 차단 확장자는 대소문자와 상관없이 거부하고 확장자를 표시한다', () => {
    expect(validateUpload({ name: 'setup.EXE', size: 10 }, '')).toEqual({
      code: 'blocked-extension',
      message: '실행·설치 파일(.exe)은 업로드할 수 없습니다.',
    })
    for (const ext of ['msi', 'bat', 'cmd', 'sh', 'ps1', 'jar', 'com', 'scr', 'dmg', 'pkg', 'deb', 'rpm']) {
      expect(validateUpload({ name: `x.${ext}`, size: 10 }, '')?.code).toBe('blocked-extension')
    }
  })

  it('T-FILE-03 a.tar.gz는 허용하고 마지막 확장자만 본다', () => {
    expect(validateUpload({ name: 'a.tar.gz', size: 10 }, '')).toBeNull()
    expect(validateUpload({ name: 'a.exe.txt', size: 10 }, '')).toBeNull()
    expect(validateUpload({ name: 'a.txt.exe', size: 10 }, '')?.code).toBe('blocked-extension')
  })

  it('T-FILE-04 100MB는 허용하고 1바이트 초과는 거부한다', () => {
    expect(validateUpload({ name: 'big.bin', size: 100 * MB }, '')).toBeNull()
    expect(validateUpload({ name: 'big.bin', size: 100 * MB + 1 }, '')).toEqual({
      code: 'too-large',
      message: '파일 크기가 100MB를 초과합니다. (최대 100MB)',
    })
  })

  it('T-FILE-05 설명은 100자까지 허용한다', () => {
    expect(validateUpload(ok, 'a'.repeat(100))).toBeNull()
    expect(validateUpload(ok, 'a'.repeat(101))).toEqual({
      code: 'description-too-long',
      message: '설명은 100자 이내로 입력하세요.',
    })
  })

  it('정상 파일은 오류가 없다', () => {
    expect(validateUpload(ok, '')).toBeNull()
  })
})
