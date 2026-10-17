import { describe, expect, it } from 'vitest'
import { BLOCKED_EXTENSIONS } from './constants'
import { extensionOf, validateUpload } from './fileRules'

const MB = 1024 * 1024

const BLOCKED_24 = [
  ...['exe', 'msi', 'bat', 'cmd', 'sh', 'ps1', 'jar', 'com', 'scr', 'dmg', 'pkg', 'deb', 'rpm'],
  ...['vbs', 'vbe', 'wsf', 'wsh', 'hta', 'cpl', 'msp', 'mst', 'apk', 'appimage', 'run'],
]

describe('extensionOf', () => {
  it('마지막 확장자를 소문자로 돌려준다', () => {
    expect(extensionOf('run.EXE')).toBe('exe')
    expect(extensionOf('a.tar.gz')).toBe('gz')
    expect(extensionOf('.bashrc')).toBe('')
    expect(extensionOf('noext')).toBe('')
    expect(extensionOf('trailing.')).toBe('')
  })

  // 서버 `extension_of`와 같은 표(backend tests/unit/domain/test_attachment_values.py). 끝의 공백·점을 걷어 낸 뒤 마지막 확장자.
  it.each([
    ['a.tar.gz', 'gz'],
    ['a.exe.txt', 'txt'],
    ['한글.PDF', 'pdf'],
    ['.exe', ''],
    ['a.', ''],
    ['README', ''],
    ['', ''],
    ['setup.exe ', 'exe'],
    ['setup.exe.', 'exe'],
    ['setup.EXE . ', 'exe'],
    ['report.pdf ', 'pdf'],
    ['a. .', ''],
    ['.exe.', ''],
  ])('extensionOf(%j) is %j like the server', (name, expected) => {
    expect(extensionOf(name)).toBe(expected)
  })

  it.each(['setup.exe\u3000', 'setup.exe\u00a0', 'setup.exe\u2003', 'setup.exe\t', 'setup.exe .', 'setup.exe.\u3000 .'])(
    'extensionOf ignores trailing unicode whitespace and dots: %j',
    (name) => {
      expect(extensionOf(name)).toBe('exe')
    },
  )
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
  })

  it('T-FILE-02b blocks exactly the 24 decided extensions, each with its own lowercase name in the message', () => {
    expect(BLOCKED_EXTENSIONS).toHaveLength(24)
    for (const ext of BLOCKED_24) {
      expect(validateUpload({ name: `x.${ext.toUpperCase()}`, size: 10 }, '')).toEqual({
        code: 'blocked-extension',
        message: `실행·설치 파일(.${ext})은 업로드할 수 없습니다.`,
      })
    }
    expect([...BLOCKED_EXTENSIONS].sort()).toEqual([...BLOCKED_24].sort())
  })

  it.each(['zip', 'gz', 'pdf', 'txt', 'docx', 'exe2'])('T-FILE-02c does not block .%s', (ext) => {
    expect(validateUpload({ name: `x.${ext}`, size: 10 }, '')).toBeNull()
  })

  it.each(['setup.exe ', 'setup.exe.', 'setup.exe\u3000', 'setup.exe\u00a0', 'setup.EXE . ', 'setup.exe.\u3000 .'])(
    'T-FILE-02d blocks %j (trailing whitespace and dots are stripped before the extension check)',
    (name) => {
      expect(validateUpload({ name, size: 10 }, '')).toEqual({
        code: 'blocked-extension',
        message: '실행·설치 파일(.exe)은 업로드할 수 없습니다.',
      })
    },
  )

  it('T-FILE-02e allows a dot file named after a blocked extension (.exe has no extension)', () => {
    expect(validateUpload({ name: '.exe', size: 10 }, '')).toBeNull()
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

  it('T-FILE-05b 설명은 앞뒤 공백을 자른 뒤 센다', () => {
    expect(validateUpload(ok, `  ${'a'.repeat(100)}  `)).toBeNull()
    expect(validateUpload(ok, `\n\t${'가'.repeat(101)} `)?.code).toBe('description-too-long')
    expect(validateUpload(ok, ' \t ')).toBeNull()
  })

  it('T-FILE-05c 설명 길이는 코드 포인트로 센다(이모지 하나가 1자)', () => {
    expect(validateUpload(ok, '😀'.repeat(100))).toBeNull()
    expect(validateUpload(ok, '😀'.repeat(101))).toEqual({
      code: 'description-too-long',
      message: '설명은 100자 이내로 입력하세요.',
    })
  })

  it('정상 파일은 오류가 없다', () => {
    expect(validateUpload(ok, '')).toBeNull()
  })
})

