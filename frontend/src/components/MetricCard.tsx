import { ReactNode } from 'react'
import clsx from 'clsx'

interface MetricCardProps {
  label: string
  value: ReactNode
  delta?: string
  positive?: boolean
}

export const MetricCard = ({ label, value, delta, positive }: MetricCardProps) => (
  <div className="glass-card h-full">
    <p className="text-xs uppercase tracking-[0.2em] text-gray-400 mb-2">{label}</p>
    <div className="text-2xl font-semibold">{value}</div>
    {delta && (
      <span className={clsx('text-sm font-medium', positive ? 'text-emerald-400' : 'text-rose-400')}>
        {delta}
      </span>
    )}
  </div>
)
