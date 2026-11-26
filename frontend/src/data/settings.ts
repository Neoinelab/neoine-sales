import { useMutation, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { DirectoryTestResult } from '../gateway/types'
import type { ApiError } from '../shared/api/problem'
import type { DirectorySettings, DirectorySaveInput, DirectoryTestInput, StorageSettings } from '../shared/model/types'
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
  readonly input: DirectorySaveInput
  readonly expectedRevision: number | null
}

/** 성공하면 저장된 설정을 갱신한다. */
export function useSaveDirectory(): Mutation<SaveDirectoryVariables, DirectorySettings> {
  const invalidate = useInvalidate()
  return useMutation<DirectorySettings, ApiError, SaveDirectoryVariables>({
    mutationFn: ({ input, expectedRevision }) => gateway.settings.saveDirectory(input, { expectedRevision }),
    gcTime: 0,
    onSuccess: () => invalidate(keys.directory),
  })
}

/** 테스트 자격 증명은 대화상자를 닫거나 요청이 끝나면 즉시 제거한다. */
export function useTestDirectory(): Mutation<DirectoryTestInput, DirectoryTestResult> {
  return useMutation<DirectoryTestResult, ApiError, DirectoryTestInput>({
    mutationFn: (input) => gateway.settings.testDirectory(input),
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
