/** Deal 등록·수정의 BANT 선택 객체(`{id}` | `{name}` | null) 처리: 서버의 판정(검증)과 확정(Label 생성)을 나눠 따른다. */

import { BANT_CATEGORIES, BANT_LABEL_MAX_LENGTH, type BantCategory } from '../../../shared/model/constants'
import type { CatalogChoice } from '../../../shared/model/catalogChoice'
import { validation } from '../errors'
import { takeId, type LabelRecord } from '../store'
import type { MockContext } from './context'

export type BantChoices = Partial<Record<BantCategory, CatalogChoice | null>>

export interface BantDraft {
  /** id로 고른 것(선택 안 함 포함) 또는 이미 있는 이름과 같아 그 Label을 쓰는 것. */
  chosen: Record<BantCategory, string | null>
  /** 같은 구분에 없어서 저장할 때 만들 이름(정규화됨). */
  newNames: Partial<Record<BantCategory, string>>
}

const INVALID_LABEL = 'BANT Label이 올바르지 않습니다.'

function normalizeName(raw: string): string {
  if (raw.includes('\0')) throw validation('Label 이름에 사용할 수 없는 문자가 있습니다.')
  const name = raw.trim()
  if (name === '') throw validation('Label 이름을 입력하세요.')
  if (Array.from(name).length > BANT_LABEL_MAX_LENGTH) throw validation(`Label 이름은 ${BANT_LABEL_MAX_LENGTH}자 이내로 입력하세요.`)
  return name
}

/** 저장소를 바꾸지 않고 판정만 한다. 틀린 id·다른 구분의 id·이름 규칙 위반은 422. */
export function checkBant(ctx: MockContext, bant: BantChoices): BantDraft {
  const { labels } = ctx.store.data
  const chosen = { budget: null, authority: null, need: null, timeline: null } as Record<BantCategory, string | null>
  const newNames: BantDraft['newNames'] = {}
  for (const category of BANT_CATEGORIES) {
    const choice = bant[category]
    if (!choice) continue
    if ('id' in choice) {
      if (!labels.some((l) => l.id === choice.id && l.category === category)) throw validation(INVALID_LABEL)
      chosen[category] = choice.id
      continue
    }
    const name = normalizeName(choice.name)
    const same = labels.find((l) => l.category === category && l.name.toLowerCase() === name.toLowerCase())
    if (same) chosen[category] = same.id
    else newNames[category] = name
  }
  return { chosen, newNames }
}

/** 검증을 모두 마친 뒤에만 부른다. 새 이름마다 그 구분에 Label을 만들고 최종 선택(id)을 돌려준다. */
export function commitBant(ctx: MockContext, draft: BantDraft, actorId: string): Record<BantCategory, string | null> {
  const result = { ...draft.chosen }
  for (const category of BANT_CATEGORIES) {
    const name = draft.newNames[category]
    if (name === undefined) continue
    const record: LabelRecord = {
      id: takeId(ctx.store.data.counters, 'lb'),
      category,
      name,
      isDefault: false,
      createdById: actorId,
      createdAt: ctx.clock.now(),
    }
    ctx.store.data.labels.push(record)
    result[category] = record.id
  }
  return result
}
