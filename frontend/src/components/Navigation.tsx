import { NavLink } from 'react-router'
import { ICON_SIZE } from '../theme'
import { NAV_ITEMS } from './navItems'
import styles from './Navigation.module.css'

function navClass({ isActive }: { isActive: boolean }) {
  return `${styles.navItem}${isActive ? ` ${styles.active}` : ''}`
}

/** Top navigation for tablet and desktop; phones use MobileTabBar instead. */
export default function Navigation() {
  return (
    <nav className={styles.nav} aria-label="Main navigation">
      {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end ?? false} className={navClass} title={label}>
          <Icon size={ICON_SIZE.lg} aria-hidden="true" />
          <span className={styles.label}>{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
