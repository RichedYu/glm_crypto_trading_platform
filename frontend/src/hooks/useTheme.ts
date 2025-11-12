import { useEffect, useState } from 'react'

const prefersDarkScheme = () =>
  window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches

export const useTheme = () => {
  const [darkMode, setDarkMode] = useState(() => {
    const stored = localStorage.getItem('glm-theme')
    if (stored) return stored === 'dark'
    return prefersDarkScheme()
  })

  useEffect(() => {
    const root = document.documentElement
    if (darkMode) {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    localStorage.setItem('glm-theme', darkMode ? 'dark' : 'light')
  }, [darkMode])

  return { darkMode, toggleTheme: () => setDarkMode((prev) => !prev) }
}
