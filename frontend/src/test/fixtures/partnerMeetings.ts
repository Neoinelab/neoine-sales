/**
 * 파트너 Activity 샘플 미팅 12건(테스트 전용). 날짜는 기준일에서 1~12일 전으로 모두 다르다.
 * 기본 정렬(미팅 날짜 내림차순)의 첫 10건은 `MEETING_CONTENTS`의 앞 10개, 나머지 2건은 마지막 2개다.
 * 작성자: kim(김영업) 6건, park(박영업) 5건, root(관리자) 1건. 미팅은 Deal과 무관하다.
 */

import type { PartnerMeetingRecord } from '../fake/store'
import { USER_ID, type SeedLoginId } from '../fake/seed/ids'
import type { SeedEnv } from '../fake/seed/env'
import { takeId } from '../fake/store'

/** [파트너 회사, 며칠 전, 내용, 작성자]. 오래된 순서(등록 순서)다. */
export const SEED_MEETINGS: readonly (readonly [string, number, string, SeedLoginId])[] = [
  ['코어테크', 12, '킥오프 일정 협의', 'kim'],
  ['코어테크', 11, '견적서 전달', 'park'],
  ['에이원시스템', 10, 'ITDR 기술 설명', 'kim'],
  ['에이원시스템', 9, 'POC 결과 공유\n다음 주 재방문', 'kim'],
  ['넷브릿지', 8, 'EDR 교체 일정', 'park'],
  ['넷브릿지', 7, '견적 재요청', 'root'],
  ['시큐어원', 6, 'PAM 데모 진행', 'park'],
  ['시큐어원', 5, 'ZTNA 계약 조건 협의', 'kim'],
  ['디지털웨이', 4, 'SSO 제안 설명', 'kim'],
  ['디지털웨이', 3, '수주 후 일정 점검', 'park'],
  ['코어테크', 2, 'ITDR 가격 협상', 'kim'],
  ['에이원시스템', 1, '계약 종료 후 정리', 'park'],
]

/** 기본 목록 순서(미팅 날짜 내림차순)의 내용. */
export const MEETING_CONTENTS: readonly string[] = [...SEED_MEETINGS].reverse().map((m) => m[2])

export function seedPartnerMeetings(env: SeedEnv, counters: Record<string, number>): PartnerMeetingRecord[] {
  return SEED_MEETINGS.map(([company, daysAgo, content, author]) => {
    const at = env.at(daysAgo, 11)
    return {
      id: takeId(counters, 'pm'),
      partnerCompany: company,
      meetingDate: env.date(-daysAgo),
      content,
      authorId: USER_ID[author],
      createdAt: at,
      updatedAt: at,
    }
  })
}
