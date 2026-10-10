import type { CustomSection, LayoutItem, SectionMeta } from '../../types'

export const CUSTOM_PREFIX = 'custom:'

/** Heading of a section before any layout title override. */
export function defaultTitle(
  section: string,
  sections: SectionMeta[],
  customSections: Record<string, CustomSection>,
): string {
  if (section === 'summary') return 'Summary'
  if (section.startsWith(CUSTOM_PREFIX)) {
    return customSections[section.slice(CUSTOM_PREFIX.length)]?.title ?? 'Custom'
  }
  return sections.find((s) => s.key === section)?.label ?? section
}

export function displayTitle(
  item: LayoutItem,
  sections: SectionMeta[],
  customSections: Record<string, CustomSection>,
): string {
  return item.title || defaultTitle(item.section, sections, customSections)
}
