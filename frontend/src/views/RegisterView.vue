<script lang="ts" setup>
import { computed, ref } from 'vue'
import router from '@/router'
import http from '@/api/http'

// 用户端与管理员端注册共用本组件（账号体系共用 users 表，后端同一注册接口），
// 差异只有文案与注册后跳回的登录页，由路由以 props 传入 audience。
// 若将来要做角色隔离（管理员/普通用户分权），需先给账号加角色字段再拆分。
const props = defineProps({
  audience: {
    type: String,
    required: true,
    validator: (v: string) => v === 'user' || v === 'admin',
  },
})

const AUDIENCES = {
  user: {
    title: '用户注册',
    sub: 'RPA 机器人、Skill 文件、Python 插件 · 用户端',
    loginPath: '/login',
  },
  admin: {
    title: '管理员注册',
    sub: 'RPA 机器人、Skill 文件、Python 插件 · 管理后台',
    loginPath: '/adminlogin',
  },
} as const

const cfg = computed(() => AUDIENCES[props.audience as 'user' | 'admin'])

const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const logoMissing = ref(false)

const handleRegister = async () => {
  if (!username.value.trim() || !email.value.trim() || !password.value || !confirmPassword.value) {
    ElMessage.error('请输入完整信息')
    return
  }

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
    ElMessage.error('邮箱格式不正确')
    return
  }

  if (password.value.length < 6) {
    ElMessage.error('密码长度至少 6 位')
    return
  }

  if (password.value !== confirmPassword.value) {
    ElMessage.error('两次输入的密码不一致')
    return
  }

  loading.value = true

  try {
    const res = await http.post('/user/register', {
      username: username.value.trim(),
      email: email.value.trim(),
      password: password.value,
    })

    ElMessage.success(res.data.message || '注册成功，请登录')
    router.push(cfg.value.loginPath)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="aitools-page auth-page">
    <router-link to="/" class="auth-home">
      <span class="auth-home-arrow">←</span>
      返回首页
    </router-link>

    <div class="auth-card">
      <router-link to="/" class="auth-brand">
        <img v-if="!logoMissing" class="auth-logo" src="/logo.png" alt="公司 logo" @error="logoMissing = true" />
        <span class="auth-brand-name">AI Tools web</span>
      </router-link>

      <h1 class="auth-title">{{ cfg.title }}</h1>
      <p class="auth-sub">{{ cfg.sub }}</p>

      <form class="auth-form" @submit.prevent="handleRegister">
        <label class="field">
          <span class="field-label">用户名</span>
          <input v-model="username" type="text" class="field-input" placeholder="请输入用户名" />
        </label>

        <label class="field">
          <span class="field-label">邮箱</span>
          <input v-model="email" type="email" class="field-input" placeholder="请输入邮箱" />
        </label>

        <label class="field">
          <span class="field-label">密码</span>
          <input v-model="password" type="password" class="field-input" placeholder="至少 6 位" />
        </label>

        <label class="field">
          <span class="field-label">确认密码</span>
          <input v-model="confirmPassword" type="password" class="field-input" placeholder="请再次输入密码" />
        </label>

        <button type="submit" class="btn btn-black btn-lg btn-block" :disabled="loading">
          {{ loading ? '注册中...' : '注册' }}
        </button>
      </form>

      <p class="auth-hint">
        已有账号？
        <router-link :to="cfg.loginPath" class="auth-hint-link">返回登录</router-link>
      </p>
    </div>
  </div>
</template>
