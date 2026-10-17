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
  it('decodes the UTF-8 filename* of a Korean name', () => {
    expect(fileNameFromDisposition(serverHeader('견적서_한빛은행 v2.pdf'))).toBe('견적서_한빛은행 v2.pdf')
  })

  it('prefers filename* over the ASCII fallback in filename', () => {
    const header = `attachment; filename="______.pdf"; filename*=UTF-8''%EA%B2%AC%EC%A0%81.pdf`

    expect(fileNameFromDisposition(header)).toBe('견적.pdf')
  })

  it('round-trips names with a percent sign, a quote, a semicolon and a backslash', () => {
    for (const name of ['100%.pdf', 'say "hi".txt', 'a;b.txt', 'back\\slash.txt', "o'neil.txt"]) {
      expect(fileNameFromDisposition(serverHeader(name))).toBe(name)
    }
  })

  it('round-trips an emoji outside the BMP', () => {
    expect(fileNameFromDisposition(serverHeader('😀 메모.txt'))).toBe('😀 메모.txt')
  })

  it('accepts a lowercase charset label in filename*', () => {
    expect(fileNameFromDisposition(`attachment; filename*=utf-8''%ED%95%9C%EA%B8%80.txt`)).toBe('한글.txt')
  })

  it('falls back to the quoted filename when there is no filename*', () => {
    expect(fileNameFromDisposition('attachment; filename="report.pdf"')).toBe('report.pdf')
  })

  it('keeps a semicolon inside the quoted filename', () => {
    expect(fileNameFromDisposition('attachment; filename="a;b.pdf"')).toBe('a;b.pdf')
  })

  it('reads an unquoted filename token', () => {
    expect(fileNameFromDisposition('attachment; filename=report.pdf')).toBe('report.pdf')
  })

  it('falls back to filename when filename* cannot be decoded', () => {
    const header = `attachment; filename="fallback.pdf"; filename*=UTF-8''%E0%A4%A.pdf`

    expect(fileNameFromDisposition(header)).toBe('fallback.pdf')
  })

  it.each([null, '', 'attachment', 'inline'])('answers download when the header is %j', (header) => {
    expect(fileNameFromDisposition(header)).toBe('download')
  })

  it('does not turn a path into a directory traversal name', () => {
    const name = fileNameFromDisposition(`attachment; filename*=UTF-8''..%2F..%2Fetc%2Fpasswd`)

    expect(name).not.toContain('/')
  })
})
