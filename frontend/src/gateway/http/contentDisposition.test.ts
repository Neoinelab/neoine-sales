import { describe, expect, it } from 'vitest'
import { fileNameFromDisposition } from './contentDisposition'

/** 서버(`web/content_disposition.py`)가 만드는 형식: ASCII 대체 이름 + RFC 5987 퍼센트 인코딩 원본 이름. */
function serverHeader(fileName: string): string {
  const fallback = Array.from(fileName, (c) => (/^[\x20-\x7e]$/.test(c) && !'"\\%'.includes(c) ? c : '_')).join('')
  // Python `quote(safe='')`와 같게: encodeURIComponent가 남기는 !'()*도 인코딩한다.
  const encoded = encodeURIComponent(fileName).replace(/[!'()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`)
  return `attachment; filename="${fallback}"; filename*=UTF-8''${encoded}`
}

describe('fileNameFromDisposition', () => {
  // 테스트 코드: AT-053
  it('한글 이름의 UTF-8 filename*를 해독한다', () => {
    // when: 서버 형식의 한글 이름 헤더에서 이름을 읽는다
    const actual = fileNameFromDisposition(serverHeader('견적서_한빛은행 v2.pdf'))

    // then: 원래 한글 이름이다
    expect(actual).toBe('견적서_한빛은행 v2.pdf')
  })

  // 테스트 코드: AT-053
  it('filename*가 있으면 ASCII 대체 이름보다 우선한다', () => {
    // given: 대체 이름과 filename*가 함께 있는 헤더
    const header = `attachment; filename="______.pdf"; filename*=UTF-8''%EA%B2%AC%EC%A0%81.pdf`

    // when: 이름을 읽는다
    const actual = fileNameFromDisposition(header)

    // then: filename*의 이름이다
    expect(actual).toBe('견적.pdf')
  })

  // 테스트 코드: AT-053
  it('퍼센트·따옴표·세미콜론·역슬래시가 든 이름도 왕복한다', () => {
    // when·then: 특수 문자가 든 이름을 서버 형식 헤더로 만들어 읽으면 원래 이름이다
    for (const name of ['100%.pdf', 'say "hi".txt', 'a;b.txt', 'back\\slash.txt', "o'neil.txt"]) {
      expect(fileNameFromDisposition(serverHeader(name))).toBe(name)
    }
  })

  // 테스트 코드: AT-053
  it('BMP 밖 이모지 이름도 왕복한다', () => {
    // when: 이모지 이름의 서버 헤더에서 이름을 읽는다
    const actual = fileNameFromDisposition(serverHeader('😀 메모.txt'))

    // then: 원래 이름이다
    expect(actual).toBe('😀 메모.txt')
  })

  // 테스트 코드: AT-053
  it('filename*의 문자셋 이름은 소문자여도 받아들인다', () => {
    // when: 소문자 utf-8 문자셋의 헤더에서 이름을 읽는다
    const actual = fileNameFromDisposition(`attachment; filename*=utf-8''%ED%95%9C%EA%B8%80.txt`)

    // then: 해독한 한글 이름이다
    expect(actual).toBe('한글.txt')
  })

  // 테스트 코드: AT-053
  it('filename*가 없으면 따옴표 filename을 쓴다', () => {
    // when: filename만 있는 헤더에서 이름을 읽는다
    const actual = fileNameFromDisposition('attachment; filename="report.pdf"')

    // then: 따옴표를 벗긴 이름이다
    expect(actual).toBe('report.pdf')
  })

  // 테스트 코드: AT-053
  it('따옴표 안의 세미콜론은 이름에 남는다', () => {
    // when: 세미콜론이 든 따옴표 filename에서 이름을 읽는다
    const actual = fileNameFromDisposition('attachment; filename="a;b.pdf"')

    // then: 세미콜론이 남아 있다
    expect(actual).toBe('a;b.pdf')
  })

  // 테스트 코드: AT-053
  it('따옴표 없는 filename도 읽는다', () => {
    // when: 따옴표 없는 filename에서 이름을 읽는다
    const actual = fileNameFromDisposition('attachment; filename=report.pdf')

    // then: 그 이름이다
    expect(actual).toBe('report.pdf')
  })

  // 테스트 코드: AT-053
  it('filename*를 해독할 수 없으면 filename을 쓴다', () => {
    // given: 해독할 수 없는 filename*와 정상 filename이 있는 헤더
    const header = `attachment; filename="fallback.pdf"; filename*=UTF-8''%E0%A4%A.pdf`

    // when: 이름을 읽는다
    const actual = fileNameFromDisposition(header)

    // then: filename의 이름이다
    expect(actual).toBe('fallback.pdf')
  })

  // 테스트 코드: AT-053
  it.each([null, '', 'attachment', 'inline'])('헤더가 %j이면 "download"로 답한다', (header) => {
    // when: 비었거나 이름 없는 헤더에서 이름을 읽는다
    const actual = fileNameFromDisposition(header)

    // then: "download"다
    expect(actual).toBe('download')
  })

  // 테스트 코드: AT-053
  it('경로 문자가 든 이름은 디렉터리 이동 이름이 되지 않는다', () => {
    // given: 경로 구분자가 인코딩된 filename* 헤더
    const header = `attachment; filename*=UTF-8''..%2F..%2Fetc%2Fpasswd`

    // when: 이름을 읽는다
    const name = fileNameFromDisposition(header)

    // then: 이름에 "/"가 없다
    expect(name).not.toContain('/')
  })
})