describe('validateUpload: 파일 이름 규칙 (서버 FileName.parse와 같은 입력)', () => {
  const invalid = { code: 'invalid-name', message: '사용할 수 없는 파일 이름입니다.' }
  const check = (name: string) => validateUpload({ name, size: 10 }, '')
  const BIDI = ['\u202a', '\u202b', '\u202c', '\u202d', '\u202e', '\u2066', '\u2067', '\u2068', '\u2069', '\u200e', '\u200f', '\u061c']

  it.each(['', '.', '..', 'a/b.pdf', 'a\\b.pdf', '/', '../x.pdf'])('T-FILE-NAME-01 rejects %j', (name) => {
    expect(check(name)).toEqual(invalid)
  })

  it.each(['a\u0000b.pdf', 'a\tb.pdf', 'a\nb.pdf', 'a\u001fb.pdf', 'a\u007fb.pdf'])('T-FILE-NAME-02 rejects the control character in %j', (name) => {
    expect(check(name)).toEqual(invalid)
  })

  it.each(BIDI)('T-FILE-NAME-03 rejects the bidirectional format character U+%s', (mark) => {
    expect(check(`견적서${mark}fdp.pdf`)).toEqual(invalid)
  })

  // 2026-10-17 사용자 결정: 서식 문자(Cf) 전체를 이름 어디에서든 거부한다(서버 FileName.parse와 같다).
  const CF = ['\ufeff', '\u200b', '\u200c', '\u200d', '\u2060', '\u00ad']

  it.each(CF)('T-FILE-NAME-08 rejects the format character U+%s at the start, middle and end', (mark) => {
    expect(check(`${mark}report.pdf`)).toEqual(invalid)
    expect(check(`re${mark}port.pdf`)).toEqual(invalid)
    expect(check(`report.pdf${mark}`)).toEqual(invalid)
  })

  it('T-FILE-NAME-09 rejects the executable disguised by a trailing ZWSP as an invalid name', () => {
    expect(check('setup.exe\u200b')).toEqual(invalid)
  })

  it('T-FILE-NAME-09 still refuses setup.exe followed by a BOM (as a blocked extension or an invalid name)', () => {
    expect(check('setup.exe\ufeff')).not.toBeNull()
  })

  it('T-FILE-NAME-10 rejects a ZWJ emoji sequence and accepts plain emoji and Korean', () => {
    expect(check('\u{1F468}\u200d\u{1F469}\u200d\u{1F467}.png')).toEqual(invalid)
    expect(check('\u{1F600}.png')).toBeNull()
    expect(check('\u2764\ufe0f.png')).toBeNull()
    expect(check('한글👍.pdf')).toBeNull()
  })

  it('T-FILE-NAME-04 allows 255 code points and rejects 256 (an emoji counts once)', () => {
    expect(check('a'.repeat(255))).toBeNull()
    expect(check('a'.repeat(256))).toEqual(invalid)
    expect(check('😀'.repeat(255))).toBeNull()
    expect(check('😀'.repeat(256))).toEqual(invalid)
  })

  it('T-FILE-NAME-05 measures the length after NFC normalisation', () => {
    const decomposed = 'e\u0301'
    expect(check(decomposed.repeat(200))).toBeNull()
    expect(check(decomposed.repeat(255))).toBeNull()
    expect(check(decomposed.repeat(256))).toEqual(invalid)
  })

  it('T-FILE-NAME-06 keeps leading and trailing spaces, dots inside and unusual but legal characters', () => {
    for (const name of [' a.pdf', 'a.pdf ', '.bashrc', 'a..b', '견적서 (최종) #1 & 2%.pdf', 'a'.repeat(250) + '.pdf']) {
      expect(check(name)).toBeNull()
    }
  })

  it('T-FILE-NAME-07 judges the blocked extension before the name (the server order)', () => {
    expect(check('a/b.exe')?.code).toBe('blocked-extension')
    expect(check('a/b.pdf')?.code).toBe('invalid-name')
  })
})

describe('validateUpload: 판정 순서 (파일 없음 > 설명 > 크기 > 확장자 > 이름)', () => {
  const long = 'x'.repeat(101)

  it('checks the missing file first', () => {
    expect(validateUpload(null, long)?.code).toBe('no-file')
  })

  it('checks the description before the size', () => {
    expect(validateUpload({ name: 'a.exe', size: 100 * MB + 1 }, long)?.code).toBe('description-too-long')
  })

  it('checks the size before the extension', () => {
    expect(validateUpload({ name: 'a.exe', size: 100 * MB + 1 }, '')?.code).toBe('too-large')
  })

  it('checks the extension before the name', () => {
    expect(validateUpload({ name: 'a/b.exe', size: 1 }, '')?.code).toBe('blocked-extension')
  })

  it('allows a zero byte file', () => {
    expect(validateUpload({ name: 'empty.txt', size: 0 }, '')).toBeNull()
  })
})
