import { ref, reactive } from 'vue'

/**
 * 通用 API 请求 Hook
 * 处理加载状态、错误、数据缓存
 */
export function useApi(apiFn, options = {}) {
  const { immediate = false, transform = null } = options
  
  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)
  
  const execute = async (...args) => {
    loading.value = true
    error.value = null
    
    try {
      const result = await apiFn(...args)
      data.value = transform ? transform(result) : result
      return result
    } catch (e) {
      error.value = e.message || '请求失败'
      throw e
    } finally {
      loading.value = false
    }
  }
  
  if (immediate) {
    execute()
  }
  
  return {
    data,
    loading,
    error,
    execute,
    refresh: execute,
  }
}

/**
 * 列表数据 Hook
 */
export function useList(apiFn, options = {}) {
  const { immediate = false } = options
  
  const items = ref([])
  const loading = ref(false)
  const error = ref(null)
  
  const fetchList = async (...args) => {
    loading.value = true
    error.value = null
    
    try {
      const result = await apiFn(...args)
      // 兼容不同的响应格式
      items.value = Array.isArray(result) ? result : (result.items || result.data || result || [])
      return items.value
    } catch (e) {
      error.value = e.message || '加载失败'
      items.value = []
      throw e
    } finally {
      loading.value = false
    }
  }
  
  if (immediate) {
    fetchList()
  }
  
  return {
    items,
    loading,
    error,
    fetchList,
    refresh: fetchList,
  }
}
