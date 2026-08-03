<template>
  <div class="admin-page" v-loading="loading && viewMode === 'personal'">
    <div class="admin-page-head">
      <h2 class="admin-page-title">项目进度</h2>
      <p class="admin-page-sub">
        {{ viewMode === 'personal'
          ? '跟踪我提交的需求、开发项目、维护任务与资产审核进展'
          : '查看与 DBServer 同步的全公司 RPA、Skill 和 Python 开发进度' }}
      </p>
    </div>

    <div class="progress-scope-row">
      <div class="progress-scope-switch" role="group" aria-label="项目进度查看范围">
        <span
          class="progress-scope-thumb"
          :class="{ 'is-company': viewMode === 'company' }"
          aria-hidden="true"
        />
        <button
          type="button"
          :class="{ 'is-active': viewMode === 'personal' }"
          :aria-pressed="viewMode === 'personal'"
          @click="setViewMode('personal')"
        >个人版</button>
        <button
          type="button"
          :class="{ 'is-active': viewMode === 'company' }"
          :aria-pressed="viewMode === 'company'"
          @click="setViewMode('company')"
        >全公司版</button>
      </div>
      <span class="progress-scope-hint">
        {{ viewMode === 'personal' ? '只看与我相关的数据' : '全公司数据实时读取，仅供查看' }}
      </span>
    </div>

    <div v-if="viewMode === 'personal'" class="personal-progress-view">
      <div class="progress-search-row">
      <el-input
        v-model="searchKeyword"
        clearable
        aria-label="搜索项目进度数据"
        placeholder="搜索数据库编号、名称、部门、状态、人员或文件名"
      />
      </div>

    <!-- 统计卡片 -->
    <div class="admin-stats">
      <button
        type="button"
        class="admin-stat admin-stat-link"
        aria-label="查看我的需求明细"
        @click="scrollToSection('requirements-details')"
      >
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-blue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/></svg></span>
          <span class="admin-stat-label">我的需求</span>
        </div>
        <div class="admin-stat-value">{{ filteredRequirements.length }}</div>
        <span class="admin-stat-arrow" aria-hidden="true">↓</span>
      </button>
      <button
        type="button"
        class="admin-stat admin-stat-link"
        aria-label="查看非使用状态项目明细"
        @click="scrollToSection('active-projects-details')"
      >
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-amber"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3a9 9 0 1 0 9 9"/><path d="M12 7v5l3 2"/></svg></span>
          <span class="admin-stat-label">非使用状态项目</span>
        </div>
        <div class="admin-stat-value">{{ otherProjects.length }}</div>
        <span class="admin-stat-arrow" aria-hidden="true">↓</span>
      </button>
      <button
        type="button"
        class="admin-stat admin-stat-link"
        aria-label="查看已完成项目明细"
        @click="scrollToSection('completed-projects-details')"
      >
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-green"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6 9 17l-5-5"/></svg></span>
          <span class="admin-stat-label">已完成项目</span>
        </div>
        <div class="admin-stat-value">{{ completedProjects.length }}</div>
        <span class="admin-stat-arrow" aria-hidden="true">↓</span>
      </button>
      <button
        type="button"
        class="admin-stat admin-stat-link"
        aria-label="查看维护任务明细"
        @click="scrollToSection('maintenance-details')"
      >
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-violet"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2-2z"/></svg></span>
          <span class="admin-stat-label">维护任务</span>
        </div>
        <div class="admin-stat-value">{{ filteredMaintenanceTasks.length }}</div>
        <span class="admin-stat-arrow" aria-hidden="true">↓</span>
      </button>
      <button
        type="button"
        class="admin-stat admin-stat-link"
        aria-label="查看 Skill 提交明细"
        @click="scrollToSection('skill-details')"
      >
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-blue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h13l3 3v13H4z"/><path d="M8 9h8M8 13h8M8 17h5"/></svg></span>
          <span class="admin-stat-label">Skill 提交</span>
        </div>
        <div class="admin-stat-value">{{ filteredSkillAssets.length }}</div>
        <span class="admin-stat-arrow" aria-hidden="true">↓</span>
      </button>
      <button
        type="button"
        class="admin-stat admin-stat-link"
        aria-label="查看插件提交明细"
        @click="scrollToSection('plugin-details')"
      >
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-green"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/></svg></span>
          <span class="admin-stat-label">插件提交</span>
        </div>
        <div class="admin-stat-value">{{ filteredPluginAssets.length }}</div>
        <span class="admin-stat-arrow" aria-hidden="true">↓</span>
      </button>
    </div>

    <!-- 我的需求 -->
    <section id="requirements-details" class="progress-detail-section" tabindex="-1">
      <h3 class="admin-section-title">我的需求 ({{ filteredRequirements.length }})</h3>
      <div class="panel">
        <table class="admin-table">
          <thead>
            <tr><th>需求标题</th><th>部门</th><th>提出人</th><th>优先级</th><th>期望完成</th><th>状态</th><th style="text-align:right">操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredRequirements" :key="row.id">
              <td class="admin-td-title">{{ row.title }}</td>
              <td>{{ row.department }}</td>
              <td>{{ row.requester }}</td>
              <td><span class="chip" :class="priorityChip(row.priority)">{{ row.priority || '—' }}</span></td>
              <td class="admin-td-mono">{{ row.expected_finish_time || '—' }}</td>
              <td><span class="chip" :class="statusChip(row.status)">{{ row.status }}</span></td>
              <td style="text-align:right">
                <button
                  class="btn-mini btn-mini-gray"
                  :disabled="!row.editable"
                  :title="row.editable ? '修改需求信息' : '已通过或已取消的需求不能修改'"
                  @click="openRequirementEdit(row)"
                >修改</button>
              </td>
            </tr>
            <tr v-if="filteredRequirements.length === 0"><td colspan="7" class="empty-cell">{{ searchKeyword ? '没有匹配的需求' : '暂无需求' }}</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 状态不是“使用”的项目 -->
    <section id="active-projects-details" class="progress-detail-section" tabindex="-1">
      <h3 class="admin-section-title">非使用状态项目 ({{ otherProjects.length }})</h3>
      <div class="panel">
        <div v-for="project in otherProjects" :key="project.id" class="proj-row">
          <div class="proj-main">
            <span class="record-id">RPA #{{ project.id }}</span>
            <span class="proj-name" :title="project.name">{{ project.name }}</span>
            <span class="chip" :class="statusChip(project.status)">{{ project.status }}</span>
            <div class="admin-bar-track"><div class="admin-bar-fill is-active" :style="{ width: project.progress + '%' }"></div></div>
            <span class="proj-pct">{{ project.progress }}%</span>
            <button class="proj-log-btn" :class="{ open: logOpen['p' + project.id] }" @click="toggleLog('p' + project.id)">日志<span class="proj-log-chev"></span></button>
          </div>
          <div v-if="logOpen['p' + project.id]" class="proj-logs">
            <el-timeline v-if="project.logs.length">
              <el-timeline-item v-for="(log, i) in project.logs" :key="i" :timestamp="log.log_time" placement="top" type="primary">
                <div class="log-line"><b>开发人员：</b>{{ log.developer_name }}</div>
                <div class="log-line"><b>状态：</b>{{ log.status }}</div>
                <div class="log-line"><b>备注：</b>{{ log.remark }}</div>
              </el-timeline-item>
            </el-timeline>
            <p v-else class="proj-nolog">暂无进度日志</p>
          </div>
        </div>
        <p v-if="otherProjects.length === 0" class="empty-cell">暂无非使用状态项目</p>
      </div>
    </section>

    <!-- 已完成的项目 -->
    <section id="completed-projects-details" class="progress-detail-section" tabindex="-1">
      <h3 class="admin-section-title">已完成的项目 ({{ completedProjects.length }})</h3>
      <div class="panel">
        <div v-for="project in completedProjects" :key="project.id" class="proj-row">
          <div class="proj-main">
            <span class="record-id">RPA #{{ project.id }}</span>
            <span class="proj-name" :title="project.name">{{ project.name }}</span>
            <span class="chip" :class="statusChip(project.status)">{{ project.status }}</span>
            <div class="admin-bar-track"><div class="admin-bar-fill is-done" :style="{ width: project.progress + '%' }"></div></div>
            <span class="proj-pct">{{ project.progress }}%</span>
            <button class="proj-log-btn" :class="{ open: logOpen['p' + project.id] }" @click="toggleLog('p' + project.id)">日志<span class="proj-log-chev"></span></button>
          </div>
          <div v-if="logOpen['p' + project.id]" class="proj-logs">
            <el-timeline v-if="project.logs.length">
              <el-timeline-item v-for="(log, i) in project.logs" :key="i" :timestamp="log.log_time" placement="top" type="success">
                <div class="log-line"><b>开发人员：</b>{{ log.developer_name }}</div>
                <div class="log-line"><b>状态：</b>{{ log.status }}</div>
                <div class="log-line"><b>备注：</b>{{ log.remark }}</div>
              </el-timeline-item>
            </el-timeline>
            <p v-else class="proj-nolog">暂无历史日志</p>
          </div>
        </div>
        <p v-if="completedProjects.length === 0" class="empty-cell">暂无已完成的项目</p>
      </div>
    </section>

    <!-- 我的维护任务 -->
    <section id="maintenance-details" class="progress-detail-section" tabindex="-1">
      <h3 class="admin-section-title">我的维护任务 ({{ filteredMaintenanceTasks.length }})</h3>
      <div class="panel">
        <div v-for="task in filteredMaintenanceTasks" :key="task.id" class="proj-row">
          <div class="proj-main">
            <span class="proj-name" :title="task.name">{{ task.name }}</span>
            <span class="chip" :class="statusChip(task.status)">{{ task.status }}</span>
            <div class="admin-bar-track"><div class="admin-bar-fill is-active" :style="{ width: task.progress + '%' }"></div></div>
            <span class="proj-pct">{{ task.progress }}%</span>
            <button class="proj-log-btn" :class="{ open: logOpen['m' + task.id] }" @click="toggleLog('m' + task.id)">日志<span class="proj-log-chev"></span></button>
          </div>
          <div v-if="logOpen['m' + task.id]" class="proj-logs">
            <el-timeline v-if="task.logs.length">
              <el-timeline-item v-for="(log, i) in task.logs" :key="i" :timestamp="log.log_time" placement="top" type="warning">
                <div class="log-line"><b>维护人员：</b>{{ log.maintainer_name }}</div>
                <div class="log-line"><b>状态：</b>{{ log.status }}</div>
                <div class="log-line"><b>备注：</b>{{ log.remark }}</div>
              </el-timeline-item>
            </el-timeline>
            <p v-else class="proj-nolog">暂无维护日志</p>
          </div>
        </div>
        <p v-if="filteredMaintenanceTasks.length === 0" class="empty-cell">{{ searchKeyword ? '没有匹配的维护任务' : '暂无维护任务' }}</p>
      </div>
    </section>

    <!-- 我的 Skill 文件 -->
    <section id="skill-details" class="progress-detail-section" tabindex="-1">
      <h3 class="admin-section-title">我的 Skill 文件 ({{ filteredSkillAssets.length }})</h3>
      <div class="panel">
        <table class="admin-table">
          <thead><tr><th>数据库编号</th><th>名称</th><th>版本</th><th>文件名</th><th>审核状态</th><th>开发进度</th><th>生命周期</th><th>提交时间</th><th style="text-align:right">操作</th></tr></thead>
          <tbody>
            <tr v-for="row in filteredSkillAssets" :key="row.id">
              <td class="admin-td-mono">Skill #{{ row.id }}</td>
              <td class="admin-td-title">{{ row.name }}</td>
              <td>{{ row.version || '—' }}</td>
              <td class="admin-td-mono">{{ row.file_name }}</td>
              <td><span class="chip" :class="statusChip(row.status)">{{ row.status }}</span></td>
              <td>{{ row.status === '已通过' ? `${row.progress ?? 0}%` : '—' }}</td>
              <td><span v-if="row.status === '已通过'" class="chip" :class="statusChip(row.lifecycle_status)">{{ row.lifecycle_status || '在编' }}</span><span v-else>—</span></td>
              <td class="admin-td-mono">{{ row.created_at }}</td>
              <td style="text-align:right"><button class="btn-mini btn-mini-gray" @click="openAssetEdit(row, 'skill')">修改</button></td>
            </tr>
            <tr v-if="filteredSkillAssets.length === 0"><td colspan="9" class="empty-cell">{{ searchKeyword ? '没有匹配的 Skill' : '暂无 Skill 提交' }}</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 我的 Python 插件 -->
    <section id="plugin-details" class="progress-detail-section" tabindex="-1">
      <h3 class="admin-section-title">我的 Python 插件 ({{ filteredPluginAssets.length }})</h3>
      <div class="panel">
        <table class="admin-table">
          <thead><tr><th>数据库编号</th><th>名称</th><th>版本</th><th>文件名</th><th>审核状态</th><th>开发进度</th><th>生命周期</th><th>提交时间</th><th style="text-align:right">操作</th></tr></thead>
          <tbody>
            <tr v-for="row in filteredPluginAssets" :key="row.id">
              <td class="admin-td-mono">Python #{{ row.id }}</td>
              <td class="admin-td-title">{{ row.name }}</td>
              <td>{{ row.version || '—' }}</td>
              <td class="admin-td-mono">{{ row.file_name }}</td>
              <td><span class="chip" :class="statusChip(row.status)">{{ row.status }}</span></td>
              <td>{{ row.status === '已通过' ? `${row.progress ?? 0}%` : '—' }}</td>
              <td><span v-if="row.status === '已通过'" class="chip" :class="statusChip(row.lifecycle_status)">{{ row.lifecycle_status || '在编' }}</span><span v-else>—</span></td>
              <td class="admin-td-mono">{{ row.created_at }}</td>
              <td style="text-align:right"><button class="btn-mini btn-mini-gray" @click="openAssetEdit(row, 'pythonPlugin')">修改</button></td>
            </tr>
            <tr v-if="filteredPluginAssets.length === 0"><td colspan="9" class="empty-cell">{{ searchKeyword ? '没有匹配的 Python 插件' : '暂无 Python 插件提交' }}</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <AssetEditDialog
      v-if="editingAsset"
      v-model="editVisible"
      :asset="editingAsset"
      :asset-type-id="editingAssetTypeId"
      :user-id="userId"
      @saved="handleAssetEdited"
    />
    <RequirementEditDialog
      v-if="editingRequirement"
      v-model="requirementEditVisible"
      :requirement="editingRequirement"
      :user-id="userId"
      @saved="handleRequirementEdited"
    />
    </div>

    <DevelopmentProgress
      v-else
      api-prefix="/user/manage"
      read-scope="all"
      self-service
      read-only
      embedded
    />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import http from '@/api/http'
