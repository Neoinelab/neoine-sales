/** mock 게이트웨이의 오류 규약. 실패는 모두 `ApiError`(status, problem)로 던진다. detail이 사용자 문구다. */

import { ApiError } from '../../shared/api/problem'

const PROBLEM_BASE = 'https://sales.neoine.test/problems/'

function problem(status: number, kind: string, title: string, detail: string, stage?: string): ApiError {
  return new ApiError(status, { type: `${PROBLEM_BASE}${kind}`, title, status, detail, ...(stage ? { stage } : {}) })
}

export const unauthorized = (detail = '로그인이 필요합니다.'): ApiError =>
  problem(401, 'unauthorized', 'Unauthorized', detail)

export const forbidden = (detail = '이 작업을 수행할 권한이 없습니다. 관리자에게 문의하세요.'): ApiError =>
  problem(403, 'forbidden', 'Forbidden', detail)

export const notFound = (detail: string): ApiError => problem(404, 'not-found', 'Not Found', detail)

export const validation = (detail: string): ApiError =>
  problem(422, 'validation', 'Unprocessable Entity', detail)

export const conflict = (detail: string): ApiError => problem(409, 'conflict', 'Conflict', detail)

export const fileExists = (fileName: string): ApiError =>
  problem(409, 'file-exists', 'File Exists', `같은 이름의 파일이 이미 있습니다: ${fileName}`)

export const storageUnavailable = (detail: string): ApiError =>
  problem(503, 'storage-unavailable', 'Service Unavailable', detail)

export const directoryFailed = (detail: string, stage: string): ApiError =>
  problem(422, 'directory-verification-failed', 'Directory Verification Failed', detail, stage)
