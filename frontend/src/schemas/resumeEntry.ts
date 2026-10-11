import { z } from 'zod'
import { MAX_URL_LENGTH, httpUrl, requiredHttpUrl } from './httpUrl'
import { isHttpUrl } from '../utils/safeUrl'
import type { ContactKind, SectionField } from '../types'

const optionalTrimmed = (max?: number) => {
  const s = z.string().trim()
  const base = max ? s.max(max) : s
  return base.transform((v) => v || undefined).optional()
}

const optionalFreeDate = z
  .string()
  .trim()
  .transform((v) => v || undefined)
  .optional()

const URL_SCHEME = /^[a-z][a-z0-9+.-]*:/i

/** Bare hosts (github.com/me) get https://, mirroring the backend. */
export function withScheme(value: string): string {
  const v = value.trim()
  return URL_SCHEME.test(v) || v.startsWith('//') ? v : `https://${v}`
}

const contactFieldSchema = (kindOf: (key: string) => ContactKind) =>
  z
    .object({
      key: z.string().trim().min(1, 'Key is required').max(200),
      value: z.string().trim().min(1, 'Value is required'),
      /** Form-only: the key is user-typed rather than a preset. Not sent. */
      custom: z.boolean().optional(),
    })
    .superRefine((f, ctx) => {
      const kind = kindOf(f.key)
      if (kind === 'email' && !z.string().email().safeParse(f.value).success) {
        ctx.addIssue({ code: 'custom', path: ['value'], message: 'Invalid email' })
      } else if (kind === 'url' && !isHttpUrl(withScheme(f.value))) {
        ctx.addIssue({ code: 'custom', path: ['value'], message: 'Enter a valid http(s) URL' })
      } else if (f.value.length > (kind === 'url' ? MAX_URL_LENGTH : 500)) {
        ctx.addIssue({ code: 'custom', path: ['value'], message: 'Value is too long' })
      }
    })
    .transform((f) => ({
      key: f.key,
      value: kindOf(f.key) === 'url' ? withScheme(f.value) : f.value,
      custom: f.custom,
    }))

/**
 * Contact form: name/phone/location plus key/value details. `kindOf` maps a key
 * to how its value is validated (presets are email/url, anything else is text).
 */
export function buildContactSchema(kindOf: (key: string) => ContactKind) {
  return z
    .object({
      name: optionalTrimmed(200),
      phone: optionalTrimmed(500),
      location: optionalTrimmed(500),
      fields: z.array(contactFieldSchema(kindOf)).max(30, 'At most 30 details').default([]),
    })
    .superRefine((data, ctx) => {
      const seen = new Set<string>()
      data.fields.forEach((f, i) => {
        const folded = f.key.toLowerCase()
        if (seen.has(folded)) {
          ctx.addIssue({ code: 'custom', path: ['fields', i, 'key'], message: 'Duplicate key' })
        }
        seen.add(folded)
      })
    })
}

export type ContactFormInput = z.input<ReturnType<typeof buildContactSchema>>

export const summarySchema = z.object({
  summary: z.string().trim().min(1, 'Summary cannot be empty'),
})

export type SummaryInput = z.infer<typeof summarySchema>

export const workExperienceSchema = z.object({
  title: z.string().trim().min(1, 'Title is required').max(200),
  company: z.string().trim().min(1, 'Company is required').max(200),
  start_date: optionalFreeDate,
  end_date: optionalFreeDate,
  location: optionalTrimmed(200),
  highlights: z.array(z.string()).default([]),
})

export type WorkExperienceInput = z.infer<typeof workExperienceSchema>

export const educationSchema = z.object({
  institution: z.string().trim().min(1, 'Institution is required').max(200),
  degree: z.string().trim().min(1, 'Degree is required').max(200),
  field: optionalTrimmed(200),
  start_date: optionalFreeDate,
  end_date: optionalFreeDate,
  honors: optionalTrimmed(200),
  highlights: z.array(z.string()).default([]),
})

export type EducationInput = z.infer<typeof educationSchema>

export const skillSchema = z.object({
  name: z.string().trim().min(1, 'Skill name is required').max(200),
  category: optionalTrimmed(200),
})

export type SkillInput = z.infer<typeof skillSchema>

/**
 * Zod schema for a registry-defined list section, built from the field
 * descriptors served by `GET /api/resume-sections`.
 */
export function buildEntrySchema(fields: SectionField[]) {
  const shape: Record<string, z.ZodTypeAny> = {}
  for (const f of fields) {
    if (f.widget === 'bullets') {
      shape[f.name] = z.array(z.string()).default([])
    } else if (f.widget === 'url') {
      shape[f.name] = f.required
        ? requiredHttpUrl(`${f.label} is required`)
        : httpUrl()
    } else if (f.widget === 'textarea') {
      shape[f.name] = f.required
        ? z.string().trim().min(1, `${f.label} is required`)
        : optionalTrimmed()
    } else {
      shape[f.name] = f.required
        ? z.string().trim().min(1, `${f.label} is required`).max(200)
        : f.widget === 'tags'
          ? optionalTrimmed()
          : optionalFreeDate
    }
  }
  return z.object(shape)
}
