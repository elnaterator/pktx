import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ContactInfo, LayoutItem } from '../../types'
import {
  addCustomSection,
  addVersionEntry,
  createResume,
  deleteResume,
  getResumeVersion,
  listResumeSections,
  listResumes,
  removeCustomSection,
  removeVersionEntry,
  setDefaultResume,
  updateResumeLabel,
  updateVersionContact,
  updateVersionEntry,
  updateVersionLayout,
  updateVersionSummary,
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

/** Section registry: static per deploy, so cache for the session. */
export function useResumeSections() {
  return useQuery({
    queryKey: [...resumeKeys.all, 'sections'] as const,
    queryFn: listResumeSections,
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
    mutationFn: (id: number) => setDefaultResume(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: resumeKeys.all }),
  })
  const updateLabelOrTags = useMutation({
    mutationFn: ({ id, label, tags }: { id: number; label: string; tags?: string[] }) =>
      updateResumeLabel(id, label, tags),
    onSuccess: (_d, { id }) => {
      invalidateResume(id)
      qc.invalidateQueries({ queryKey: ['tags'] })
    },
  })
  const updateContactSection = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<ContactInfo> }) =>
      updateVersionContact(id, data),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })
  const updateSummarySection = useMutation({
    mutationFn: ({ id, text }: { id: number; text: string }) =>
      updateVersionSummary(id, text),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })
  const addEntry = useMutation({
    mutationFn: ({
      id,
      section,
      data,
    }: {
      id: number
      section: string
      data: Record<string, unknown>
    }) => addVersionEntry(id, section, data),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })
  const updateEntry = useMutation({
    mutationFn: ({
      id,
      section,
      entryRef,
      data,
    }: {
      id: number
      section: string
      entryRef: string | number
      data: Record<string, unknown>
    }) => updateVersionEntry(id, section, entryRef, data),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })
  const removeEntry = useMutation({
    mutationFn: ({
      id,
      section,
      entryRef,
    }: {
      id: number
      section: string
      entryRef: string | number
    }) => removeVersionEntry(id, section, entryRef),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })
  const updateLayout = useMutation({
    mutationFn: ({ id, layout }: { id: number; layout: LayoutItem[] }) =>
      updateVersionLayout(id, layout),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })
  const addCustom = useMutation({
    mutationFn: ({ id, title }: { id: number; title: string }) =>
      addCustomSection(id, title),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })
  const removeCustom = useMutation({
    mutationFn: ({ id, customId }: { id: number; customId: string }) =>
      removeCustomSection(id, customId),
    onSuccess: (_d, { id }) => invalidateResume(id),
  })

  return {
    create,
    remove,
    setDefault,
    updateLabelOrTags,
    updateContactSection,
    updateSummarySection,
    addEntry,
    updateEntry,
    removeEntry,
    updateLayout,
    addCustom,
    removeCustom,
  }
}
