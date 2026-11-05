/**
 * 라이선스 계약 샘플 데이터(테스트 전용).
 * - 시드 Deal 24건 중 Won은 11·12·24뿐이라 여러 상태·여러 Vendor를 채우려고 시드 Deal 밖의 과거 Deal(`dealSide`) 계약을 더한다.
 *   Deal이 있는 계약(11·12·24)은 Deal 값을 읽고, 없는 계약은 자기 `dealSide`를 쓴다.
 * - 날짜는 서버 시계 2027-03-15를 기준으로 고정한 절대 날짜다(계약 화면 테스트가 이 날짜로 시계를 고정한다).
 * - 규칙: Deal당 발급 상태 계약은 최대 1건, 미발급은 날짜·기간이 없고 그 밖에는 모두 있다.
 *   dated(날짜 있는) 계약 40건, 미발급 21건 = 61건 → 기본 정렬(종료일 오름차순, 날짜 없는 것은 맨 뒤) 첫 쪽(50건)에 네 상태가 모두 들어간다.
 * - 첨부는 모두 kim(김영업)이 올린 것이라 sales 로그인으로 교체·삭제를 시험할 수 있다.
 */

import { addDays } from '../../shared/model/dates'
import { licenseEnd } from '../../shared/model/licensePeriod'
import type { ContractStatus, InspectionCycle } from '../../shared/model/types'
import type { SeedEnv } from '../fake/seed/env'
import { USER_ID, type SeedLoginId } from '../fake/seed/ids'
import { takeId, type ContractAttachmentRecord, type LicenseContractRecord } from '../fake/store'
import { seedVendorId } from './vendors'

const TODAY = '2027-03-15'
const CUSTOMERS = [
  '가람전자', '나래제약', '다온물류', '라온건설', '마루식품', '바다해운', '사랑병원', '아침교육', '자연화학', '차오름미디어',
  '카페라떼푸드', '타오르는에너지', '파란항공', '하늘정보통신', '가온통신', '나비유통', '다솜금융', '라임소프트', '마음병원', '보람건설',
] as const
const VENDORS: readonly (readonly [string, string])[] = [
  ['Okta', 'WorkforceSSO'],
  ['CyberArk', 'PrivilegedPAM'],
  ['Silverfort', 'IdentityITDR'],
  ['CrowdStrike', 'FalconEDR'],
  ['Palo Alto', 'PrismaNGFW'],
  ['Tenable', 'NessusVM'],
  ['SentinelOne', 'SingularityEDR'],
  ['Zscaler', 'PrivateZTNA'],
]
const PARTNERS = ['한빛파트너스', '새벽IT', '푸른솔시스템', null] as const
const OWNERS: readonly SeedLoginId[] = ['kim', 'park', 'lee', 'jung', 'old']
const TECHS = ['박도윤', '최민재', '정유나', '', '한서진'] as const
const INSPECTIONS: readonly InspectionCycle[] = ['quarterly', 'monthly', 'semiannual', 'none', 'yearly']
const NOTES = ['', '갱신 협의 중', '', '월 1회 원격 점검', '', '이중화 구성', '']

