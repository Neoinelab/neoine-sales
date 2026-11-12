import { describe, expect, it } from 'vitest'
import { BLOCKED_EXTENSIONS } from './constants'
import { extensionOf, validateUpload } from './fileRules'

const MB = 1024 * 1024

const BLOCKED_24 = [
  ...['exe', 'msi', 'bat', 'cmd', 'sh', 'ps1', 'jar', 'com', 'scr', 'dmg', 'pkg', 'deb', 'rpm'],
  ...['vbs', 'vbe', 'wsf', 'wsh', 'hta', 'cpl', 'msp', 'mst', 'apk', 'appimage', 'run'],
]

describe('extensionOf', () => {
  // 테스트 코드: AT-044
  it('마지막 확장자를 소문자로 돌려준다', () => {
    // when·then: 여러 이름의 확장자를 읽으면 마지막 확장자가 소문자로 나온다
    expect(extensionOf('run.EXE')).toBe('exe')
    expect(extensionOf('a.tar.gz')).toBe('gz')
    expect(extensionOf('.bashrc')).toBe('')
    expect(extensionOf('noext')).toBe('')
    expect(extensionOf('trailing.')).toBe('')
  })

  // 서버 `extension_of`와 같은 표(backend tests/unit/domain/test_attachment_values.py). 끝의 공백·점을 걷어 낸 뒤 마지막 확장자.
  // 테스트 코드: AT-044
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
  ])('확장자 판정은 서버와 같은 표를 따른다(%j는 %j)', (name, expected) => {
    // when: 이름의 확장자를 읽는다
    const actual = extensionOf(name)

    // then: 서버 `extension_of`와 같은 값이다
    expect(actual).toBe(expected)
  })

  // 테스트 코드: AT-044
  it.each(['setup.exe\u3000', 'setup.exe\u00a0', 'setup.exe\u2003', 'setup.exe\t', 'setup.exe .', 'setup.exe.\u3000 .'])(
    '끝의 유니코드 공백·점은 무시하고 확장자를 읽는다: %j',
    (name) => {
      // when: 끝에 공백·점이 붙은 이름의 확장자를 읽는다
      const actual = extensionOf(name)

      // then: 확장자는 "exe"다
      expect(actual).toBe('exe')
    },
  )
})

