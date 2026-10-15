/** 첨부 파일 업로드 검증(A-0 계약, 구현은 A-1). 화면과 게이트웨이가 같은 함수를 쓴다. 계획 6.5 / PRD 5.8·7.7. */

import { BLOCKED_EXTENSIONS, MAX_FILE_BYTES, MAX_FILE_DESCRIPTION } from './constants'

export type FileRuleCode = 'no-file' | 'description-too-long' | 'too-large' | 'blocked-extension'

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
 */
export function validateUpload(
  file: { name: string; size: number } | null,
  description: string,
): FileRuleError | null {
  if (file === null) return { code: 'no-file', message: '업로드할 파일을 선택하세요.' }
  if (Array.from(description).length > MAX_FILE_DESCRIPTION) {
    return { code: 'description-too-long', message: `설명은 ${MAX_FILE_DESCRIPTION}자 이내로 입력하세요.` }
  }
  if (file.size > MAX_FILE_BYTES) {
    return { code: 'too-large', message: '파일 크기가 100MB를 초과합니다. (최대 100MB)' }
  }
  const ext = extensionOf(file.name)
  if (BLOCKED_EXTENSIONS.includes(ext)) {
    return { code: 'blocked-extension', message: `실행·설치 파일(.${ext})은 업로드할 수 없습니다.` }
  }
  return null
}

/** 마지막 확장자(점 제외, 소문자). 없으면 ''. 'a.tar.gz' → 'gz', 'run.EXE' → 'exe', '.bashrc' → ''. */
export function extensionOf(fileName: string): string {
  const dot = fileName.lastIndexOf('.')
  if (dot <= 0 || dot === fileName.length - 1) return ''
  return fileName.slice(dot + 1).toLowerCase()
}

/** 저장소 장애(503) 문구: "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요." */
export const STORAGE_UNAVAILABLE_MESSAGE =
  '파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요.'
