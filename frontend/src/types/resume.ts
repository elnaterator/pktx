/**
 * TypeScript type definitions for resume data.
 *
 * These types mirror the backend Pydantic models exactly.
 * Field names use snake_case to match the JSON API responses.
 */

import type { GroupedLinks } from './link'

export interface Profile {
  label: string
  url: string
}

export interface ContactInfo {
  name: string | null
  email: string | null
  phone: string | null
  location: string | null
  linkedin: string | null
  website: string | null
  github: string | null
  profiles: Profile[]
}

/** Stable id assigned by the backend; absent only on entries not yet saved. */
interface Entry {
  id?: string | null
}

export interface WorkExperience extends Entry {
  title: string
  company: string
  start_date: string | null
  end_date: string | null
  location: string | null
  highlights: string[]
}

export interface Education extends Entry {
  institution: string
  degree: string
  field: string | null
  start_date: string | null
  end_date: string | null
  honors: string | null
  highlights: string[]
}

export interface Skill extends Entry {
  name: string
  category: string | null
}

export interface Project extends Entry {
  name: string
  description: string | null
  url: string | null
  tech: string[]
  start_date: string | null
  end_date: string | null
  highlights: string[]
}

export interface Certification extends Entry {
  name: string
  issuer: string | null
  issued: string | null
  expires: string | null
  credential_id: string | null
  url: string | null
}

export interface Award extends Entry {
  title: string
  issuer: string | null
  date: string | null
  description: string | null
}

export interface Publication extends Entry {
  title: string
  venue: string | null
  date: string | null
  url: string | null
  description: string | null
}

export interface Volunteer extends Entry {
  role: string
  organization: string
  start_date: string | null
  end_date: string | null
  location: string | null
  highlights: string[]
}

export interface Language extends Entry {
  language: string
  proficiency: string | null
}

export interface CustomEntry extends Entry {
  heading: string | null
  body: string | null
  highlights: string[]
}

export interface CustomSection {
  title: string
  entries: CustomEntry[]
}

/** Order, visibility and optional title override for one section. */
export interface LayoutItem {
  /** Section key, or `custom:<id>` for a user-defined section. */
  section: string
  visible: boolean
  title: string | null
}

/** Generic list entry as rendered by the registry-driven section. */
export type ListEntry = Entry & Record<string, unknown>

export interface Resume {
  contact: ContactInfo
  summary: string
  experience: WorkExperience[]
  education: Education[]
  skills: Skill[]
  projects: Project[]
  certifications: Certification[]
  awards: Award[]
  publications: Publication[]
  volunteer: Volunteer[]
  languages: Language[]
  custom_sections: Record<string, CustomSection>
  layout: LayoutItem[]
}

export interface SectionField {
  name: string
  label: string
  widget: 'text' | 'textarea' | 'url' | 'bullets' | 'tags'
  required: boolean
}

/** Section definition served by `GET /api/resume-sections`. */
export interface SectionMeta {
  key: string
  label: string
  primary_field: string | null
  unique_field: string | null
  insert: 'prepend' | 'append'
  fields: SectionField[]
}

export interface ResumeVersion {
  id: number
  label: string
  is_default: boolean
  resume_data: Resume
  app_count: number
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