import { fetchMyAssets } from '@/api/assets'
import DevelopmentProgress from '@/components/admin/DevelopmentProgress.vue'
import AssetEditDialog from './AssetEditDialog.vue'
import RequirementEditDialog from './RequirementEditDialog.vue'

const requirements = ref([])
const projects = ref([])
const maintenanceTasks = ref([])
const skillAssets = ref([])
const pluginAssets = ref([])
const userId = ref('')
const loading = ref(false)
const logOpen = ref({}) // 展开日志的行 key（p<id> 项目 / m<id> 维护）
const editVisible = ref(false)
const editingAsset = ref(null)
const editingAssetTypeId = ref('skill')
const requirementEditVisible = ref(false)
const editingRequirement = ref(null)
const searchKeyword = ref('')
const viewMode = ref('personal')

const normalizedKeyword = computed(() => searchKeyword.value.trim().toLocaleLowerCase())
const matchesKeyword = (...values) => {
  if (!normalizedKeyword.value) return true
  return values.some((value) =>
    String(value ?? '').toLocaleLowerCase().includes(normalizedKeyword.value)
  )
}
const filteredRequirements = computed(() =>
  requirements.value.filter((row) =>
    matchesKeyword(row.id, row.title, row.department, row.requester, row.priority, row.status)
  )
)
const filteredProjects = computed(() =>
  projects.value.filter((row) =>
    matchesKeyword(
      row.id,
      row.name,
      row.status,
      row.progress,
      ...(row.logs || []).flatMap((log) => [log.developer_name, log.status, log.remark])
    )
  )
)
const filteredMaintenanceTasks = computed(() =>
  maintenanceTasks.value.filter((row) =>
    matchesKeyword(
      row.id,
      row.name,
      row.status,
      row.progress,
      ...(row.logs || []).flatMap((log) => [log.maintainer_name, log.status, log.remark])
    )
  )
)
const filterAssets = (rows) => rows.filter((row) =>
  matchesKeyword(
    row.id,
    row.name,
    row.version,
    row.file_name,
    row.status,
    row.lifecycle_status,
    row.submitter
  )
)
const filteredSkillAssets = computed(() => filterAssets(skillAssets.value))
const filteredPluginAssets = computed(() => filterAssets(pluginAssets.value))
const otherProjects = computed(() => filteredProjects.value.filter((p) => p.status !== '使用'))
const completedProjects = computed(() => filteredProjects.value.filter((p) => p.status === '使用'))

