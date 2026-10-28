import { Briefcase, FileText, House, StickyNote, Trophy, Users, type LucideIcon } from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  /** Shorter label for the phone tab bar, where width is tight. */
  shortLabel?: string
  icon: LucideIcon
  /** Match the path exactly (Home) rather than as a prefix. */
  end?: boolean
  /** On the phone tab bar; the rest go under "More". */
  inTabBar?: boolean
}

/** The app's top-level sections, in menu order. Desktop nav and phone tab bar share this. */
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Home', icon: House, end: true, inTabBar: true },
  { to: '/applications', label: 'Applications', shortLabel: 'Jobs', icon: Briefcase, inTabBar: true },
  { to: '/resumes', label: 'Resumes', icon: FileText, inTabBar: true },
  { to: '/accomplishments', label: 'Accomplishments', icon: Trophy },
  { to: '/notes', label: 'Notes', icon: StickyNote },
  { to: '/contacts', label: 'Contacts', icon: Users, inTabBar: true },
]