describe('validateUpload', () => {
  const ok = { name: '견적서.pdf', size: 1000 }

  // 테스트 코드: AT-044
  it('파일이 없으면 거부한다', () => {
    // when: 파일 없이 검증한다
    const actual = validateUpload(null, '')

    // then: "no-file" 오류와 문구가 나온다
    expect(actual).toEqual({ code: 'no-file', message: '업로드할 파일을 선택하세요.' })
  })

  // 테스트 코드: AT-044
  it('차단 확장자는 대소문자와 상관없이 거부하고 확장자를 표시한다', () => {
    // when: 대문자 확장자 파일을 검증한다
    const actual = validateUpload({ name: 'setup.EXE', size: 10 }, '')

    // then: 차단 오류에 소문자 확장자가 든다
    expect(actual).toEqual({
      code: 'blocked-extension',
      message: '실행·설치 파일(.exe)은 업로드할 수 없습니다.',
    })
  })

  // 테스트 코드: AT-044
  it('정해진 24개 확장자를 모두 막고 문구에 각자의 소문자 확장자를 담는다', () => {
    // when·then: 24개 확장자를 각각 검증하면 모두 차단 오류이고 목록이 24개 집합과 같다
    expect(BLOCKED_EXTENSIONS).toHaveLength(24)
    for (const ext of BLOCKED_24) {
      expect(validateUpload({ name: `x.${ext.toUpperCase()}`, size: 10 }, '')).toEqual({
        code: 'blocked-extension',
        message: `실행·설치 파일(.${ext})은 업로드할 수 없습니다.`,
      })
    }
    expect([...BLOCKED_EXTENSIONS].sort()).toEqual([...BLOCKED_24].sort())
  })

  // 테스트 코드: AT-044
  it.each(['zip', 'gz', 'pdf', 'txt', 'docx', 'exe2'])('일반·압축 확장자 .%s는 막지 않는다', (ext) => {
    // when: 일반 확장자 파일을 검증한다
    const actual = validateUpload({ name: `x.${ext}`, size: 10 }, '')

    // then: 오류가 없다
    expect(actual).toBeNull()
  })

  // 테스트 코드: AT-044
  it.each(['setup.exe ', 'setup.exe.', 'setup.exe\u3000', 'setup.exe\u00a0', 'setup.EXE . ', 'setup.exe.\u3000 .'])(
    '끝의 공백·점을 걷은 뒤 판정해 %j를 막는다',
    (name) => {
      // when: 끝에 공백·점이 붙은 실행 파일을 검증한다
      const actual = validateUpload({ name, size: 10 }, '')

      // then: 차단 오류와 ".exe" 문구가 나온다
      expect(actual).toEqual({
        code: 'blocked-extension',
        message: '실행·설치 파일(.exe)은 업로드할 수 없습니다.',
      })
    },
  )

  // 테스트 코드: AT-044
  it('차단 확장자 이름의 점 파일(.exe)은 확장자가 없어 허용한다', () => {
    // when: ".exe" 파일을 검증한다
    const actual = validateUpload({ name: '.exe', size: 10 }, '')

    // then: 오류가 없다
    expect(actual).toBeNull()
  })

  // 테스트 코드: AT-044
  it('a.tar.gz는 허용하고 마지막 확장자만 본다', () => {
    // when·then: 이중 확장자 세 가지를 검증하면 앞의 둘은 통과하고 마지막(.exe)만 차단된다
    expect(validateUpload({ name: 'a.tar.gz', size: 10 }, '')).toBeNull()
    expect(validateUpload({ name: 'a.exe.txt', size: 10 }, '')).toBeNull()
    expect(validateUpload({ name: 'a.txt.exe', size: 10 }, '')?.code).toBe('blocked-extension')
  })

  // 테스트 코드: AT-044
  it('100MB는 허용하고 1바이트 초과는 거부한다', () => {
    // when·then: 정확히 100MB와 1바이트 초과를 검증하면 앞은 통과하고 뒤는 크기 오류다
    expect(validateUpload({ name: 'big.bin', size: 100 * MB }, '')).toBeNull()
    expect(validateUpload({ name: 'big.bin', size: 100 * MB + 1 }, '')).toEqual({
      code: 'too-large',
      message: '파일 크기가 100MB를 초과합니다. (최대 100MB)',
    })
  })

  // 테스트 코드: AT-045
  it('설명은 100자까지 허용한다', () => {
    // when·then: 설명 100자와 101자를 검증하면 100자는 통과하고 101자는 설명 오류다
    expect(validateUpload(ok, 'a'.repeat(100))).toBeNull()
    expect(validateUpload(ok, 'a'.repeat(101))).toEqual({
      code: 'description-too-long',
      message: '설명은 100자 이내로 입력하세요.',
    })
  })

  // 테스트 코드: AT-045
  it('설명은 앞뒤 공백을 자른 뒤 센다', () => {
    // when·then: 공백이 붙은 100자는 통과하고 공백 뒤 101자는 설명 오류이며 공백뿐인 설명은 통과한다
    expect(validateUpload(ok, `  ${'a'.repeat(100)}  `)).toBeNull()
    expect(validateUpload(ok, `\n\t${'가'.repeat(101)} `)?.code).toBe('description-too-long')
    expect(validateUpload(ok, ' \t ')).toBeNull()
  })

  // 테스트 코드: AT-045
  it('설명 길이는 코드 포인트로 센다(이모지 하나가 1자)', () => {
    // when·then: 이모지 100개는 통과하고 101개는 설명 오류다
    expect(validateUpload(ok, '😀'.repeat(100))).toBeNull()
    expect(validateUpload(ok, '😀'.repeat(101))).toEqual({
      code: 'description-too-long',
      message: '설명은 100자 이내로 입력하세요.',
    })
  })

  // 테스트 코드: AT-044
  it('정상 파일은 오류가 없다', () => {
    // when: 올바른 파일을 검증한다
    const actual = validateUpload(ok, '')

    // then: 오류가 없다
    expect(actual).toBeNull()
  })
})