const setViewMode = async (mode) => {
  if (mode === viewMode.value || !['personal', 'company'].includes(mode)) return
  viewMode.value = mode
  searchKeyword.value = ''
  if (mode === 'personal') await fetchData()
}

const toggleLog = (key) => { logOpen.value = { ...logOpen.value, [key]: !logOpen.value[key] } }
const scrollToSection = (sectionId) => {
  const section = document.getElementById(sectionId)
  if (!section) return
  section.focus({ preventScroll: true })
  section.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// 状态 → chip 配色（与全站 chip 类统一）
const statusChip = (status) => {
  switch (status) {
    case '已通过':
    case '已完成': return 'chip-green'
    case '已拒绝':
    case '已取消':
    case '失败': return 'chip-red'
    case '待审核':
    case '维护中':
    case '优化中':
    case '在编':
    case '开发中':
    case '大修': return 'chip-amber'
    case '使用': return 'chip-blue'
    case '新编': return 'chip-violet'
    case '停用': return 'chip-gray'
    default: return 'chip-gray'
  }
}
const priorityChip = (p) => ({ 高: 'chip-red', 中: 'chip-amber', 低: 'chip-green' }[p] || 'chip-gray')

const openAssetEdit = (asset, assetTypeId) => {
  editingAsset.value = asset
  editingAssetTypeId.value = assetTypeId
  editVisible.value = true
}

const handleAssetEdited = (updated) => {
  if (!updated) return
  const list = editingAssetTypeId.value === 'skill' ? skillAssets.value : pluginAssets.value
  const index = list.findIndex((item) => item.id === updated.id)
  if (index !== -1) list[index] = updated
}

const openRequirementEdit = (requirement) => {
  if (!requirement?.editable) return
  editingRequirement.value = requirement
  requirementEditVisible.value = true
}

const handleRequirementEdited = (updated) => {
  if (!updated) return
  const index = requirements.value.findIndex((item) => item.id === updated.id)
  if (index !== -1) requirements.value[index] = updated
}

const fetchData = async () => {
  // 未登录时 user_id 缺失，资产接口的 int(user_id) 会 400 拖垮整个 Promise.all，
  // 直接提示登录并跳过请求
  const storedUserId = localStorage.getItem('user_id')
  if (!storedUserId) {
    ElMessage.error('请先登录')
    return
  }
  userId.value = storedUserId
  loading.value = true
  try {
    // 各接口互不依赖：并行请求，页面等待时间 = 最慢的一个而不是各项之和
    const [reqRes, projRes, maintRes, skillRes, pluginRes] = await Promise.all([
      http.get('/user/get_my_requirements', { params: { user_id: storedUserId } }),
      http.get('/user/get_my_projects', { params: { user_id: storedUserId } }),
      http.get('/user/get_my_maintenance_tasks', { params: { user_id: storedUserId } }),
      fetchMyAssets({ userId: storedUserId, assetType: 'skill' }),
      fetchMyAssets({ userId: storedUserId, assetType: 'python_plugin' }),
    ])
    skillAssets.value = skillRes.data?.data ?? []
    pluginAssets.value = pluginRes.data?.data ?? []
    requirements.value = reqRes.data.data || []
    projects.value = (projRes.data.data || []).map((p) => ({
      ...p,
      progress: Number(p.progress || 0),
      logs: Array.isArray(p.logs) ? p.logs : [],
    }))
    maintenanceTasks.value = (maintRes.data.data || []).map((t) => ({
      ...t,
      progress: Number(t.progress || 0),
      logs: Array.isArray(t.logs) ? t.logs : [],
    }))
  } catch (error) {
    ElMessage.error('获取数据失败')
    console.error('Error fetching dashboard data:', error)
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.empty-cell { text-align: center; color: var(--brand-muted); padding: 34px 0; font-size: 13.5px; }
.progress-scope-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: -8px 0 22px;
}
.progress-scope-switch {
  position: relative;
  display: grid;
  grid-template-columns: repeat(2, 96px);
  padding: 4px;
  border: 1px solid var(--brand-line);
  border-radius: 999px;
  background: #f0f0eb;
}
.progress-scope-thumb {
  position: absolute;
  top: 4px;
  left: 4px;
  width: 96px;
  height: calc(100% - 8px);
  border-radius: 999px;
  background: var(--brand-text);
  box-shadow: 0 5px 14px rgba(20, 20, 19, 0.18);
  transition: transform 0.24s ease;
}
.progress-scope-thumb.is-company { transform: translateX(96px); }
.progress-scope-switch button {
  position: relative;
  z-index: 1;
  height: 34px;
  padding: 0 14px;
  border: 0;
  background: transparent;
  color: var(--brand-muted);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: color 0.2s ease;
}
.progress-scope-switch button.is-active { color: #fff; }
.progress-scope-switch button:focus-visible {
  outline: 3px solid rgba(79, 70, 184, 0.28);
  outline-offset: 2px;
  border-radius: 999px;
}
.progress-scope-hint { color: var(--brand-muted); font-size: 12.5px; }
.progress-search-row {
  display: flex;
  justify-content: flex-end;
  margin: -8px 0 20px;
}
.progress-search-row :deep(.el-input) { width: min(460px, 100%); }
.record-id {
  flex: none;
  color: var(--brand-muted);
  font-family: var(--brand-mono);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.admin-stat-link {
  width: 100%;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  appearance: none;
}
.admin-stat-link:focus-visible {
  outline: 3px solid rgba(79, 70, 184, 0.28);
  outline-offset: 2px;
}
.admin-stat-arrow {
  position: absolute;
  right: 17px;
  bottom: 16px;
  color: var(--brand-muted);
  font-size: 18px;
  line-height: 1;
  transition: color 0.18s ease, transform 0.18s ease;
}
.admin-stat-link:hover .admin-stat-arrow {
  color: var(--brand-text);
  transform: translateY(3px);
}
.progress-detail-section {
  scroll-margin-top: 92px;
  outline: none;
}
@media (max-width: 640px) {
  .progress-scope-row { align-items: flex-start; flex-direction: column; }
}
</style>
