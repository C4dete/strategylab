import { Loader2 } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import './ui.css'

type Variante = 'primary' | 'secondary' | 'ghost' | 'danger'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variante
  size?: 'sm' | 'md'
  icon?: ReactNode
  loading?: boolean
}

export function Button({ variant = 'secondary', size = 'md', icon, loading, children, className, disabled, ...rest }: Props) {
  return (
    <button
      type="button"
      className={`btn btn--${variant} btn--${size} ${className ?? ''}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Loader2 size={16} className="spin" aria-hidden /> : icon}
      {children}
    </button>
  )
}

interface IconProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string
  variant?: 'ghost' | 'danger'
  children: ReactNode
}

/** Botão só de ícone: o `label` vira aria-label e dica nativa. */
export function IconButton({ label, variant = 'ghost', children, className, ...rest }: IconProps) {
  return (
    <button
      type="button"
      className={`iconbtn iconbtn--${variant} ${className ?? ''}`}
      aria-label={label}
      title={label}
      {...rest}
    >
      {children}
    </button>
  )
}
