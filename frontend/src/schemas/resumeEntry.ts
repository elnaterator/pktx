import { z } from 'zod'
import { httpUrl } from './httpUrl'

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

export const contactInfoSchema = z.object({
  name: optionalTrimmed(200),
  email: optionalTrimmed()
    .pipe(z.string().email('Invalid email').optional()),
  phone: optionalTrimmed(50),
  location: optionalTrimmed(200),
  linkedin: httpUrl(),
  website: httpUrl(),
  github: httpUrl(),
})

export type ContactInfoInput = z.infer<typeof contactInfoSchema>

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
