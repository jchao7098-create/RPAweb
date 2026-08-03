<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { changeLearningRole, fetchLearningUsers, fetchRoleChangeLogs } from '@/api/learning'

const roles = ['employee', 'intern', 'hr', 'boss']
const users = ref([]); const usersTotal = ref(0); const userPage = ref(1)
const query = ref(''); const audit = ref([]); const auditTotal = ref(0); const auditPage = ref(1)
const pending = ref(null); const error = ref(''); let timer
async function loadUsers() { const value = await fetchLearningUsers({ query: query.value.trim(), page: userPage.value, per_page: 10 }); users.value = value?.items || []; usersTotal.value = value?.total || 0 }
async function loadAudit() { const value = await fetchRoleChangeLogs({ page: auditPage.value, per_page: 10 }); audit.value = value?.items || []; auditTotal.value = value?.total || 0 }
async function searchNow() { userPage.value = 1; await loadUsers() }
function scheduleSearch() { clearTimeout(timer); timer = setTimeout(searchNow, 300) }
function selectRole(user, event) { const role = event.target.value; if (role !== user.role) pending.value = { user, role }; else event.target.value = user.role }
async function confirmRole() { if (!pending.value) return; error.value = ''; try { const result = await changeLearningRole(pending.value.user.user_id, pending.value.role); Object.assign(pending.value.user, result); pending.value = null; await loadAudit() } catch (value) { error.value = value?.response?.data?.error || '角色修改失败' } }
function formatTime(value) { return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Shanghai' }).format(new Date(value)) : '—' }
onMounted(async () => { try { await Promise.all([loadUsers(), loadAudit()]) } catch (value) { error.value = value?.response?.data?.error || '人员列表加载失败' } })
onBeforeUnmount(() => clearTimeout(timer))
defineExpose({ searchNow })
</script>

<template>
  <section class="admin-page role-management"><header class="page-head"><div><p class="eyebrow">Learning access</p><h1>人员权限</h1></div><label>搜索人员<input data-test="user-search" v-model="query" placeholder="姓名或邮箱" @input="scheduleSearch" /></label></header><p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <section class="panel"><div class="table-wrap"><table><thead><tr><th>人员</th><th>邮箱</th><th>当前角色</th><th>调整角色</th></tr></thead><tbody><tr v-for="user in users" :key="user.user_id"><td>{{ user.username || user.name }}</td><td>{{ user.email }}</td><td>{{ user.role || 'employee' }}</td><td><select data-test="role-select" :value="user.role || 'employee'" @change="selectRole(user, $event)"><option v-for="role in roles" :key="role" data-test="role-option" :value="role">{{ role }}</option></select></td></tr></tbody></table></div><p class="pagination">共 {{ usersTotal }} 人 · 第 {{ userPage }} 页</p></section>
    <section class="panel"><h2>角色审计</h2><div class="table-wrap"><table><thead><tr><th>目标人员</th><th>操作人</th><th>原角色</th><th>新角色</th><th>来源</th><th>时间</th></tr></thead><tbody><tr v-for="item in audit" :key="item.id || item.changed_at"><td>{{ item.target_username || item.target_user_name || item.target_user_id }}</td><td>{{ item.operator_username || item.operator_user_name || (item.source === 'bootstrap' ? '系统初始化' : '—') }}</td><td>{{ item.old_role }}</td><td>{{ item.new_role }}</td><td>{{ item.source }}</td><td>{{ formatTime(item.changed_at) }}</td></tr></tbody></table></div><p class="pagination">共 {{ auditTotal }} 条 · 第 {{ auditPage }} 页</p></section>
    <div v-if="pending" class="dialog-backdrop" role="dialog" aria-modal="true" aria-label="确认角色变更"><section class="panel dialog"><h2>确认角色调整</h2><p>将 {{ pending.user.username || pending.user.user_id }} 调整为 {{ pending.role }}？</p><div class="actions"><button class="btn btn-gray" @click="pending = null">取消</button><button data-test="confirm-role" class="btn btn-black" @click="confirmRole">确认修改</button></div></section></div>
  </section>
</template>

<style scoped>
.admin-page{max-width:1120px;margin:0 auto}.page-head{display:flex;justify-content:space-between;gap:16px;align-items:end}.page-head h1{margin:4px 0}.page-head input,select{padding:8px;border:1px solid var(--brand-line);border-radius:8px}.eyebrow{margin:0;color:#7c5cff;font-weight:700}.panel{padding:20px;margin-top:18px;border:1px solid var(--brand-line);border-radius:16px;background:var(--brand-raised)}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;text-align:left}th,td{padding:12px;border-bottom:1px solid var(--brand-line)}.pagination{color:var(--brand-muted)}.form-error{padding:10px;color:#b42318;background:#fff0ee;border-radius:8px}.dialog-backdrop{position:fixed;inset:0;display:grid;place-items:center;padding:16px;background:rgba(0,0,0,.36);z-index:5}.dialog{width:min(440px,100%);margin:0}.actions{display:flex;gap:10px;margin-top:18px}@media(max-width:640px){.page-head{flex-direction:column;align-items:start}}
</style>
