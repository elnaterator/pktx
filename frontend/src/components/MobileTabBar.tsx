import { useState } from 'react'
import { NavLink, useLocation } from 'react-router'
import { Ellipsis } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import { cx } from '../utils/cx'
import { Modal } from './Modal'
import { NAV_ITEMS } from './navItems'
import styles from './MobileTabBar.module.css'

const TABS = NAV_ITEMS.filter((item) => item.inTabBar)
const MORE = NAV_ITEMS.filter((item) => !item.inTabBar)

/** Phone-only bottom navigation: four sections plus a "More" sheet for the rest. */
export default function MobileTabBar() {
  const { pathname } = useLocation()
  const [moreOpen, setMoreOpen] = useState(false)
  const inMore = MORE.some((item) => pathname === item.to || pathname.startsWith(`${item.to}/`))

  return (
    <>
      <nav className={styles.bar} aria-label="Main navigation">
        {TABS.map(({ to, label, shortLabel, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end ?? false}
            aria-label={label}
            className={({ isActive }) => cx(styles.tab, isActive && styles.active)}
          >
            <Icon size={ICON_SIZE.xl} aria-hidden="true" />
            <span className={styles.label}>{shortLabel ?? label}</span>
          </NavLink>
        ))}
        <button
          type="button"
          className={cx(styles.tab, inMore && styles.active)}
          aria-haspopup="dialog"
          aria-expanded={moreOpen}
          aria-current={inMore ? 'page' : undefined}
          onClick={() => setMoreOpen(true)}
        >
          <Ellipsis size={ICON_SIZE.xl} aria-hidden="true" />
          <span className={styles.label}>More</span>
        </button>
      </nav>

      {moreOpen && (
        <Modal label="More sections" placement="bottom" className={styles.sheet} onClose={() => setMoreOpen(false)}>
          <ul className={styles.sheetList}>
            {MORE.map(({ to, label, icon: Icon, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end ?? false}
                  className={({ isActive }) => cx(styles.sheetItem, isActive && styles.active)}
                  onClick={() => setMoreOpen(false)}
                >
                  <Icon size={ICON_SIZE.xl} aria-hidden="true" />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </Modal>
      )}
    </>
  )
}
