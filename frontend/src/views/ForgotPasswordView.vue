<script lang="ts" setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import http from '@/api/http'
import { removeAccount } from '@/utils/credentialStore'

const props = defineProps({
  audience: {
    type: String,
    required: true,
    validator: (value: string) => value === 'user' || value === 'admin',
  },
})

const AUDIENCES = {
  user: {
    title: '找回密码',
    sub: '请填写网站账号注册时使用的邮箱（不是网站发件邮箱）',
    loginPath: '/login',
    loginLabel: '返回用户登录',
  },
  admin: {
    title: '找回管理员密码',
    sub: '请填写网站账号注册时使用的邮箱（不是网站发件邮箱）',
    loginPath: '/adminlogin',
    loginLabel: '返回管理员登录',
  },
} as const

const route = useRoute()
const cfg = computed(() => AUDIENCES[props.audience as 'user' | 'admin'])
const token = computed(() => String(route.query.token || ''))
const isResetMode = computed(() => Boolean(token.value))

const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const requestSent = ref(false)
const resetComplete = ref(false)
const developmentResetUrl = ref('')
const logoMissing = ref(false)

const handleRequest = async () => {
  const value = email.value.trim()
  if (!value) {
    ElMessage.error('请输入注册邮箱')
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
    ElMessage.error('邮箱格式不正确')
    return
  }

  loading.value = true
  try {
    const response = await http.post('/user/password-reset/request', {
      email: value,
      audience: props.audience,
    })
    requestSent.value = true
    developmentResetUrl.value = response.data.reset_url || ''
    ElMessage.success(response.data.message || '重置邮件已发送')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '重置邮件发送失败')
  } finally {
    loading.value = false
  }
}

const handleReset = async () => {
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
    const response = await http.post('/user/password-reset/confirm', {
      token: token.value,
      password: password.value,
      confirm_password: confirmPassword.value,
    })

    // 账号体系在用户端和管理端共用，密码修改后清除两个入口里可能记住的旧密码。
    for (const scope of ['user', 'admin'] as const) {
      removeAccount(scope, response.data.username)
      removeAccount(scope, response.data.email)
    }
    resetComplete.value = true
    ElMessage.success(response.data.message || '密码已重置')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '密码重置失败')
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

      <h1 class="auth-title">{{ isResetMode ? '设置新密码' : cfg.title }}</h1>
      <p class="auth-sub">
        {{ isResetMode ? '新密码设置成功后，原重置链接会立即失效' : cfg.sub }}
      </p>

      <div v-if="requestSent" class="auth-result" data-test="request-success">
        <span class="auth-result-icon">✓</span>
        <h2>请检查邮箱</h2>
        <p>如果该邮箱已注册，您会在几分钟内收到重置链接。链接 15 分钟内有效。</p>
        <p data-test="registered-email-note">
          请确认填写的是该账号的注册邮箱。为保护账号安全，未注册邮箱也会显示此页面，但不会发送邮件。
        </p>
        <a
          v-if="developmentResetUrl"
          class="auth-hint-link"
          :href="developmentResetUrl"
          data-test="development-reset-link"
        >
          打开本机测试链接
        </a>
      </div>

      <div v-else-if="resetComplete" class="auth-result" data-test="reset-success">
        <span class="auth-result-icon">✓</span>
        <h2>密码已重置</h2>
        <p>请返回登录页，使用新密码登录。</p>
      </div>

      <form v-else-if="isResetMode" class="auth-form" @submit.prevent="handleReset">
        <label class="field">
          <span class="field-label">新密码</span>
          <input
            v-model="password"
            type="password"
            class="field-input"
            autocomplete="new-password"
            placeholder="至少 6 位"
          />
        </label>

        <label class="field">
          <span class="field-label">确认新密码</span>
          <input
            v-model="confirmPassword"
            type="password"
            class="field-input"
            autocomplete="new-password"
            placeholder="请再次输入新密码"
          />
        </label>

        <button type="submit" class="btn btn-black btn-lg btn-block" :disabled="loading">
          {{ loading ? '提交中...' : '重置密码' }}
        </button>
      </form>

      <form v-else class="auth-form" @submit.prevent="handleRequest">
        <label class="field">
          <span class="field-label">注册邮箱</span>
          <input
            v-model="email"
            type="email"
            class="field-input"
            autocomplete="email"
            placeholder="请输入注册时使用的邮箱"
          />
        </label>

        <button type="submit" class="btn btn-black btn-lg btn-block" :disabled="loading">
          {{ loading ? '发送中...' : '发送重置链接' }}
        </button>
      </form>

      <p class="auth-hint">
        <router-link :to="cfg.loginPath" class="auth-hint-link">{{ cfg.loginLabel }}</router-link>
      </p>
    </div>
  </div>
</template>
