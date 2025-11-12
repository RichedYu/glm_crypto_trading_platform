import { ReactNode, useCallback } from 'react'
import { SidebarNav } from './SidebarNav'
import { TopBar } from './TopBar'
import { useTheme } from '../../hooks/useTheme'

type Props = {
  children: ReactNode
  lastUpdated?: string
}

export const AppLayout = ({ children, lastUpdated }: Props) => {
  const { darkMode, toggleTheme } = useTheme()

  const handleNavigate = useCallback((id: string) => {
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [])

  return (
    <div className={`min-h-screen ${darkMode ? 'dark' : ''} bg-background`}>
      <div className="flex">
        <SidebarNav onNavigate={handleNavigate} />
        <div className="flex-1 flex flex-col">
          <TopBar onToggleTheme={toggleTheme} lastUpdated={lastUpdated} />
          <main className="p-4 md:p-8 space-y-12 bg-[#0b0e11]">
            {children}
          </main>
        </div>
      </div>
    </div>
  )
}
