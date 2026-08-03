<script lang="ts" setup>
import { computed, ref, watch } from 'vue'
import router from '@/router'
import http from '@/api/http'
import { getSavedPassword, saveAccount, removeAccount } from '@/utils/credentialStore'
import { setLearningSession } from '@/utils/learningSession'

// 用户端与管理员端登录共用本组件：差异全部收敛在 AUDIENCES 配置里，
// 由路由以 props 传入 audience（'user' | 'admin'）。
// App.vue 的顶层 RouterView 按路由记录 key，两个登录路由互切时会重建实例。
const props = defineProps({
  audience: {
    type: String,
    required: true,
    validator: (v: string) => v === 'user' || v === 'admin',
  },
})

const AUDIENCES = {
  user: {
    title: '用户登录',
    sub: 'RPA 机器人、Skill 文件、Python 插件 · 用户端',
    endpoint: '/user/login',
    idField: 'user_id',
    redirect: '/main',
    submitLabel: '登录',
    successMsg: '登录成功',
    registerPath: '/register',
    forgotPath: '/forgot-password',
  },
  admin: {
    title: '管理员登录',
    sub: 'RPA 机器人、Skill 文件、Python 插件 · 管理后台',
    endpoint: '/admin/login',
    idField: 'admin_id',
    redirect: '/admin',
    submitLabel: '登录后台',
    successMsg: '管理员登录成功',
    registerPath: '/adminregister',
    forgotPath: '/admin-forgot-password',
  },
} as const

const cfg = computed(() => AUDIENCES[props.audience as 'user' | 'admin'])

const useEmailLogin = ref(false) // 控制登录方式：false=用户名，true=邮箱
const username = ref('')
const email = ref('')
const password = ref('')
const employmentType = ref('')
const remember = ref(false) // 记住账号和密码（按账号名分别保存在本机，用户/管理端分开存）
const loading = ref(false)
const logoMissing = ref(false)

const toggleLoginMode = () => {
  useEmailLogin.value = !useEmailLogin.value
  username.value = ''
  email.value = ''
  password.value = ''
}

// 输入的用户名/邮箱命中本机保存过的账号时，自动带出密码并勾选"记住"；
// 密码框已有内容时不覆盖（避免打断用户手动输入）
watch([username, email, useEmailLogin], () => {
  const account = useEmailLogin.value ? email.value : username.value
  const saved = getSavedPassword(props.audience, account)
  if (saved && !password.value) {
    password.value = saved
    remember.value = true
  }
})

const handleLogin = async () => {
  if ((useEmailLogin.value && !email.value) || (!useEmailLogin.value && !username.value) || !password.value) {
    ElMessage.error('请输入完整信息')
    return
  }
  if (props.audience === 'user' && !employmentType.value) {
    ElMessage.error('请选择职位')
    return
  }

  loading.value = true

  try {
    const payload = {
      ...(useEmailLogin.value ? { email: email.value } : { username: username.value }),
      password: password.value,
      ...(props.audience === 'user' ? { employment_type: employmentType.value } : {}),
    }

    const res = await http.post(cfg.value.endpoint, payload)

    ElMessage.success(res.data.message || cfg.value.successMsg)
    localStorage.setItem(cfg.value.idField, res.data[cfg.value.idField])
    setLearningSession({ token: res.data.learning_token, role: res.data.learning_role })

    // 登录成功才落盘：勾选则保存/更新该账号的密码，未勾选视为取消记忆
    const account = useEmailLogin.value ? email.value : username.value
    if (remember.value) saveAccount(props.audience, account, password.value)
    else removeAccount(props.audience, account)

    router.push(cfg.value.redirect)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || error.response?.data?.error || '登录失败')
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

      <form class="auth-form" @submit.prevent="handleLogin">
        <label v-if="useEmailLogin" class="field">
          <span class="field-label">邮箱</span>
          <input v-model="email" type="email" class="field-input" placeholder="请输入邮箱" />
        </label>
        <label v-else class="field">
          <span class="field-label">用户名</span>
          <input v-model="username" type="text" class="field-input" placeholder="请输入用户名" />
        </label>

        <label v-if="props.audience === 'user'" class="field">
          <span class="field-label">职位</span>
          <select v-model="employmentType" data-test="employment-type" class="field-input">
            <option disabled value="">请选择职位</option>
            <option value="intern">实习生</option>
            <option value="employee">正式员工</option>
          </select>
        </label>

        <label class="field">
          <span class="field-label">密码</span>
          <input v-model="password" type="password" class="field-input" placeholder="请输入密码" />
        </label>

        <div class="auth-options">
          <label class="remember-row">
            <input v-model="remember" type="checkbox" class="remember-box" />
            记住账号和密码
          </label>
          <router-link :to="cfg.forgotPath" class="auth-option-link">忘记密码？</router-link>
        </div>

        <button type="submit" class="btn btn-black btn-lg btn-block" :disabled="loading">
          {{ loading ? '登录中...' : cfg.submitLabel }}
        </button>
      </form>

      <button type="button" class="auth-switch" @click="toggleLoginMode">
        {{ useEmailLogin ? '使用用户名登录' : '使用邮箱登录' }}
      </button>

      <p class="auth-hint">
        还没有账号？
        <router-link :to="cfg.registerPath" class="auth-hint-link">立即注册</router-link>
      </p>
    </div>
  </div>
</template>