describe('validateUpload: 파일 이름 규칙 (서버 FileName.parse와 같은 입력)', () => {
  const invalid = { code: 'invalid-name', message: '사용할 수 없는 파일 이름입니다.' }
  const check = (name: string) => validateUpload({ name, size: 10 }, '')
  const BIDI = ['\u202a', '\u202b', '\u202c', '\u202d', '\u202e', '\u2066', '\u2067', '\u2068', '\u2069', '\u200e', '\u200f', '\u061c']

  // 테스트 코드: AT-044
  it.each(['', '.', '..', 'a/b.pdf', 'a\\b.pdf', '/', '../x.pdf'])('쓸 수 없는 이름 %j를 거부한다', (name) => {
    // when: 이름을 검증한다
    const actual = check(name)

    // then: 이름 오류가 나온다
    expect(actual).toEqual(invalid)
  })

  // 테스트 코드: AT-044
  it.each(['a\u0000b.pdf', 'a\tb.pdf', 'a\nb.pdf', 'a\u001fb.pdf', 'a\u007fb.pdf'])('제어 문자가 든 이름 %j를 거부한다', (name) => {
    // when: 제어 문자가 든 이름을 검증한다
    const actual = check(name)

    // then: 이름 오류가 나온다
    expect(actual).toEqual(invalid)
  })

  // 테스트 코드: AT-044
  it.each(BIDI)('방향 제어 문자 U+%s가 든 이름을 거부한다', (mark) => {
    // when: 방향 제어 문자가 든 이름을 검증한다
    const actual = check(`견적서${mark}fdp.pdf`)

    // then: 이름 오류가 나온다
    expect(actual).toEqual(invalid)
  })

  // 2026-10-17 사용자 결정: 서식 문자(Cf) 전체를 이름 어디에서든 거부한다(서버 FileName.parse와 같다).
  const CF = ['\ufeff', '\u200b', '\u200c', '\u200d', '\u2060', '\u00ad']

  // 테스트 코드: AT-044
  it.each(CF)('서식 문자 U+%s는 앞·중간·뒤 어디에 있어도 거부한다', (mark) => {
    // when·then: 서식 문자를 앞·중간·뒤에 넣은 이름을 검증하면 모두 이름 오류다
    expect(check(`${mark}report.pdf`)).toEqual(invalid)
    expect(check(`re${mark}port.pdf`)).toEqual(invalid)
    expect(check(`report.pdf${mark}`)).toEqual(invalid)
  })

  // 테스트 코드: AT-044
  it('끝의 제로폭 공백으로 위장한 실행 파일은 이름 오류로 거부한다', () => {
    // when: 끝에 제로폭 공백이 붙은 "setup.exe"를 검증한다
    const actual = check('setup.exe\u200b')

    // then: 이름 오류가 나온다
    expect(actual).toEqual(invalid)
  })

  // 테스트 코드: AT-044
  it('끝에 BOM이 붙은 setup.exe도 거부한다', () => {
    // when·then: 끝에 BOM이 붙은 "setup.exe"를 검증하면 오류가 있다
    expect(check('setup.exe\ufeff')).not.toBeNull()
  })

  // 테스트 코드: AT-044
  it('ZWJ 이모지 시퀀스는 거부하고 일반 이모지·한글은 받아들인다', () => {
    // when·then: ZWJ 시퀀스는 이름 오류이고 서식 문자 없는 이모지·한글 이름은 통과한다
    expect(check('\u{1F468}\u200d\u{1F469}\u200d\u{1F467}.png')).toEqual(invalid)
    expect(check('\u{1F600}.png')).toBeNull()
    expect(check('\u2764\ufe0f.png')).toBeNull()
    expect(check('한글👍.pdf')).toBeNull()
  })

  // 테스트 코드: AT-044
  it('255 코드 포인트는 허용하고 256은 거부한다(이모지는 한 글자)', () => {
    // when·then: 255자와 256자 이름을 검증하면 255자는 통과하고 256자는 이름 오류다
    expect(check('a'.repeat(255))).toBeNull()
    expect(check('a'.repeat(256))).toEqual(invalid)
    expect(check('😀'.repeat(255))).toBeNull()
    expect(check('😀'.repeat(256))).toEqual(invalid)
  })

  // 테스트 코드: AT-044
  it('길이는 NFC 정규화 뒤에 잰다', () => {
    // when·then: 결합 문자로 분해한 이름을 검증하면 정규화한 길이 255까지 통과하고 256은 이름 오류다
    const decomposed = 'e\u0301'
    expect(check(decomposed.repeat(200))).toBeNull()
    expect(check(decomposed.repeat(255))).toBeNull()
    expect(check(decomposed.repeat(256))).toEqual(invalid)
  })

  // 테스트 코드: AT-044
  it('앞뒤 공백·가운데 점·특수하지만 허용되는 문자는 그대로 허용한다', () => {
    // when·then: 허용되는 여러 이름을 검증하면 모두 통과한다
    for (const name of [' a.pdf', 'a.pdf ', '.bashrc', 'a..b', '견적서 (최종) #1 & 2%.pdf', 'a'.repeat(250) + '.pdf']) {
      expect(check(name)).toBeNull()
    }
  })

  // 테스트 코드: AT-044
  it('차단 확장자를 이름 규칙보다 먼저 판정한다(서버 순서)', () => {
    // when·then: 이름이 틀린 실행 파일은 차단 확장자 오류, 이름만 틀린 파일은 이름 오류다
    expect(check('a/b.exe')?.code).toBe('blocked-extension')
    expect(check('a/b.pdf')?.code).toBe('invalid-name')
  })
})

