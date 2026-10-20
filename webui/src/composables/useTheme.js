import { ref, watch, onMounted } from 'vue'

const THEME_KEY = 'feiyunmy-theme'

const theme = ref('dark')

export function useTheme() {
  const isDark = ref(true)
  
  const setTheme = (newTheme) => {
    theme.value = newTheme
    isDark.value = newTheme === 'dark'
    
    if (newTheme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    
    localStorage.setItem(THEME_KEY, newTheme)
  }
  
  const toggleTheme = () => {
    setTheme(isDark.value ? 'light' : 'dark')
  }
  
  onMounted(() => {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved) {
      setTheme(saved)
    } else {
      // 默认暗红色主题
      setTheme('dark')
    }
  })
  
  return {
    theme,
    isDark,
    setTheme,
    toggleTheme,
  }
}
