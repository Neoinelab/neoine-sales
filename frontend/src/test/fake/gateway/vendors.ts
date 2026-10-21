/** Vendor·Solution 관리(서버 규칙): 이름 정규화·중복(대소문자 무시)·사용 중 삭제 409·Vendor 삭제 시 소속 Solution 함께 삭제·쓰기 admin만. */

import type { VendorsGateway } from '../../../gateway/types'
import type { Solution, Vendor } from '../../../shared/model/types'
import { conflict, notFound, validation } from '../errors'
import { takeId, type SolutionRecord, type VendorRecord } from '../store'
import { read, requireAdmin, requireUser, write, type MockContext } from './context'

const VENDOR_MAX = 100
const SOLUTION_MAX = 200
const DUPLICATE_VENDOR = '이미 있는 Vendor 이름입니다.'
const DUPLICATE_SOLUTION = '이 Vendor에 이미 있는 Solution 이름입니다.'

/** 소문자 이름의 코드 포인트 순, 같으면 id 순(서버와 같은 정렬). */
function byName<T extends { id: number; name: string }>(a: T, b: T): number {
  const x = a.name.toLowerCase()
  const y = b.name.toLowerCase()
  if (x !== y) return x < y ? -1 : 1
  return a.id - b.id
}

function checkName(kind: 'Vendor' | 'Solution', raw: string, max: number): string {
  if (raw.includes('\u0000')) throw validation(`${kind} 이름에 사용할 수 없는 문자가 있습니다.`)
  const name = raw.trim()
  if (name === '') throw validation(`${kind} 이름을 입력하세요.`)
  if (Array.from(name).length > max) throw validation(`${kind} 이름은 ${max}자 이내로 입력하세요.`)
  return name
}

function dealCount(ctx: MockContext, pick: (d: { vendorId: number | null; solutionId: number | null }) => number | null, id: number): number {
  return ctx.store.data.deals.filter((d) => pick(d) === id).length
}

function solutionView(ctx: MockContext, record: SolutionRecord): Solution {
  return { id: record.id, vendorId: record.vendorId, name: record.name, usageCount: dealCount(ctx, (d) => d.solutionId, record.id) }
}

function vendorView(ctx: MockContext, record: VendorRecord): Vendor {
  return {
    id: record.id,
    name: record.name,
    usageCount: dealCount(ctx, (d) => d.vendorId, record.id),
    solutions: ctx.store.data.solutions
      .filter((s) => s.vendorId === record.id)
      .sort(byName)
      .map((s) => solutionView(ctx, s)),
  }
}

function findVendor(ctx: MockContext, id: number): VendorRecord {
  const found = ctx.store.data.vendors.find((v) => v.id === id)
  if (!found) throw notFound('Vendor를 찾을 수 없습니다.')
  return found
}

function findSolution(ctx: MockContext, vendorId: number, id: number): SolutionRecord {
  findVendor(ctx, vendorId)
  const found = ctx.store.data.solutions.find((s) => s.id === id && s.vendorId === vendorId)
  if (!found) throw notFound('Solution을 찾을 수 없습니다.')
  return found
}

function ensureUniqueVendor(ctx: MockContext, name: string, selfId?: number): void {
  const lower = name.toLowerCase()
  if (ctx.store.data.vendors.some((v) => v.id !== selfId && v.name.toLowerCase() === lower)) throw conflict(DUPLICATE_VENDOR)
}

function ensureUniqueSolution(ctx: MockContext, vendorId: number, name: string, selfId?: number): void {
  const lower = name.toLowerCase()
  if (ctx.store.data.solutions.some((s) => s.vendorId === vendorId && s.id !== selfId && s.name.toLowerCase() === lower)) {
    throw conflict(DUPLICATE_SOLUTION)
  }
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
        const name = checkName('Vendor', rawName, VENDOR_MAX)
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
        const name = checkName('Vendor', rawName, VENDOR_MAX)
        ensureUniqueVendor(ctx, name, id)
        record.name = name
        record.updatedAt = ctx.clock.now()
        return vendorView(ctx, record)
      }),
    remove: (id) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const record = findVendor(ctx, id)
        const usage = dealCount(ctx, (d) => d.vendorId, id)
        if (usage > 0) throw conflict(`사용 중인 Vendor는 삭제할 수 없습니다. (Deal ${usage}건)`)
        const store = ctx.store.data
        store.solutions = store.solutions.filter((s) => s.vendorId !== id)
        store.vendors.splice(store.vendors.indexOf(record), 1)
      }),
    createSolution: (vendorId, rawName) =>
      write(ctx, () => {
        requireAdmin(ctx)
        findVendor(ctx, vendorId)
        const name = checkName('Solution', rawName, SOLUTION_MAX)
        ensureUniqueSolution(ctx, vendorId, name)
        const now = ctx.clock.now()
        const record: SolutionRecord = { id: takeId(ctx.store.data.counters, 'sl'), vendorId, name, createdAt: now, updatedAt: now }
        ctx.store.data.solutions.push(record)
        return solutionView(ctx, record)
      }),
    renameSolution: (vendorId, solutionId, rawName) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const record = findSolution(ctx, vendorId, solutionId)
        const name = checkName('Solution', rawName, SOLUTION_MAX)
        ensureUniqueSolution(ctx, vendorId, name, solutionId)
        record.name = name
        record.updatedAt = ctx.clock.now()
        return solutionView(ctx, record)
      }),
    removeSolution: (vendorId, solutionId) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const record = findSolution(ctx, vendorId, solutionId)
        const usage = dealCount(ctx, (d) => d.solutionId, solutionId)
        if (usage > 0) throw conflict(`사용 중인 Solution은 삭제할 수 없습니다. (Deal ${usage}건)`)
        const store = ctx.store.data
        store.solutions.splice(store.solutions.indexOf(record), 1)
      }),
  }
}

/** Deal 검증이 쓰는 조회(서버 `validation._vendor_choice`와 같은 순서·문구). */
export const UNKNOWN_VENDOR_MESSAGE = '선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.'
export const SOLUTION_MISMATCH_MESSAGE = '선택한 Solution은 이 Vendor에 속하지 않습니다.'
export const SOLUTION_NEEDS_VENDOR_MESSAGE = 'Solution을 선택하려면 Vendor를 먼저 선택하세요.'
