/** 상세 화면 테스트 도우미(운영 코드에서 쓰지 않는다). 시드 Deal 번호(계획 4.3) → 상세 경로. */
import { gateway } from '../gateway'
import { mockControl } from './fake/default'

/** 시드로 되돌린 뒤 Deal 번호(1~24)의 code를 찾는다. `renderAt`이 다시 시드로 되돌리므로 code는 같다. */
export async function dealCodeOf(no: number): Promise<string> {
  mockControl.resetData()
  await gateway.auth.quickLogin('u-root')
  const page = await gateway.deals.list({ limit: 100 })
  const found = page.items.find((d) => d.code.endsWith(`-D${String(no).padStart(3, '0')}`))
  if (!found) throw new Error(`시드 Deal ${no} 없음`)
  return found.code
}

export async function detailPath(no: number, query = ''): Promise<string> {
  return `/deals/${await dealCodeOf(no)}${query}`
}