describe('validateUpload: 판정 순서 (파일 없음 > 설명 > 크기 > 확장자 > 이름)', () => {
  const long = 'x'.repeat(101)

  // 테스트 코드: AT-044
  it('파일 없음을 가장 먼저 판정한다', () => {
    // when: 파일 없이 긴 설명으로 검증한다
    const actual = validateUpload(null, long)?.code

    // then: 파일 없음 오류다
    expect(actual).toBe('no-file')
  })

  // 테스트 코드: AT-044
  it('설명을 크기보다 먼저 판정한다', () => {
    // when: 설명 초과, 크기 초과, 차단 확장자를 함께 검증한다
    const actual = validateUpload({ name: 'a.exe', size: 100 * MB + 1 }, long)?.code

    // then: 설명 오류다
    expect(actual).toBe('description-too-long')
  })

  // 테스트 코드: AT-044
  it('크기를 확장자보다 먼저 판정한다', () => {
    // when: 크기 초과와 차단 확장자를 함께 검증한다
    const actual = validateUpload({ name: 'a.exe', size: 100 * MB + 1 }, '')?.code

    // then: 크기 오류다
    expect(actual).toBe('too-large')
  })

  // 테스트 코드: AT-044
  it('확장자를 이름보다 먼저 판정한다', () => {
    // when: 차단 확장자와 틀린 이름을 함께 검증한다
    const actual = validateUpload({ name: 'a/b.exe', size: 1 }, '')?.code

    // then: 차단 확장자 오류다
    expect(actual).toBe('blocked-extension')
  })

  // 테스트 코드: AT-044
  it('0바이트 파일은 허용한다', () => {
    // when: 0바이트 파일을 검증한다
    const actual = validateUpload({ name: 'empty.txt', size: 0 }, '')

    // then: 오류가 없다
    expect(actual).toBeNull()
  })
})
