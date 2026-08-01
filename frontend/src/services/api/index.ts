/**
 * Barrel re-export for all API service modules.
 *
 * Import from this module to get any API function:
 *   import * as api from '../services/api'
 *   import { listNotes, createNote } from '../services/api'
 */

export { setTokenGetter, ApiClientError } from './client'
export * from './resumes'
export * from './applications'
export * from './accomplishments'
export * from './notes'
export * from './contacts'
export * from './tags'
export * from './links'
export * from './search'
export * from './export'
