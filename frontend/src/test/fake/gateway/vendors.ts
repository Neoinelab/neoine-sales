/** Vendor 관리(서버 규칙): 이름 정규화·중복(대소문자 무시)·사용 중 삭제 409·쓰기 admin만. Solution 관리는 없다(Deal의 자유 텍스트). */

import type { VendorsGateway } from '../../../gateway/types'
import type { Vendor } from '../../../shared/model/types'
import { conflict, notFound, validation } from '../errors'
import { takeId, type VendorRecord } from '../store'
import { read, requireAdmin, requireUser, write, type MockContext } from './context'

const VENDOR_MAX = 100
const DUPLICATE_VENDOR = '이미 있는 Vendor 이름입니다.'

/** 소문자 이름의 코드 포인트 순, 같으면 id 순(서버와 같은 정렬). */
function byName<T extends { id: number; name: string }>(a: T, b: T): number {
  const x = a.name.toLowerCase()
  const y = b.name.toLowerCase()
  if (x !== y) return x < y ? -1 : 1
  return a.id - b.id
}

function checkName(raw: string): string {
  if (raw.includes('\u0000')) throw validation('Vendor 이름에 사용할 수 없는 문자가 있습니다.')
  const name = raw.trim()
  if (name === '') throw validation('Vendor 이름을 입력하세요.')
  if (Array.from(name).length > VENDOR_MAX) throw validation(`Vendor 이름은 ${VENDOR_MAX}자 이내로 입력하세요.`)
  return name
}

function dealCount(ctx: MockContext, vendorId: number): number {
  return ctx.store.data.deals.filter((d) => d.vendorId === vendorId).length
}

function vendorView(ctx: MockContext, record: VendorRecord): Vendor {
  return { id: record.id, name: record.name, usageCount: dealCount(ctx, record.id) }
}

function findVendor(ctx: MockContext, id: number): VendorRecord {
  const found = ctx.store.data.vendors.find((v) => v.id === id)
  if (!found) throw notFound('Vendor를 찾을 수 없습니다.')
  return found
}

function ensureUniqueVendor(ctx: MockContext, name: string, selfId?: number): void {
  const lower = name.toLowerCase()
  if (ctx.store.data.vendors.some((v) => v.id !== selfId && v.name.toLowerCase() === lower)) throw conflict(DUPLICATE_VENDOR)
}

export function createVendorsGateway(ctx: MockContext): VendorsGateway {
  return {
    list: () =>
      read(ctx, () => {
        requireUser(ctx)
        return [...ctx.store.data.vendors].sort(byName).map((v) => vendorView(ctx, v))
      }),
    create: (rawName) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const name = checkName(rawName)
        ensureUniqueVendor(ctx, name)
        const now = ctx.clock.now()
        const record: VendorRecord = { id: takeId(ctx.store.data.counters, 'vd'), name, createdAt: now, updatedAt: now }
        ctx.store.data.vendors.push(record)
        return vendorView(ctx, record)
      }),
    rename: (id, rawName) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const record = findVendor(ctx, id)
        const name = checkName(rawName)
        ensureUniqueVendor(ctx, name, id)
        record.name = name
        record.updatedAt = ctx.clock.now()
        return vendorView(ctx, record)
      }),
    remove: (id) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const record = findVendor(ctx, id)
        const usage = dealCount(ctx, id)
        if (usage > 0) throw conflict(`사용 중인 Vendor는 삭제할 수 없습니다. (Deal ${usage}건)`)
        const store = ctx.store.data
        store.vendors.splice(store.vendors.indexOf(record), 1)
      }),
  }
}

/** Deal 검증이 쓰는 Vendor 문구(서버 `validation._vendor`와 같다). */
export const UNKNOWN_VENDOR_MESSAGE = '선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.'
