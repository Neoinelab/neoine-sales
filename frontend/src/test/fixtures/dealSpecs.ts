/**
 * 시드 Deal 24건의 명세(계획 4.3). 날짜는 모두 기준일 상대값.
 * - close: Expected Close(= 매출일)가 기준일에서 며칠 뒤인지(음수=과거)
 * - lastAgo: 마지막 Action이 며칠 전인지, due: 마지막 Action의 Due Date가 기준일에서 며칠 뒤인지
 * - count: Action 개수
 */

export interface DealSpec {
  no: number
  name: string
  customer: string
  /** 활성 파트너(없으면 null). */
  partner: string | null
  /** 이전에 연결했다가 교체된 파트너. */
  prevPartner?: string
  owner: string
  vendor: string
  solution: string
  status: string
  forecast: string
  amountM: number
  close: number
  lastAgo: number
  due: number
  count: number
  users: number
  procurement?: string
  quote?: 'YES' | 'NO'
  poc?: 'YES' | 'ING' | 'NO'
  /** [Budget, Authority, Need, Timeline] Label 이름(없으면 null). */
  bant?: readonly [string | null, string | null, string | null, string | null]
}

const NONE = null

export const DEAL_SPECS: readonly DealSpec[] = [
  { no: 1, name: '한빛은행 ITDR 도입', customer: 'c:한빛은행/정민수', partner: 'p:에이원시스템/표성호', owner: 'kim', vendor: 'Silverfort', solution: 'ITDR', status: 'price_negotiation', forecast: 'commit', amountM: 1870, close: 12, lastAgo: 2, due: 3, count: 4, users: 1500, procurement: '조달청 경쟁 입찰', quote: 'YES', poc: 'YES', bant: ['단독 예산 확보', 'CISO 보고 완료', '보안 강화 요건', '금년 구매'] },
  { no: 2, name: '대한제조 MFA 확대', customer: 'c:대한제조/서준영', partner: 'p:코어테크/민지훈', owner: 'kim', vendor: 'Silverfort', solution: 'MFA', status: 'technical_evaluation', forecast: 'most_likely', amountM: 420, close: 40, lastAgo: 5, due: 6, count: 4, users: 300, procurement: '검토 중', quote: 'NO', poc: 'YES', bant: ['풀 예산 확보', '팀장 보고 완료', NONE, 'POC 후 일정수립'] },
  { no: 3, name: '미래전자 EDR 교체', customer: 'c:미래전자/권나연', partner: 'p:넷브릿지/하준서', owner: 'park', vendor: 'CrowdStrike', solution: 'EDR', status: 'poc_completed', forecast: 'best', amountM: 960, close: 55, lastAgo: 6, due: -4, count: 3, users: 800, bant: ['예산 작업중', '팀장 검토', '보안 사고 발생', NONE] },
  { no: 4, name: '새론병원 PAM 구축', customer: 'c:새론병원/문서연', partner: 'p:시큐어원/조예린', owner: 'park', vendor: 'CyberArk', solution: 'PAM', status: 'poc_preparation', forecast: 'best', amountM: 310, close: 70, lastAgo: 21, due: 2, count: 3, users: 120 },
  { no: 5, name: '누리통신 NGFW 갱신', customer: 'c:누리통신/배성훈/차장', partner: null, owner: 'lee', vendor: 'Palo Alto', solution: 'NGFW', status: 'introduction', forecast: 'pipeline', amountM: 650, close: 95, lastAgo: 4, due: 9, count: 3, users: 2000 },
  { no: 6, name: '푸른물류 SSO 도입', customer: 'c:푸른물류/장하은', partner: 'p:디지털웨이/구본혁', owner: 'lee', vendor: 'Okta', solution: 'SSO', status: 'prospecting', forecast: 'pipeline', amountM: 180, close: 120, lastAgo: 3, due: 14, count: 2, users: 400 },
  { no: 7, name: '하늘카드 AD 보안 강화', customer: 'c:하늘카드/신동혁', partner: 'p:에이원시스템/남궁은지', owner: 'kim', vendor: 'Silverfort', solution: 'ITDR', status: 'poc_completed', forecast: 'commit', amountM: 740, close: 20, lastAgo: 18, due: -3, count: 4, users: 900, quote: 'YES', bant: ['잔여 예산 활용', 'CEO 보고 완료', '컴플라이언스', '금년 구매'] },
  { no: 8, name: '세종에너지 취약점 진단', customer: 'c:세종에너지/고민재', partner: 'p:코어테크/민지훈', owner: 'jung', vendor: 'Tenable', solution: 'VM', status: 'technical_evaluation', forecast: 'most_likely', amountM: 230, close: 33, lastAgo: 7, due: 5, count: 3, users: 600 },
  { no: 9, name: '도담건설 EDR', customer: 'c:도담건설/안서진', partner: 'p:넷브릿지/하준서', owner: 'jung', vendor: 'SentinelOne', solution: 'EDR', status: 'introduction', forecast: 'pipeline', amountM: 95, close: 85, lastAgo: 8, due: 10, count: 2, users: 150 },
  { no: 10, name: '우주항공연구원 ZTNA', customer: 'c:우주항공연구원/노현우', partner: 'p:시큐어원/조예린', owner: 'park', vendor: 'Zscaler', solution: 'ZTNA', status: 'price_negotiation', forecast: 'commit', amountM: 1200, close: 8, lastAgo: 1, due: 1, count: 4, users: 1200, procurement: '수의계약', quote: 'YES', poc: 'YES', bant: ['단독 예산 확보', 'CEO 보고 완료', 'CISO 지시', '금년 구매'] },
  { no: 11, name: '청명대학교 SSO/MFA', customer: 'c:청명대학교/황지수', partner: 'p:디지털웨이/마서연', owner: 'kim', vendor: 'Okta', solution: 'SSO', status: 'contract_completed', forecast: 'won', amountM: 150, close: -10, lastAgo: 10, due: -5, count: 3, users: 3000 },
  { no: 12, name: '바른제약 PAM', customer: 'c:바른제약/송다인', partner: null, owner: 'lee', vendor: 'CyberArk', solution: 'PAM', status: 'contract_completed', forecast: 'won', amountM: 520, close: -35, lastAgo: 35, due: -30, count: 2, users: 250 },
  { no: 13, name: '한빛은행 EDR 확장', customer: 'c:한빛은행/임태호', partner: 'p:넷브릿지/하준서', owner: 'kim', vendor: 'CrowdStrike', solution: 'EDR', status: 'technical_evaluation', forecast: 'best', amountM: 880, close: 60, lastAgo: 9, due: 7, count: 3, users: 1000, bant: ['풀 예산 확보', '담당자 검토', '보안 강화 요건', '내년구매'] },
  { no: 14, name: '대한제조 NGFW', customer: 'c:대한제조/서준영', partner: null, owner: 'park', vendor: 'Palo Alto', solution: 'NGFW', status: 'prospecting', forecast: 'pipeline', amountM: 400, close: 150, lastAgo: 16, due: 12, count: 2, users: 500 },
  { no: 15, name: '미래전자 ITDR', customer: 'c:미래전자/권나연', partner: 'p:코어테크/민지훈', owner: 'jung', vendor: 'Silverfort', solution: 'ITDR', status: 'introduction', forecast: 'pipeline', amountM: 275, close: 100, lastAgo: 6, due: 8, count: 3, users: 350 },
  { no: 16, name: '새론병원 SSO', customer: 'c:새론병원/문서연', partner: null, owner: 'kim', vendor: 'Okta', solution: 'SSO', status: 'price_negotiation', forecast: 'lost', amountM: 140, close: -5, lastAgo: 5, due: -2, count: 3, users: 200 },
  { no: 17, name: '누리통신 MFA', customer: 'c:누리통신/배성훈/과장', partner: 'p:에이원시스템/표성호', prevPartner: 'p:코어테크/민지훈', owner: 'lee', vendor: 'Silverfort', solution: 'MFA', status: 'poc_preparation', forecast: 'best', amountM: 330, close: 75, lastAgo: 4, due: 6, count: 4, users: 700 },
  { no: 18, name: '푸른물류 취약점 진단', customer: 'c:푸른물류/장하은', partner: 'p:시큐어원/조예린', owner: 'jung', vendor: 'Tenable', solution: 'VM', status: 'price_negotiation', forecast: 'most_likely', amountM: 190, close: 18, lastAgo: 3, due: 0, count: 3, users: 450 },
  { no: 19, name: '하늘카드 PAM', customer: 'c:하늘카드/윤소라', partner: null, owner: 'park', vendor: 'CyberArk', solution: 'PAM', status: 'poc_completed', forecast: 'best', amountM: 610, close: 45, lastAgo: 5, due: 9, count: 3, users: 280 },
  { no: 20, name: '세종에너지 ZTNA', customer: 'c:세종에너지/고민재', partner: 'p:디지털웨이/구본혁', owner: 'kim', vendor: 'Zscaler', solution: 'ZTNA', status: 'prospecting', forecast: 'pipeline', amountM: 210, close: 130, lastAgo: 2, due: 11, count: 2, users: 650 },
  { no: 21, name: '청명대학교 EDR', customer: 'c:청명대학교/황지수', partner: 'p:넷브릿지/하준서', owner: 'lee', vendor: 'SentinelOne', solution: 'EDR', status: 'technical_evaluation', forecast: 'commit', amountM: 470, close: 25, lastAgo: 3, due: 4, count: 3, users: 5000, quote: 'YES' },
  { no: 22, name: '바른제약 ITDR', customer: 'c:바른제약/송다인', partner: 'p:코어테크/민지훈', owner: 'park', vendor: 'Silverfort', solution: 'ITDR', status: 'poc_preparation', forecast: 'pipeline', amountM: 260, close: 110, lastAgo: 6, due: 10, count: 3, users: 320, poc: 'ING' },
  { no: 23, name: '한빛은행 PAM', customer: 'c:한빛은행/오지현', partner: 'p:시큐어원/조예린', owner: 'old', vendor: 'CyberArk', solution: 'PAM', status: 'introduction', forecast: 'pipeline', amountM: 450, close: 90, lastAgo: 22, due: 5, count: 3, users: 380 },
  { no: 24, name: '도담건설 MFA', customer: 'c:도담건설/안서진', partner: 'p:에이원시스템/표성호', owner: 'kim', vendor: 'Silverfort', solution: 'MFA', status: 'contract_completed', forecast: 'won', amountM: 88, close: -60, lastAgo: 60, due: -50, count: 2, users: 180 },
]

/** Action 간 간격(일). 가장 오래된 Action은 마지막 Action보다 SPACING*(count-1)일 전이다. */
export const ACTION_SPACING = 8

/** Deal 등록은 가장 오래된 Action보다 이만큼 전. */
export const CREATE_LEAD_DAYS = 3

/** i번째(0=가장 최근) Action의 수행 시각(시). */
export function actionHour(no: number, i: number): number {
  return 10 + ((no + i) % 7)
}

export function createdAgo(spec: Pick<DealSpec, 'lastAgo' | 'count'>): number {
  return spec.lastAgo + ACTION_SPACING * (spec.count - 1) + CREATE_LEAD_DAYS
}
