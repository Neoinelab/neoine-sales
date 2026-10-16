import { api } from '../../shared/api/client'
import type { UsersGateway } from '../types'
import { toUser, toUserRef } from './mappers/user'
import { unwrap } from './request'

/** 서버 목록 한 번에 받을 수 있는 최대 개수. */
const MAX_PAGE = 200
/** 서버가 끝을 알려 주지 않을 때를 위한 안전장치(200 x 50 = 1만 명). */
const MAX_PAGES = 50

interface Page<T> {
  items: T[]
  limit: number
}

/**
 * 서버 목록 응답은 `{ items, offset, limit }`뿐이고 전체 개수가 없다.
 * 가득 찬 페이지(items가 limit개)가 오는 동안 offset을 늘려 이어 읽고, 덜 찬(또는 빈) 페이지에서 멈춘다.
 */
async function readAll<T>(fetchPage: (offset: number | undefined) => Promise<Page<T>>): Promise<T[]> {
  const all: T[] = []
  let offset: number | undefined
  for (let n = 0; n < MAX_PAGES; n += 1) {
    const page = await fetchPage(offset)
    all.push(...page.items)
    if (page.items.length === 0 || page.items.length < page.limit) break
    offset = all.length
  }
  return all
}

export function createUsersHttp(): UsersGateway {
  return {
    list: async (filter) =>
      (
        await readAll((offset) =>
          unwrap(api.GET('/api/v1/users', { params: { query: { status: filter, limit: MAX_PAGE, offset } } })),
        )
      ).map(toUser),
    // /user-options는 limit·offset 없이 전체를 한 번에 돌려준다. items만 사용한다.
    options: async (query) =>
      (
        await unwrap(
          api.GET('/api/v1/user-options', {
            params: { query: { include_resigned: query.includeResigned ?? false, role: query.role } },
          }),
        )
      ).items.map(toUserRef),
    create: async (input) =>
      toUser(
        await unwrap(
          api.POST('/api/v1/users', { body: { login_id: input.loginId, role: input.role, display_name: input.name } }),
        ),
      ),
    remove: (id) => unwrap(api.DELETE('/api/v1/users/{user_id}', { params: { path: { user_id: id } } })),
  }
}