/** 종료일이 기준일에서 며칠 뒤인 1년 계약의 시작일·종료일. */
function yearContract(endOffset: number): { start: string; end: string } {
  const [y, m, d] = addDays(TODAY, endOffset + 1).split('-').map(Number)
  const start = `${(y ?? 0) - 1}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
  return { start, end: licenseEnd(start, 1, 'year') }
}

interface Plan {
  status: ContractStatus
  /** 종료일의 기준일 대비 일수(미발급은 null). */
  endOffset: number | null
  /** 갱신 원본(종료된 이전 계약)을 함께 만든다. */
  withPrevious?: boolean
  files?: number
}

// 종료(12): 모두 지난 계약. 발급(신규)(10): 만료 임박(1개월 미만 3건·2개월 미만 2건) 포함. 발급(갱신)(8): 앞 3건은 원본 없음.
const PLANS: readonly Plan[] = [
  ...[-380, -350, -320, -290, -260, -230, -200, -170, -140, -110, -80, -50].map((o, i): Plan => ({ status: 'ended', endOffset: o, files: i === 1 || i === 4 ? 1 : 0 })),
  ...[-20, 10, 25, 40, 55, 90, 150, 220, 300, 360].map((o, i): Plan => ({ status: 'issued_new', endOffset: o, files: i === 2 || i === 5 ? 2 : 0 })),
  ...[20, 50, 200].map((o): Plan => ({ status: 'issued_renewal', endOffset: o })),
  ...[100, 140, 260, 330, 400].map((o): Plan => ({ status: 'issued_renewal', endOffset: o, withPrevious: true })),
  ...Array.from({ length: 20 }, (_, i): Plan => ({ status: 'not_issued', endOffset: null, files: i === 0 ? 1 : 0 })),
]

interface Built {
  contracts: LicenseContractRecord[]
  attachments: ContractAttachmentRecord[]
}

export function seedLicenseContracts(env: SeedEnv, deals: readonly { code: string; ownerId: number }[], counters: Record<string, number>): Built {
  const contracts: LicenseContractRecord[] = []
  const attachments: ContractAttachmentRecord[] = []
  const at = (offset: number, hour = 10) => `${addDays(TODAY, offset)}T${String(hour).padStart(2, '0')}:00:00${env.tz}`
  const add = (
    dealCode: string,
    ownerId: number,
    plan: { status: ContractStatus; end: number | null; renewedFromId?: number | null; tech: string; inspection: InspectionCycle; note: string },
    side?: LicenseContractRecord['dealSide'],
  ): LicenseContractRecord => {
    const period = plan.end === null ? null : yearContract(plan.end)
    const record: LicenseContractRecord = {
      id: takeId(counters, 'lc'),
      dealCode,
      status: plan.status,
      licenseStart: period?.start ?? null,
      licenseEnd: period?.end ?? null,
      term: period ? { amount: 1, unit: 'year' } : null,
      techOwner: plan.tech,
      inspection: plan.inspection,
      note: plan.note,
      renewedFromId: plan.renewedFromId ?? null,
      endedAt: plan.status === 'ended' ? at(plan.end ?? -1, 9) : null,
      createdById: ownerId,
      updatedById: ownerId,
      createdAt: at((plan.end ?? 0) - 365, 9),
      updatedAt: at((plan.end ?? 0) - 365, 9),
      ...(side ? { dealSide: side } : {}),
    }
    contracts.push(record)
    return record
  }
  const attach = (contract: LicenseContractRecord, count: number): void => {
    for (let n = 1; n <= count; n += 1) {
      const fileName = `계약서_${contract.id}_${n}.pdf`
      attachments.push({
        id: takeId(counters, 'lca'),
        contractId: contract.id,
        fileName,
        size: 400_000 + n * 1_000,
        mime: 'application/pdf',
        description: n === 1 ? '서명 완료본' : '',
        uploadedById: USER_ID.kim,
        uploadedAt: at(-40 - n, 14),
        content: `[목업 더미 내용] ${fileName}`,
      })
    }
  }

  // Deal이 있는 Won 계약: 11(청명대학교)은 종료 2건 뒤 발급(갱신), 12는 미발급, 24는 종료 뒤 발급(신규)다. 24의 발급(신규)가 가장 먼저 만료되므로 기본 정렬의 첫 발급(신규)는 실제 Deal에 속한다.
  const real = (suffix: string) => {
    const deal = deals.find((d) => d.code.endsWith(suffix))
    if (!deal) throw new Error(`시드 Deal 없음: ${suffix}`)
    return deal
  }
  const d11 = real('-D011')
  const first = add(d11.code, d11.ownerId, { status: 'ended', end: -700, tech: '박도윤', inspection: 'quarterly', note: '' })
  const second = add(d11.code, d11.ownerId, { status: 'ended', end: -335, renewedFromId: first.id, tech: '박도윤', inspection: 'quarterly', note: '' })
  attach(add(d11.code, d11.ownerId, { status: 'issued_renewal', end: 180, renewedFromId: second.id, tech: '박도윤', inspection: 'quarterly', note: '갱신 완료' }), 1)
  const d12 = real('-D012')
  add(d12.code, d12.ownerId, { status: 'not_issued', end: null, tech: '', inspection: 'none', note: '' })
  const d24 = real('-D024')
  const old = add(d24.code, d24.ownerId, { status: 'ended', end: -395, tech: '최민재', inspection: 'monthly', note: '' })
  add(d24.code, d24.ownerId, { status: 'issued_new', end: -30, renewedFromId: old.id, tech: '최민재', inspection: 'monthly', note: '' })

  // Deal 밖의 과거 계약.
  PLANS.forEach((plan, index) => {
    const [vendorName, product] = VENDORS[index % VENDORS.length] ?? VENDORS[0]!
    const owner = USER_ID[OWNERS[index % OWNERS.length] ?? 'kim']
    const customer = CUSTOMERS[index % CUSTOMERS.length] ?? CUSTOMERS[0]
    const dealCode = `2025${String((index % 12) + 1).padStart(2, '0')}01-L${String(index + 1).padStart(3, '0')}`
    const side = {
      dealName: `${customer} ${product}`,
      customer,
      vendorId: seedVendorId(vendorName),
      product,
      partner: PARTNERS[index % PARTNERS.length] ?? null,
      ownerId: owner,
    }
    const body = {
      tech: TECHS[index % TECHS.length] ?? '',
      inspection: INSPECTIONS[index % INSPECTIONS.length] ?? 'none',
      note: NOTES[index % NOTES.length] ?? '',
    }
    const endOffset = plan.endOffset
    const previous =
      plan.withPrevious && endOffset !== null ? add(dealCode, owner, { status: 'ended', end: endOffset - 365, ...body }, side) : null
    const main = add(dealCode, owner, { status: plan.status, end: endOffset, renewedFromId: previous?.id ?? null, ...body }, side)
    if (plan.files) attach(main, plan.files)
  })
  return { contracts, attachments }
}
