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

const optionalDate = z
  .string()
  .trim()
  .regex(/^\d{4}-\d{2}-\d{2}$/, 'Must be YYYY-MM-DD')
  .transform((v) => v || undefined)
  .optional()
  .or(z.literal('').transform(() => undefined))

export const contactCreateSchema = z.object({
  name: trimmed(200).min(1, 'Name is required'),
  email: optionalTrimmed()
    .pipe(z.string().email('Invalid email').optional()),
  phone: optionalTrimmed(50),
  company: optionalTrimmed(200),
  title: optionalTrimmed(200),
  relationship: optionalTrimmed(200),
  linkedin_url: httpUrl(),
  location: optionalTrimmed(200),
  last_contacted_date: optionalDate,
  followup_date: optionalDate,
  notes: optionalTrimmed(),
  tags: z.array(z.string()).default([]),
})

export type ContactCreateInput = z.infer<typeof contactCreateSchema>

export const contactUpdateSchema = contactCreateSchema.partial()
export type ContactUpdateInput = z.infer<typeof contactUpdateSchema>
