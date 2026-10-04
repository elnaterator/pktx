import { z } from 'zod'
import { httpUrl } from './httpUrl'

const trimmed = (max?: number) => {
  const s = z.string().trim()
  return max ? s.max(max) : s
}
const optionalTrimmed = (max?: number) =>
  trimmed(max)
    .transform((v) => v || undefined)
    .optional()

export const APPLICATION_STATUSES = [
  'Interested',
  'Applied',
  'Phone Screen',
  'Interview',
  'Offer',
  'Rejected',
  'Withdrawn',
  'Accepted',
] as const

export const applicationCreateSchema = z.object({
  company: trimmed(200).min(1, 'Company is required'),
  position: trimmed(200).min(1, 'Position is required'),
  status: z.enum(APPLICATION_STATUSES).default('Interested'),
  url: httpUrl(),
  description: optionalTrimmed(),
  notes: optionalTrimmed(),
  tags: z.array(z.string()).default([]),
})

export type ApplicationCreateInput = z.infer<typeof applicationCreateSchema>

export const applicationUpdateSchema = applicationCreateSchema.partial()
export type ApplicationUpdateInput = z.infer<typeof applicationUpdateSchema>
