import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cx } from '../utils/cx'
import styles from './button.module.css'

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'link'
export type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
}

/** Text button. Styling lives in button.module.css — pick a variant, don't restyle. */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'md', type = 'button', className, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx(styles.button, styles[variant], styles[size], className)}
      {...rest}
    />
  )
})
