import { z } from 'zod'

const trimmed = (max?: number) => {
  const s = z.string().trim()
  return max ? s.max(max) : s
}
const optionalTrimmed = (max?: number) =>
  trimmed(max)
    .transform((v) => v || undefined)
    .optional()

export const noteCreateSchema = z.object({
  title: trimmed(500).min(1, 'Title is required'),
  content: optionalTrimmed(),
  tags: z.array(z.string()).default([]),
})

export type NoteCreateInput = z.infer<typeof noteCreateSchema>
/** Raw form values before parsing (defaults not yet applied) — `useForm`'s first type arg. */
export type NoteFormInput = z.input<typeof noteCreateSchema>

export const noteUpdateSchema = noteCreateSchema.partial()
export type NoteUpdateInput = z.infer<typeof noteUpdateSchema>
