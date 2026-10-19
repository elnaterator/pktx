import { NavLink } from 'react-router'
import { House, FileText, Briefcase, Trophy, StickyNote, Users } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import styles from './Navigation.module.css'

function navClass({ isActive }: { isActive: boolean }) {
  return `${styles.navItem}${isActive ? ` ${styles.active}` : ''}`
}

export default function Navigation() {
  return (
    <nav className={styles.nav} aria-label="Main navigation">
      <NavLink to="/" end className={navClass}>
        <House size={ICON_SIZE.lg} />
        Home
      </NavLink>
      <NavLink to="/applications" className={navClass} end={false}>
        <Briefcase size={ICON_SIZE.lg} />
        Applications
      </NavLink>
      <NavLink to="/resumes" className={navClass} end={false}>
        <FileText size={ICON_SIZE.lg} />
        Resumes
      </NavLink>
      <NavLink to="/accomplishments" className={navClass} end={false}>
        <Trophy size={ICON_SIZE.lg} />
        Accomplishments
      </NavLink>
      <NavLink to="/notes" className={navClass} end={false}>
        <StickyNote size={ICON_SIZE.lg} />
        Notes
      </NavLink>
      <NavLink to="/contacts" className={navClass} end={false}>
        <Users size={ICON_SIZE.lg} />
        Contacts
      </NavLink>
    </nav>
  )
}
