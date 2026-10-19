import { z } from 'zod'
import { MAX_URL_LENGTH } from './httpUrl'
import { isHttpUrl } from '../utils/safeUrl'
import type { SectionField } from '../types'

const optionalTrimmed = (max?: number) => {
  const s = z.string().trim()
  const base = max ? s.max(max) : s
  return base.transform((v) => v || undefined).optional()
}

const URL_SCHEME = /^[a-z][a-z0-9+.-]*:/i

/** Bare hosts (github.com/me) get https://, mirroring the backend. */
export function withScheme(value: string): string {
  const v = value.trim()
  return URL_SCHEME.test(v) || v.startsWith('//') ? v : `https://${v}`
}

/** Optional http(s) URL; a bare host gets `https://` like the backend does. */
const looseHttpUrl = () =>
  z
    .string()
    .trim()
    .transform((v) => (v ? withScheme(v) : undefined))
    .pipe(
      z
        .string()
        .max(MAX_URL_LENGTH)
        .refine(isHttpUrl, 'Enter a valid http(s) URL')
        .optional(),
    )
    .optional()

/** `YYYY`, `YYYY-MM` or `YYYY-MM-DD`; matches the backend's partial ISO dates. */
export const PARTIAL_DATE = /^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$/

const partialDate = () =>
  z
    .string()
    .trim()
    .transform((v) => v || undefined)
    .pipe(z.string().regex(PARTIAL_DATE, 'Use YYYY, YYYY-MM or YYYY-MM-DD').optional())
    .optional()

/**
 * Zod schema for a list section, built from the fields the section's JSON Schema
 * declares (`GET /api/resumes/schema`). Only the primary field is required in the
 * form; the API itself only needs one non-empty field.
 */
export function buildEntrySchema(fields: SectionField[], primaryField: string) {
  const shape: Record<string, z.ZodTypeAny> = {}
  for (const f of fields) {
    const required = f.name === primaryField
    if (f.widget === 'bullets') {
      shape[f.name] = z.array(z.string()).default([])
    } else if (required) {
      shape[f.name] = z.string().trim().min(1, `${f.label} is required`).max(200)
    } else if (f.widget === 'url') {
      shape[f.name] = looseHttpUrl()
    } else if (f.widget === 'date') {
      shape[f.name] = partialDate()
    } else if (f.widget === 'email') {
      shape[f.name] = z
        .string()
        .trim()
        .transform((v) => v || undefined)
        .pipe(z.string().email('Invalid email').optional())
        .optional()
    } else if (f.widget === 'textarea' || f.widget === 'tags') {
      shape[f.name] = optionalTrimmed()
    } else {
      shape[f.name] = optionalTrimmed(200)
    }
  }
  return z.object(shape)
}

/** Social networks suggested in the profile editor; any name is accepted. */
export const NETWORKS = [
  'LinkedIn',
  'GitHub',
  'GitLab',
  'X',
  'Mastodon',
  'Bluesky',
  'Stack Overflow',
  'Portfolio',
  'YouTube',
] as const

export const basicsSchema = z.object({
  name: optionalTrimmed(200),
  label: optionalTrimmed(200),
  email: z
    .string()
    .trim()
    .transform((v) => v || undefined)
    .pipe(z.string().email('Invalid email').max(500).optional())
    .optional(),
  phone: optionalTrimmed(200),
  url: looseHttpUrl(),
  city: optionalTrimmed(200),
  region: optionalTrimmed(200),
  countryCode: optionalTrimmed(200),
  summary: optionalTrimmed(),
  profiles: z
    .array(
      z.object({
        /** Form-only: the backend id, kept so edits don't re-key a profile. */
        profileId: z.string().optional(),
        network: z.string().trim().min(1, 'Network is required').max(200),
        username: optionalTrimmed(200),
        url: looseHttpUrl(),
      }),
    )
    .max(30, 'At most 30 profiles'),
})

export type BasicsFormInput = z.input<typeof basicsSchema>
export type BasicsFormOutput = z.output<typeof basicsSchema>
