/** mock 게이트웨이의 오류 규약. 실패는 모두 `ApiError`(status, problem)로 던진다. detail이 사용자 문구다. */

import { ApiError } from '../../shared/api/problem'
import type { ReportIssue } from '../../shared/model/reportTypes'

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

/** 서버와 같은 문구: Quarter와 월은 함께 쓸 수 없다(422). */
export const QUARTER_MONTH_EXCLUSIVE = 'Quarter와 월은 함께 선택할 수 없습니다.'

/** 리포트 정의 위반(422 invalid-report). detail은 첫 위반 문구이고 위반 전체는 `problem.reportErrors`에 싣는다. */
export const invalidReport = (issues: ReportIssue[]): ApiError =>
  new ApiError(422, {
    type: `${PROBLEM_BASE}invalid-report`,
    title: 'Invalid Report',
    status: 422,
    detail: issues[0]?.message ?? '리포트 정의가 올바르지 않습니다.',
    reportErrors: issues,
  })

/** 서버와 같은 고정 문구: 조회가 제한 시간 안에 끝나지 않음(503 report-timeout). */
export const REPORT_TIMEOUT_MESSAGE = '조회가 10초 안에 끝나지 않았습니다. 조건을 좁히거나 컬럼을 줄이세요'
export const reportTimeout = (): ApiError =>
  problem(503, 'report-timeout', 'Report Timeout', REPORT_TIMEOUT_MESSAGE)

/** 저장 리포트: 모든 리포트 사이에서 대소문자 무시로 같은 이름(409). 서버 kind 표기(`already-exists`)를 그대로 쓴다(게이트웨이 정규화 `conflict`로 합치지 않는다). */
export const SAVED_REPORT_DUPLICATE_MESSAGE = '같은 이름의 리포트가 이미 있습니다.'
export const alreadyExists = (detail: string): ApiError => problem(409, 'already-exists', 'Already Exists', detail)

/** 저장 리포트: 먼저 저장된 revision과 어긋남(409). 서버 kind 표기(`invalid-state`) 그대로. */
export const SAVED_REPORT_CONFLICT_MESSAGE = '다른 사용자가 먼저 이 리포트를 저장했습니다. 다시 불러온 뒤 수정하거나 다른 이름으로 저장하세요.'
export const invalidState = (detail: string): ApiError => problem(409, 'invalid-state', 'Invalid State', detail)

/** 저장 리포트: 없는 리포트와 볼 수 없는 리포트에 같은 문구(존재를 숨긴다). */
export const SAVED_REPORT_NOT_FOUND_MESSAGE = '리포트를 찾을 수 없습니다.'
export const SAVED_REPORT_DELETE_FORBIDDEN_MESSAGE = '리포트를 만든 사람 또는 admin만 삭제할 수 있습니다.'
export const SAVED_REPORT_VISIBILITY_FORBIDDEN_MESSAGE = '공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다.'
