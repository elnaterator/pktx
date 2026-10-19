import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { Basics, Resume } from '../../types'
import {
  addEntry,
  createResume,
  deleteResume,
  getResumeSchema,
  getResumeVersion,
  listResumes,
  removeEntry,
  reorderEntries,
  replaceResumeData,
  updateBasics,
  updateEntry,
  updateResume,
} from '../../services/api'

export interface ResumeFilters {
  tags?: string[]
  q?: string
}

export const resumeKeys = {
  all: ['resumes'] as const,
  lists: () => [...resumeKeys.all, 'list'] as const,
  list: (filters?: ResumeFilters) => [...resumeKeys.lists(), filters ?? {}] as const,
  details: () => [...resumeKeys.all, 'detail'] as const,
  detail: (id: number) => [...resumeKeys.details(), id] as const,
}

export function useResumeList(filters?: ResumeFilters) {
  return useQuery({
    queryKey: resumeKeys.list(filters),
    queryFn: () =>
      listResumes(
        filters?.tags?.length ? filters.tags : undefined,
        filters?.q || undefined,
      ),
  })
}

export function useResumeDetail(id: number | undefined) {
  return useQuery({
    queryKey: id ? resumeKeys.detail(id) : resumeKeys.details(),
    queryFn: () => getResumeVersion(id!),
    enabled: !!id,
  })
}

/** Section schemas: static per deploy, so cache for the session. */
export function useResumeSchema() {
  return useQuery({
    queryKey: [...resumeKeys.all, 'schema'] as const,
    queryFn: getResumeSchema,
    staleTime: Infinity,
  })
}

export function useResumeMutations() {
  const qc = useQueryClient()
  const invalidateResume = (id?: number) => {
    qc.invalidateQueries({ queryKey: resumeKeys.lists() })
    if (id !== undefined) qc.invalidateQueries({ queryKey: resumeKeys.detail(id) })
  }

  const create = useMutation({
    mutationFn: (label: string) => createResume(label),
    onSuccess: () => qc.invalidateQueries({ queryKey: resumeKeys.lists() }),
  })
  const remove = useMutation({
    mutationFn: (id: number) => deleteResume(id),
    onSuccess: (_d, id) => {
      qc.invalidateQueries({ queryKey: resumeKeys.lists() })
      qc.removeQueries({ queryKey: resumeKeys.detail(id) })
    },
  })
  const setDefault = useMutation({
    mutationFn: (id: number) => updateResume(id, { is_default: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: resumeKeys.all }),
  })
  const updateLabelOrTags = useMutation({
    mutationFn: ({ id, label, tags }: { id: number; label?: string; tags?: string[] }) =>
      updateResume(id, { label, tags }),
    onSuccess: (_d, { id }) => {
      invalidateResume(id)
      qc.invalidateQueries({ queryKey: ['tags'] })
    },
  })
  const replaceData = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Resume }) => replaceResumeData(id, data),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })
  const updateBasicsSection = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Basics }) => updateBasics(id, patch),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })
  const addEntryMutation = useMutation({
    mutationFn: ({
      id,
      section,
      data,
      position,
    }: {
      id: number
      section: string
      data: Record<string, unknown>
      position?: number
    }) => addEntry(id, section, data, position),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })
  const updateEntryMutation = useMutation({
    mutationFn: ({
      id,
      section,
      entryId,
      data,
    }: {
      id: number
      section: string
      entryId: string
      data: Record<string, unknown>
    }) => updateEntry(id, section, entryId, data),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })
  const removeEntryMutation = useMutation({
    mutationFn: ({ id, section, entryId }: { id: number; section: string; entryId: string }) =>
      removeEntry(id, section, entryId),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })
  const reorder = useMutation({
    mutationFn: ({ id, section, ids }: { id: number; section: string; ids: string[] }) =>
      reorderEntries(id, section, ids),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })

  return {
    create,
    remove,
    setDefault,
    updateLabelOrTags,
    replaceData,
    updateBasicsSection,
    addEntry: addEntryMutation,
    updateEntry: updateEntryMutation,
    removeEntry: removeEntryMutation,
    reorder,
  }
}
