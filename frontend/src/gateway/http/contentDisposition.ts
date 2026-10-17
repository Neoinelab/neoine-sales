/** 서버 Content-Disposition(`filename`=ASCII 대체, `filename*`=UTF-8 원본)에서 내려받을 파일 이름을 읽는다. */

const FALLBACK = 'download'

/** 따옴표 안의 `;`와 `\"` 이스케이프를 지키며 `;`로 나눈다. */
function splitParams(header: string): string[] {
  const parts: string[] = []
  let current = ''
  let quoted = false
  for (let i = 0; i < header.length; i += 1) {
    const ch = header.charAt(i)
    if (quoted && ch === '\\' && i + 1 < header.length) {
      current += ch + header.charAt(i + 1)
      i += 1
    } else if (ch === '"') {
      quoted = !quoted
      current += ch
    } else if (ch === ';' && !quoted) {
      parts.push(current)
      current = ''
    } else {
      current += ch
    }
  }
  parts.push(current)
  return parts
}

function unquote(value: string): string {
  const v = value.trim()
  if (v.length >= 2 && v.startsWith('"') && v.endsWith('"')) return v.slice(1, -1).replace(/\\(.)/g, '$1')
  return v
}

function decodeExtended(value: string): string | null {
  const match = /^utf-8'[^']*'(.*)$/i.exec(value.trim())
  if (!match) return null
  try {
    return decodeURIComponent(match[1] ?? '')
  } catch {
    return null
  }
}

/** 경로 구분자를 이름에 남기지 않는다(저장 시 디렉터리 탈출 방지). */
function safe(name: string): string {
  const cleaned = name.replace(/\//g, '_')
  return cleaned === '' || cleaned === '.' || cleaned === '..' ? FALLBACK : cleaned
}

export function fileNameFromDisposition(header: string | null): string {
  if (!header) return FALLBACK
  let plain: string | null = null
  let extended: string | null = null
  for (const part of splitParams(header).slice(1)) {
    const eq = part.indexOf('=')
    if (eq < 0) continue
    const key = part.slice(0, eq).trim().toLowerCase()
    const value = part.slice(eq + 1)
    if (key === 'filename*') extended ??= decodeExtended(value)
    else if (key === 'filename') plain ??= unquote(value)
  }
  const name = extended ?? plain
  return name === null || name === '' ? FALLBACK : safe(name)
}
