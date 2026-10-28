import { z } from 'zod'

const optionalTrimmed = () =>
  z
    .string()
    .trim()
    .transform((v) => v || undefined)
    .optional()

const isoDate = z
  .string()
  .trim()
  .regex(/^\d{4}-\d{2}-\d{2}$/, 'Must be YYYY-MM-DD')

export const COMM_TYPES = ['email', 'phone', 'interview_note', 'other'] as const
export const COMM_DIRECTIONS = ['sent', 'received'] as const
export const COMM_STATUSES = ['draft', 'ready', 'sent', 'archived'] as const

export type CommType = (typeof COMM_TYPES)[number]
export type CommDirection = (typeof COMM_DIRECTIONS)[number]
export type CommStatus = (typeof COMM_STATUSES)[number]

/** Human-readable labels for the stored enum values. */
export const COMM_TYPE_LABELS: Record<CommType, string> = {
  email: 'Email',
  phone: 'Phone',
  interview_note: 'Interview note',
  other: 'Other',
}
/** Direction reads as Outgoing/Incoming so it never collides with the "Sent" status. */
export const COMM_DIRECTION_LABELS: Record<CommDirection, string> = {
  sent: 'Outgoing',
  received: 'Incoming',
}

/** Row label for a direction: "To Jane" / "From Jane", or Outgoing/Incoming without a name. */
export function commDirectionLabel(direction: string, contactName?: string): string {
  const first = contactName?.trim().split(/\s+/)[0]
  if (!first) return commLabel(COMM_DIRECTION_LABELS, direction)
  if (direction === 'sent') return `To ${first}`
  if (direction === 'received') return `From ${first}`
  return commLabel(COMM_DIRECTION_LABELS, direction)
}
export const COMM_STATUS_LABELS: Record<CommStatus, string> = {
  draft: 'Draft',
  ready: 'Ready',
  sent: 'Sent',
  archived: 'Archived',
}

/** Label for a stored value, falling back to the raw value for unknown ones. */
export function commLabel(labels: Record<string, string>, value: string): string {
  return labels[value] ?? value
}

export const communicationCreateSchema = z.object({
  type: z.enum(COMM_TYPES),
  direction: z.enum(COMM_DIRECTIONS),
  subject: optionalTrimmed(),
  body: optionalTrimmed(),
  date: isoDate,
  status: z.enum(COMM_STATUSES),
  tags: z.array(z.string()).default([]),
})

export type CommunicationCreateInput = z.infer<typeof communicationCreateSchema>
/** Raw form values before parsing (defaults not yet applied) — `useForm`'s first type arg. */
export type CommunicationFormInput = z.input<typeof communicationCreateSchema>

export const communicationUpdateSchema = communicationCreateSchema.partial()
export type CommunicationUpdateInput = z.infer<typeof communicationUpdateSchema>
