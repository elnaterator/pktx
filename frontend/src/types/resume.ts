/**
 * TypeScript types for resumes.
 *
 * A resume version is an envelope (`id`, `label`, `tags`, ...) around a JSON
 * Resume document (`data`, jsonresume.org v1.0.0, camelCase). Empty sections
 * are omitted, so every section is optional. The only non-spec field is the
 * stable `id` the backend gives every entry and profile.
 */

import type { GroupedLinks } from './link'

/** Stable id assigned by the backend; absent only on entries not yet saved. */
interface Entry {
  id?: string
}

export interface Location {
  address?: string
  postalCode?: string
  city?: string
  countryCode?: string
  region?: string
}

export interface Profile extends Entry {
  network?: string
  username?: string
  url?: string
}

export interface Basics {
  name?: string
  label?: string
  image?: string
  email?: string
  phone?: string
  url?: string
  summary?: string
  location?: Location
  profiles?: Profile[]
}

export interface Work extends Entry {
  name?: string
  location?: string
  description?: string
  position?: string
  url?: string
  startDate?: string
  endDate?: string
  summary?: string
  highlights?: string[]
}

export interface Volunteer extends Entry {
  organization?: string
  position?: string
  url?: string
  startDate?: string
  endDate?: string
  summary?: string
  highlights?: string[]
}

export interface Education extends Entry {
  institution?: string
  url?: string
  area?: string
  studyType?: string
  startDate?: string
  endDate?: string
  score?: string
  courses?: string[]
}

export interface Award extends Entry {
  title?: string
  date?: string
  awarder?: string
  summary?: string
}

export interface Certificate extends Entry {
  name?: string
  date?: string
  url?: string
  issuer?: string
}

export interface Publication extends Entry {
  name?: string
  publisher?: string
  releaseDate?: string
  url?: string
  summary?: string
}

/** A group of skills, e.g. `{ name: 'Languages', keywords: ['Go', 'Python'] }`. */
export interface Skill extends Entry {
  name?: string
  level?: string
  keywords?: string[]
}

export interface Language extends Entry {
  language?: string
  fluency?: string
}

export interface Interest extends Entry {
  name?: string
  keywords?: string[]
}

export interface Reference extends Entry {
  name?: string
  reference?: string
}

export interface Project extends Entry {
  name?: string
  description?: string
  highlights?: string[]
  keywords?: string[]
  startDate?: string
  endDate?: string
  url?: string
  roles?: string[]
  entity?: string
  type?: string
}

export interface Meta {
  canonical?: string
  version?: string
  lastModified?: string
}

/** The JSON Resume document stored in `ResumeVersion.data`. */
export interface Resume {
  basics?: Basics
  work?: Work[]
  volunteer?: Volunteer[]
  education?: Education[]
  awards?: Award[]
  certificates?: Certificate[]
  publications?: Publication[]
  skills?: Skill[]
  languages?: Language[]
  interests?: Interest[]
  references?: Reference[]
  projects?: Project[]
  meta?: Meta
}

/** Keys of the list sections (everything except `basics` and `meta`). */
export type ListSectionKey = Exclude<keyof Resume, 'basics' | 'meta'>

/** Generic list entry as rendered by the schema-driven section. */
export type ListEntry = Entry & Record<string, unknown>

export type Widget = 'text' | 'textarea' | 'url' | 'bullets' | 'tags' | 'date' | 'email'

/** The slice of a JSON Schema property the UI reads. */
export interface SchemaProperty {
  title?: string
  widget?: Widget
  type?: string
}

/** One entry of `GET /api/resumes/schema`. */
export interface SectionMeta {
  key: string
  label: string
  kind: 'object' | 'list'
  primaryField: string
  schema: { properties: Record<string, SchemaProperty> }
}

/** A form field derived from a section's JSON Schema. */
export interface SectionField {
  name: string
  label: string
  widget: Widget
}

export interface ResumeVersion {
  id: number
  label: string
  is_default: boolean
  data: Resume
  app_count?: number
  tags: string[]
  created_at: string
  updated_at: string
  links: GroupedLinks
}

export interface ResumeVersionSummary {
  id: number
  label: string
  is_default: boolean
  app_count: number
  tags: string[]
  created_at: string
  updated_at: string
  link_count?: number
}
