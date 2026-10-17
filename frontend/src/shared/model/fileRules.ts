/** 첨부 파일 업로드 검증(A-0 계약, 구현은 A-1). 화면과 게이트웨이가 같은 함수를 쓴다. 계획 6.5 / PRD 5.8·7.7. */

import { BLOCKED_EXTENSIONS, MAX_FILE_BYTES, MAX_FILE_DESCRIPTION } from './constants'

export type FileRuleCode = 'no-file' | 'description-too-long' | 'too-large' | 'blocked-extension' | 'invalid-name'

export interface FileRuleError {
  code: FileRuleCode
  /** 사용자에게 보일 문구(아래 표 그대로). */
  message: string
}

/**
 * 문구
 * - no-file: "업로드할 파일을 선택하세요."
 * - description-too-long: "설명은 100자 이내로 입력하세요."
 * - too-large: "파일 크기가 100MB를 초과합니다. (최대 100MB)"  (100MB=104,857,600바이트 허용, +1바이트 거부)
 * - blocked-extension: "실행·설치 파일(.exe)은 업로드할 수 없습니다."  (확장자는 실제 값, 소문자로 표시)
 * - invalid-name: "사용할 수 없는 파일 이름입니다."
 * 판정 순서: 파일 없음 > 설명(trim 뒤 코드 포인트) > 크기 > 차단 확장자 > 이름 규칙. 서버와 같은 순서·문구다.
 */
export function validateUpload(
  file: { name: string; size: number } | null,
  description: string,
): FileRuleError | null {
  if (file === null) return { code: 'no-file', message: '업로드할 파일을 선택하세요.' }
  if (Array.from(description.trim()).length > MAX_FILE_DESCRIPTION) {
    return { code: 'description-too-long', message: `설명은 ${MAX_FILE_DESCRIPTION}자 이내로 입력하세요.` }
  }
  if (file.size > MAX_FILE_BYTES) {
    return { code: 'too-large', message: '파일 크기가 100MB를 초과합니다. (최대 100MB)' }
  }
  const ext = extensionOf(file.name)
  if (BLOCKED_EXTENSIONS.includes(ext)) {
    return { code: 'blocked-extension', message: `실행·설치 파일(.${ext})은 업로드할 수 없습니다.` }
  }
  if (!isValidFileName(file.name)) return { code: 'invalid-name', message: INVALID_NAME_MESSAGE }
  return null
}

const INVALID_NAME_MESSAGE = '사용할 수 없는 파일 이름입니다.'
const MAX_FILE_NAME_LENGTH = 255
// 제어 문자(C0, DEL)와 양방향 서식 문자(U+202A-202E, U+2066-2069, U+200E/F, U+061C).
// eslint-disable-next-line no-control-regex
const FORBIDDEN_NAME_CHARS = /[\u0000-\u001f\u007f\u202a-\u202e\u2066-\u2069\u200e\u200f\u061c/\\]/

// 서식 문자(유니코드 Cf: BOM, 제로폭 문자, 소프트 하이픈, 양방향 문자 등). U+FE0F(Mn)는 해당하지 않아 허용된다.
const FORMAT_CHARS = /\p{Cf}/u

/** 서버 `FileName.parse`와 같은 규칙: NFC 정규화 뒤 빈 이름·`.`·`..`·경로 구분자·제어/양방향 문자·255 코드 포인트 초과를 거부. */
function isValidFileName(rawName: string): boolean {
  const name = rawName.normalize('NFC')
  if (name === '' || name === '.' || name === '..') return false
  if (FORBIDDEN_NAME_CHARS.test(name) || FORMAT_CHARS.test(name)) return false
  return Array.from(name).length <= MAX_FILE_NAME_LENGTH
}

/** 이름 끝의 공백·점을 걷어 낸 뒤(서버와 같게) 마지막 확장자(점 제외, 소문자). 없으면 ''. 'a.tar.gz' → 'gz', 'run.EXE' → 'exe', '.bashrc' → ''. */
export function extensionOf(fileName: string): string {
  const trimmed = fileName.replace(/[\s.]+$/, '')
  const dot = trimmed.lastIndexOf('.')
  if (dot <= 0) return ''
  return trimmed.slice(dot + 1).toLowerCase()
}

/** 저장소 장애(503) 문구: "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요." */
export const STORAGE_UNAVAILABLE_MESSAGE =
  '파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요.'
