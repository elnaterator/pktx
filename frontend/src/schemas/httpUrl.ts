import { z } from 'zod'
import { isHttpUrl } from '../utils/safeUrl'

/** Mirrors the backend's `validate_http_url` length cap. */
export const MAX_URL_LENGTH = 2048

/**
 * Optional http(s) URL field: trims, maps empty to `undefined`, and rejects any
 * non-http(s) scheme (`javascript:`, `data:`, `ftp:`, ...). `z.string().url()`
 * alone accepts `javascript:alert(1)`.
 */
export const httpUrl = () =>
  z
    .string()
    .trim()
    .transform((v) => v || undefined)
    .optional()
    .pipe(
      z
        .string()
        .max(MAX_URL_LENGTH)
        .url('Invalid URL')
        .refine(isHttpUrl, 'URL must start with http:// or https://')
        .optional(),
    )
