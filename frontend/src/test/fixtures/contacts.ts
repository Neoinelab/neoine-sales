import type { Contact, ContactKind } from '../../shared/model/types'
import { takeId } from '../fake/store'
import type { SeedEnv } from '../fake/seed/env'

type Row = readonly [company: string, name: string, title: string, email: string | null, phone: string | null]

/** 고객 12사 / 17행. 한빛은행 3명, 누리통신 동명이인, 미래전자 이메일 없음. 회사명·담당자명에 공백 없음. */
const CUSTOMERS: readonly Row[] = [
  ['한빛은행', '정민수', '과장', 'jung@hanbit.test', '010-2345-6789'],
  ['한빛은행', '오지현', '차장', 'oh@hanbit.test', '010-3456-7890'],
  ['한빛은행', '임태호', '부장', 'lim@hanbit.test', '02-1234-5678'],
  ['누리통신', '배성훈', '차장', 'bae1@nuri.test', '010-1111-2222'],
  ['누리통신', '배성훈', '과장', 'bae2@nuri.test', '010-3333-4444'],
  ['미래전자', '권나연', '대리', null, '010-5555-6666'],
  ['대한제조', '서준영', '부장', 'seo@daehan.test', '02-3456-7890'],
  ['대한제조', '류하준', '대리', 'ryu@daehan.test', null],
  ['새론병원', '문서연', '팀장', 'moon@saeron.test', '010-7777-8888'],
  ['푸른물류', '장하은', '과장', 'jang@pureun.test', '010-2222-3333'],
  ['하늘카드', '신동혁', '차장', 'shin@haneul.test', '02-4567-8901'],
  ['하늘카드', '윤소라', '과장', 'yoon@haneul.test', '010-9999-0000'],
  ['세종에너지', '고민재', '부장', 'ko@sejong.test', '02-5678-9012'],
  ['도담건설', '안서진', '대리', 'ahn@dodam.test', '010-4444-5555'],
  ['우주항공연구원', '노현우', '책임', 'noh@kari.test', '042-123-4567'],
  ['청명대학교', '황지수', '교수', 'hwang@cmu.test', '02-6789-0123'],
  ['바른제약', '송다인', '과장', 'song@bareun.test', '010-6666-7777'],
]

/** 파트너 5사 / 7행. */
const PARTNERS: readonly Row[] = [
  ['에이원시스템', '표성호', '이사', 'pyo@aone.test', '010-1212-3434'],
  ['에이원시스템', '남궁은지', '과장', 'namgung@aone.test', '010-5656-7878'],
  ['코어테크', '민지훈', '대표', 'min@coretech.test', '02-7890-1234'],
  ['넷브릿지', '하준서', '부장', 'ha@netbridge.test', '010-8989-0101'],
  ['시큐어원', '조예린', '팀장', 'jo@secureone.test', '010-2323-4545'],
  ['디지털웨이', '구본혁', '이사', 'gu@digitalway.test', '02-8901-2345'],
  ['디지털웨이', '마서연', '대리', 'ma@digitalway.test', '010-6767-8989'],
]

export function seedContacts(env: SeedEnv, counters: Record<string, number>): Contact[] {
  const make = (kind: ContactKind, rows: readonly Row[], base: number): Contact[] =>
    rows.map(([company, name, title, email, phone], index) => {
      const at = env.at(base - index, 9)
      return { id: takeId(counters, 'ct'), kind, company, name, title, email, phone, createdAt: at, updatedAt: at }
    })
  return [...make('customer', CUSTOMERS, 280), ...make('partner', PARTNERS, 250)]
}

/** 시드 Deal 명세에서 연락처를 가리키는 키: `종류:회사/이름[/직급]`. */
export function contactKey(c: Pick<Contact, 'kind' | 'company' | 'name' | 'title'>, withTitle = false): string {
  const base = `${c.kind === 'customer' ? 'c' : 'p'}:${c.company}/${c.name}`
  return withTitle ? `${base}/${c.title}` : base
}

export function findSeedContact(contacts: readonly Contact[], key: string): Contact {
  const found = contacts.find((c) => contactKey(c) === key || contactKey(c, true) === key)
  if (!found) throw new Error(`시드 연락처 없음: ${key}`)
  return found
}
