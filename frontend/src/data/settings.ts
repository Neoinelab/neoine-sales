import { useMutation, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { DirectorySettings, DirectorySettingsInput, StorageSettings } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** gateway.settings.getDirectory. 키 keys.directory. admin 화면 전용. */
export function useDirectorySettings(): Query<DirectorySettings | null> {
  return useQuery<DirectorySettings | null, ApiError>({
    queryKey: keys.directory,
    queryFn: () => gateway.settings.getDirectory(),
    ...NO_RETRY,
  })
}

export interface SaveDirectoryVariables {
  input: DirectorySettingsInput
  /** 현재 관리자 비밀번호(개발용 로그인은 null). */
  password: string | null
  /** 화면이 읽은 설정 버전(낙관적 잠금). */
  expectedRevision: number
}

export interface TestDirectoryVariables {
  input: DirectorySettingsInput
  password: string | null
}

/** gateway.settings.saveDirectory. gcTime 0(비밀번호가 든 variables를 캐시에 남기지 않는다). 성공: keys.directory 무효화. */
export function useSaveDirectory(): Mutation<SaveDirectoryVariables, DirectorySettings> {
  const invalidate = useInvalidate()
  return useMutation<DirectorySettings, ApiError, SaveDirectoryVariables>({
    mutationFn: ({ input, password, expectedRevision }) => gateway.settings.saveDirectory(input, { password, expectedRevision }),
    gcTime: 0,
    onSuccess: () => invalidate(keys.directory),
  })
}

/** gateway.settings.testDirectory. gcTime 0(비밀번호). 실패는 ApiError(kind directory-verification-failed, stage). 캐시 영향 없음. */
export function useTestDirectory(): Mutation<TestDirectoryVariables> {
  return useMutation<void, ApiError, TestDirectoryVariables>({
    mutationFn: ({ input, password }) => gateway.settings.testDirectory(input, password),
    gcTime: 0,
  })
}

/** gateway.settings.getStorage. 키 keys.storage. */
export function useStorageSettings(): Query<StorageSettings | null> {
  return useQuery<StorageSettings | null, ApiError>({
    queryKey: keys.storage,
    queryFn: () => gateway.settings.getStorage(),
    ...NO_RETRY,
  })
}

/** gateway.settings.saveStorage(path). 성공: keys.storage 무효화. */
export function useSaveStorage(): Mutation<string, StorageSettings> {
  const invalidate = useInvalidate()
  return useMutation<StorageSettings, ApiError, string>({
    mutationFn: (path) => gateway.settings.saveStorage(path),
    onSuccess: () => invalidate(keys.storage),
  })
}

/** gateway.settings.testStorage(path). 캐시 영향 없음. */
export function useTestStorage(): Mutation<string> {
  return useMutation<void, ApiError, string>({ mutationFn: (path) => gateway.settings.testStorage(path) })
}
