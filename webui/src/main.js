import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

// 简单路由（实际通过状态管理页面切换）
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', name: 'dashboard', component: { template: '<div></div>' } },
    { path: '/chat', name: 'chat', component: { template: '<div></div>' } }
  ]
})

const app = createApp(App)
app.use(router)
app.mount('#app')
