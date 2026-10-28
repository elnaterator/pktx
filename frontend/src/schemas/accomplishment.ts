import { z } from 'zod'

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

export const accomplishmentCreateSchema = z.object({
  title: trimmed(500).min(1, 'Title is required'),
  situation: optionalTrimmed(),
  task: optionalTrimmed(),
  action: optionalTrimmed(),
  result: optionalTrimmed(),
  accomplishment_date: optionalDate,
  tags: z.array(z.string()).default([]),
})

export type AccomplishmentCreateInput = z.infer<typeof accomplishmentCreateSchema>
/** Raw form values before parsing (defaults not yet applied) — `useForm`'s first type arg. */
export type AccomplishmentFormInput = z.input<typeof accomplishmentCreateSchema>

export const accomplishmentUpdateSchema = accomplishmentCreateSchema.partial()
export type AccomplishmentUpdateInput = z.infer<typeof accomplishmentUpdateSchema>
