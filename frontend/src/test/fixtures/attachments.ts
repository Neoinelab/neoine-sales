import { extensionOf } from '../../shared/model/fileRules'
import type { Deal } from '../../shared/model/types'
import { nextSeq, takeId, type AttachmentRecord, type HistoryRecord } from '../fake/store'
import type { SeedEnv } from '../fake/seed/env'

/** [Deal 번호, 파일명, 크기(byte), 업로더 loginId, 며칠 전, 설명]. 삭제 권한 시나리오(본인/타인/퇴사자)는 Deal 1에 모았다. */
const FILES: readonly (readonly [number, string, number, string, number, string])[] = [
  [1, '견적서_한빛은행_v2.pdf', 2_400_000, 'kim', 25, '2차 견적서'],
  [1, '제안서_ITDR.pptx', 8_100_000, 'park', 18, 'ITDR 제안서(공유용)'],
  [1, '기술검토.xlsx', 310_000, 'old', 26, '기술 검토 결과 정리'],
  [7, 'POC결과서.pdf', 1_800_000, 'kim', 30, 'POC 결과 보고'],
  [10, '견적서.pdf', 1_200_000, 'park', 12, ''],
  [10, '계약조건.docx', 450_000, 'park', 6, '협의 중인 계약 조건'],
  [21, '견적서_청명대_EDR.pdf', 980_000, 'lee', 9, ''],
  [23, '고객요건.docx', 520_000, 'old', 30, '고객 요건 정리'],
]

const MIME: Record<string, string> = {
  pdf: 'application/pdf',
  pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}

export function seedAttachments(
  env: SeedEnv,
  deals: readonly Deal[],
  counters: Record<string, number>,
): { attachments: AttachmentRecord[]; history: HistoryRecord[] } {
  const attachments: AttachmentRecord[] = []
  const history: HistoryRecord[] = []
  for (const [no, fileName, size, uploader, ago, description] of FILES) {
    const deal = deals.find((d) => d.code.endsWith(`-D${String(no).padStart(3, '0')}`))
    if (!deal) throw new Error(`시드 Deal 없음: ${no}`)
    const uploadedAt = env.at(ago, 15)
    const uploadedById = `u-${uploader}`
    attachments.push({
      id: takeId(counters, 'att'),
      dealCode: deal.code,
      fileName,
      size,
      mime: MIME[extensionOf(fileName)] ?? 'application/octet-stream',
      description,
      uploadedById,
      uploadedAt,
      content: `[목업 더미 내용] ${fileName}`,
    })
    history.push({
      id: takeId(counters, 'hi'),
      seq: nextSeq(counters),
      dealCode: deal.code,
      at: uploadedAt,
      byId: uploadedById,
      category: 'attachment',
      target: '첨부 파일',
      before: '',
      after: `업로드 ${fileName}`,
    })
  }
  return { attachments, history }
}
