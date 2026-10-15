/** shared/model 단위 테스트용 고정 코드 집합(시드와 같은 key·순서, 이름은 한글). 운영 코드에서 쓰지 않는다. */

import type { Code, CodeSet } from './types'

function status(order: number, key: string, name: string): Code {
  return {
    id: `cd-s${order}`,
    kind: 'status',
    key,
    name,
    order,
    locked: key === 'contract_completed',
    outcome: 'open',
    probabilityHint: null,
  }
}

function forecast(order: number, key: string, name: string, outcome: Code['outcome'], hint: string | null): Code {
  return {
    id: `cd-f${order}`,
    kind: 'forecast',
    key,
    name,
    order,
    locked: key === 'won',
    outcome,
    probabilityHint: hint,
  }
}

export function testCodes(): CodeSet {
  return {
    statuses: [
      status(1, 'prospecting', '기회발굴'),
      status(2, 'introduction', '제품소개'),
      status(3, 'poc_preparation', 'POC준비'),
      status(4, 'poc_completed', 'POC완료'),
      status(5, 'technical_evaluation', '기술평가'),
      status(6, 'price_negotiation', '가격협상'),
      status(7, 'contract_completed', '계약완료'),
    ],
    forecasts: [
      forecast(1, 'pipeline', 'Pipeline', 'open', '0–50'),
      forecast(2, 'best', 'Best', 'open', '51–75'),
      forecast(3, 'most_likely', 'Most Likely', 'open', '75–85'),
      forecast(4, 'commit', 'Commit', 'open', '85–100'),
      forecast(5, 'won', 'Won', 'won', null),
      forecast(6, 'lost', 'Lost', 'lost', null),
    ],
  }
}
