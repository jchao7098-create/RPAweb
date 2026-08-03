<script setup>
import { ref, onMounted, computed } from 'vue'
import http from '@/api/http'
import { fetchAdminAssets, updateAssetProgress } from '@/api/assets'
import { departmentFromProjectName, departmentGroup } from '@/utils/departments'

const props = defineProps({
  apiPrefix: { type: String, default: '/admin' },
  selfService: { type: Boolean, default: false },
  readScope: { type: String, default: '' },
  readOnly: { type: Boolean, default: false },
  embedded: { type: Boolean, default: false },
})

const LIFECYCLE_STATUSES = ['在编', '使用', '大修', '停用']

const resourceTab = ref('rpa')
const searchKeyword = ref('')
const projects = ref([])
const assets = ref([])
const loading = ref(true)
const updating = ref(false)
const expandedLogs = ref({})

const projectDialogVisible = ref(false)
const currentProject = ref(null)
const newProgress = ref(0)
const newRemark = ref('')
const newProjectStatus = ref('在编')

const assetDialogVisible = ref(false)
const currentAsset = ref(null)
const assetUpdating = ref(false)
const newAssetProgress = ref(0)
const assetStatusMode = ref('auto')
const newAssetStatus = ref('在编')

const departmentOf = departmentFromProjectName
const resourceLabel = computed(() => (resourceTab.value === 'skill' ? 'Skill 文件' : 'Python 插件'))

const managedAssets = computed(() => assets.value.filter((asset) => asset.status === '已通过'))
const normalizedKeyword = computed(() => searchKeyword.value.trim().toLocaleLowerCase())
const includesKeyword = (...values) => {
  if (!normalizedKeyword.value) return true
  return values.some((value) =>
    String(value ?? '').toLocaleLowerCase().includes(normalizedKeyword.value)
  )
}
const filteredProjects = computed(() =>
  projects.value.filter((project) =>
    includesKeyword(
      project.name,
      project.id,
      departmentOf(project.name),
      project.status,
      ...(project.logs || []).map((log) => log.developer_name)
    )
  )
)
const visibleAssets = computed(() =>
  managedAssets.value.filter(
    (asset) =>
      asset.asset_type === resourceTab.value &&
      includesKeyword(
        asset.name,
        asset.id,
        asset.department,
        asset.lifecycle_status,
        asset.submitter,
        asset.version,
        asset.file_name
      )
  )
)
const developmentRecords = computed(() => [
  ...projects.value.map((project) => ({ type: 'rpa', status: project.status })),
  ...managedAssets.value.map((asset) => ({
    type: asset.asset_type,
    status: asset.lifecycle_status,
  })),
])
const countTypes = (records) => ({
  rpa: records.filter((record) => record.type === 'rpa').length,
  skill: records.filter((record) => record.type === 'skill').length,
  python: records.filter((record) => record.type === 'python_plugin').length,
})
const summaryCards = computed(() => {
  const definitions = [
    { key: 'total', label: '项目总数', icon: '#', iconClass: 'ic-blue' },
    { key: '在编', label: '在编', icon: '↻', iconClass: 'ic-amber' },
    { key: '使用', label: '使用', icon: '✓', iconClass: 'ic-green' },
    { key: '大修', label: '大修', icon: '◆', iconClass: 'ic-violet' },
    { key: '停用', label: '停用', icon: '■', iconClass: 'ic-red' },
  ]
  return definitions.map((definition) => {
    const records =
      definition.key === 'total'
        ? developmentRecords.value
        : developmentRecords.value.filter((record) => record.status === definition.key)
    return {
      ...definition,
      total: records.length,
      breakdown: countTypes(records),
    }
  })
})

const groupedProjects = computed(() => {
  const groups = {}
  filteredProjects.value.forEach((project) => {
    const dept = departmentOf(project.name)
    if (!groups[dept]) groups[dept] = []
    groups[dept].push(project)
  })
  return Object.entries(groups)
    .map(([name, items]) => ({
      name,
      items: [...items].sort((a, b) => (a.progress || 0) - (b.progress || 0)),
      inDevelopment: items.filter((item) => item.status === '在编').length,
      disabled: items.filter((item) => item.status === '停用').length,
    }))
    .sort((a, b) => b.inDevelopment - a.inDevelopment || b.items.length - a.items.length)
})

const groupedAssets = computed(() => {
  const groups = {}
  visibleAssets.value.forEach((asset) => {
    const dept = departmentGroup(asset.department)
    if (!groups[dept]) groups[dept] = []
    groups[dept].push(asset)
  })
  return Object.entries(groups)
    .map(([name, items]) => ({
      name,
      items: [...items].sort((a, b) => (a.progress || 0) - (b.progress || 0)),
      inDevelopment: items.filter((item) => item.lifecycle_status === '在编').length,
      disabled: items.filter((item) => item.lifecycle_status === '停用').length,
    }))
    .sort((a, b) => b.inDevelopment - a.inDevelopment || b.items.length - a.items.length)
})

const collapsed = ref({})
const groupKey = (type, name) => `${type}:${name}`
const isOpen = (type, name, inDevelopment) => {
  const key = groupKey(type, name)
  if (key in collapsed.value) return !collapsed.value[key]
  return inDevelopment > 0
}
const toggle = (type, group) => {
  const key = groupKey(type, group.name)
  collapsed.value = {
    ...collapsed.value,
    [key]: isOpen(type, group.name, group.inDevelopment),
  }
}

const toggleLogs = (id) => {
  expandedLogs.value = { ...expandedLogs.value, [id]: !expandedLogs.value[id] }
}
const barClass = (status, progress) => {
  if (status === '停用') return 'is-zero'
  if ((progress || 0) >= 100) return 'is-done'
  if ((progress || 0) > 0) return 'is-active'
  return 'is-zero'
}
const statusChip = (status) =>
  ({ 在编: 'chip-amber', 使用: 'chip-blue', 大修: 'chip-violet', 停用: 'chip-gray' }[status] || 'chip-gray')
const automaticStatus = (progress) => (Number(progress) >= 100 ? '使用' : '在编')
const canEditResource = (resource) => {
  if (props.readOnly) return false
  if (!props.selfService) return true
  if (typeof resource?.can_edit === 'boolean') return resource.can_edit
  return resource?.is_owned !== false
}

onMounted(async () => {
  loading.value = true
  try {
    const projectRequest = props.readScope
      ? http.get(`${props.apiPrefix}/get_projects`, {
          params: { scope: props.readScope },
        })
      : http.get(`${props.apiPrefix}/get_projects`)
    const assetRequest = fetchAdminAssets({
      apiPrefix: props.apiPrefix,
      ...(props.readScope ? { scope: props.readScope } : {}),
    })
    const [projectRes, assetRes] = await Promise.all([
      projectRequest,
      assetRequest,
    ])
    projects.value = (projectRes.data.data || []).map((project) => ({
      ...project,
      progress: Number(project.progress || 0),
    }))
    assets.value = (assetRes.data?.data || []).map((asset) => {
      const progress = Number(asset.progress || 0)
      return {
        ...asset,
        progress,
        lifecycle_status: asset.lifecycle_status || automaticStatus(progress),
      }
    })
  } catch (error) {
    console.error('获取开发资源数据失败：', error)
    ElMessage.error('获取开发资源数据失败')
  } finally {
    loading.value = false
  }
})

const openProjectDialog = (project) => {
  if (!canEditResource(project)) {
    ElMessage.warning('普通用户只能修改自己上传的 RPA 项目')
    return
  }
  currentProject.value = project
  newProgress.value = project.progress || 0
  newRemark.value = ''
  newProjectStatus.value = LIFECYCLE_STATUSES.includes(project.status) ? project.status : '在编'
  projectDialogVisible.value = true
}
const updateProjectProgress = async () => {
  if (!currentProject.value || updating.value) return
  updating.value = true
  try {
    const res = await http.post(`${props.apiPrefix}/update_progress`, {
      project_id: currentProject.value.id,
      progress: newProgress.value,
      status: newProjectStatus.value,
      remark: newRemark.value,
    })
    if (res.data.success) {
      const updated = projects.value.find((project) => project.id === currentProject.value.id)
      if (updated) {
        updated.progress = Number(res.data.progress)
        updated.status = res.data.status
        ;(updated.logs || (updated.logs = [])).unshift({
          developer_name: '当前用户',
          status: res.data.status,
          remark: newRemark.value,
          log_time: new Date().toLocaleString(),
        })
      }
      ElMessage.success('RPA 项目更新成功')
      projectDialogVisible.value = false
    }
  } catch (error) {
    ElMessage.error(`更新失败: ${error.response?.data?.message || error.message}`)
  } finally {
    updating.value = false
  }
}

const pendingAssetStatus = computed(() =>
  assetStatusMode.value === 'auto' ? automaticStatus(newAssetProgress.value) : newAssetStatus.value
)
const openAssetDialog = (asset) => {
  if (!canEditResource(asset)) {
    ElMessage.warning('普通用户只能修改自己上传的 Skill 或 Python 文件')
    return
  }
  currentAsset.value = asset
  newAssetProgress.value = asset.progress || 0
  assetStatusMode.value = ['大修', '停用'].includes(asset.lifecycle_status) ? 'manual' : 'auto'
  newAssetStatus.value = LIFECYCLE_STATUSES.includes(asset.lifecycle_status)
    ? asset.lifecycle_status
    : automaticStatus(asset.progress)
  assetDialogVisible.value = true
}
const updateAsset = async () => {
  if (!currentAsset.value || assetUpdating.value) return
  assetUpdating.value = true
  try {
    const res = await updateAssetProgress({
      id: currentAsset.value.id,
      progress: newAssetProgress.value,
      lifecycleStatus: assetStatusMode.value === 'auto' ? 'auto' : newAssetStatus.value,
      apiPrefix: props.apiPrefix,
    })
    const updated = assets.value.find((asset) => asset.id === currentAsset.value.id)
    if (updated) {
      updated.progress = Number(res.data.progress)
      updated.lifecycle_status = res.data.lifecycle_status
    }
    ElMessage.success(`${resourceLabel.value}更新成功`)
    assetDialogVisible.value = false
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '资产进度更新失败')
  } finally {
    assetUpdating.value = false
  }
}
</script>

<template>
  <div class="admin-page" :class="{ 'is-embedded': embedded }">
    <div class="admin-page-head">
      <h2 class="admin-page-title">{{ readOnly ? '全公司项目进度' : '开发进度管理' }}</h2>
      <p class="admin-page-sub">
        {{ readOnly
          ? '实时查看全公司 RPA、Skill 和 Python 插件开发进度'
          : selfService
            ? '查看全平台进度；普通用户仅可更新本人上传内容，管理员可更新全部'
            : '统一管理 RPA、Skill 和 Python 插件的进度及生命周期状态' }}
      </p>
    </div>

    <div class="admin-stats lifecycle-summary">
      <div v-for="card in summaryCards" :key="card.key" class="admin-stat">
        <div class="admin-stat-top">
          <span class="admin-stat-ic" :class="card.iconClass">{{ card.icon }}</span>
          <span class="admin-stat-label">{{ card.label }}</span>
        </div>
        <div class="admin-stat-value">{{ card.total }}</div>
        <div class="summary-breakdown">
          <span>RPA {{ card.breakdown.rpa }}</span>
          <span>Skill {{ card.breakdown.skill }}</span>
          <span>Python {{ card.breakdown.python }}</span>
        </div>
      </div>
    </div>

    <div class="progress-toolbar">
      <el-radio-group v-model="resourceTab" class="resource-tabs">
        <el-radio-button value="rpa">RPA 程序（{{ projects.length }}）</el-radio-button>
        <el-radio-button value="skill">Skill 文件（{{ managedAssets.filter(a => a.asset_type === 'skill').length }}）</el-radio-button>
        <el-radio-button value="python_plugin">Python 插件（{{ managedAssets.filter(a => a.asset_type === 'python_plugin').length }}）</el-radio-button>
      </el-radio-group>
      <el-input
        v-model="searchKeyword"
        class="progress-search"
        clearable
        aria-label="搜索开发项目"
        placeholder="搜索项目名称、部门、状态或人员"
      />
    </div>

    <template v-if="resourceTab === 'rpa'">
      <p v-if="!loading && filteredProjects.length === 0" class="admin-empty">
        {{ searchKeyword.trim() ? '没有匹配的 RPA 项目' : '暂无 RPA 项目数据' }}
      </p>
      <div v-for="group in groupedProjects" :key="group.name" class="dept-group">
        <button class="dept-group-head" @click="toggle('rpa', group)">
          <span class="dept-group-name">{{ group.name }}</span>
          <span class="dept-group-count">{{ group.items.length }} 个项目</span>
          <span v-if="group.inDevelopment > 0" class="chip chip-amber">在编 {{ group.inDevelopment }}</span>
          <span v-if="group.disabled > 0" class="chip chip-gray">停用 {{ group.disabled }}</span>
          <span class="dept-group-spacer"></span>
          <span class="dept-group-chev" :class="{ open: isOpen('rpa', group.name, group.inDevelopment) }"></span>
        </button>
        <div v-if="isOpen('rpa', group.name, group.inDevelopment)" class="dept-group-body">
          <div v-for="project in group.items" :key="project.id" class="proj-row">
            <div class="proj-main">
              <span class="record-id">RPA #{{ project.id }}</span>
              <span class="proj-name" :title="project.name">{{ project.name }}</span>
              <span class="chip" :class="statusChip(project.status)">{{ project.status }}</span>
              <div class="admin-bar-track">
                <div class="admin-bar-fill" :class="barClass(project.status, project.progress)" :style="{ width: project.progress + '%' }"></div>
              </div>
              <span class="proj-pct">{{ project.progress }}%</span>
              <button
                v-if="canEditResource(project)"
                class="btn-mini btn-mini-gray"
                @click="openProjectDialog(project)"
              >更新</button>
              <span v-else-if="!readOnly" class="read-only-label">仅查看</span>
              <button class="proj-log-btn" :class="{ open: expandedLogs[project.id] }" @click="toggleLogs(project.id)">
                日志<span class="proj-log-chev"></span>
              </button>
            </div>
            <div v-if="expandedLogs[project.id]" class="proj-logs">
              <el-timeline v-if="project.logs && project.logs.length">
                <el-timeline-item
                  v-for="(log, index) in project.logs"
                  :key="index"
                  :timestamp="log.log_time"
                  placement="top"
                  :type="project.status === '使用' ? 'success' : 'primary'"
                >
                  <div class="log-line"><b>开发人员：</b>{{ log.developer_name }}</div>
                  <div class="log-line"><b>状态：</b>{{ log.status }}</div>
                  <div class="log-line"><b>备注：</b>{{ log.remark }}</div>
                </el-timeline-item>
              </el-timeline>
              <p v-else class="proj-nolog">暂无进度日志</p>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template v-else>
      <p class="section-note">仅统计和管理已经审核通过的{{ resourceLabel }}；待审核记录请前往“需求审核”。</p>
      <p v-if="!loading && visibleAssets.length === 0" class="admin-empty">
        {{ searchKeyword.trim() ? `没有匹配的${resourceLabel}` : `暂无已通过的${resourceLabel}` }}
      </p>
      <div v-for="group in groupedAssets" :key="group.name" class="dept-group">
        <button class="dept-group-head" @click="toggle(resourceTab, group)">
          <span class="dept-group-name">{{ group.name }}</span>
          <span class="dept-group-count">{{ group.items.length }} 个项目</span>
          <span v-if="group.inDevelopment > 0" class="chip chip-amber">在编 {{ group.inDevelopment }}</span>
          <span v-if="group.disabled > 0" class="chip chip-gray">停用 {{ group.disabled }}</span>
          <span class="dept-group-spacer"></span>
          <span class="dept-group-chev" :class="{ open: isOpen(resourceTab, group.name, group.inDevelopment) }"></span>
        </button>
        <div v-if="isOpen(resourceTab, group.name, group.inDevelopment)" class="dept-group-body">
          <div v-for="asset in group.items" :key="asset.id" class="proj-row">
            <div class="proj-main">
              <span class="record-id">{{ resourceTab === 'skill' ? 'Skill' : 'Python' }} #{{ asset.id }}</span>
              <span class="proj-name" :title="asset.name">{{ asset.name }}</span>
              <span class="chip" :class="statusChip(asset.lifecycle_status)">{{ asset.lifecycle_status }}</span>
              <div class="admin-bar-track">
                <div class="admin-bar-fill" :class="barClass(asset.lifecycle_status, asset.progress)" :style="{ width: asset.progress + '%' }"></div>
              </div>
              <span class="proj-pct">{{ asset.progress }}%</span>
              <button
                v-if="canEditResource(asset)"
                class="btn-mini btn-mini-gray"
                @click="openAssetDialog(asset)"
              >更新</button>
              <span v-else-if="!readOnly" class="read-only-label">仅查看</span>
              <span class="asset-meta">{{ asset.version || '无版本' }} · {{ asset.submitter }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <el-dialog v-if="!readOnly" v-model="projectDialogVisible" title="更新 RPA 项目" width="540px">
      <el-form label-width="96px" label-position="left">
        <el-form-item label="开发进度：">
          <div class="slider-container">
            <el-slider v-model="newProgress" :min="0" :max="100" show-stops :step="1" class="custom-slider" />
            <span class="progress-value">{{ newProgress }}%</span>
          </div>
        </el-form-item>
        <el-form-item label="最新状态：">
          <el-select v-model="newProjectStatus" style="width: 100%">
            <el-option v-for="status in LIFECYCLE_STATUSES" :key="status" :label="status" :value="status" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态说明：">
          <span class="status-source-note">状态以本次保存生成的最新日志为准，与进度条数值独立。</span>
        </el-form-item>
        <el-form-item label="更新备注：">
          <el-input v-model="newRemark" type="textarea" :rows="4" placeholder="请输入进度说明或状态变更原因..." resize="none" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="projectDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!newRemark.trim()" :loading="updating" @click="updateProjectProgress">确认更新</el-button>
      </template>
    </el-dialog>

    <el-dialog v-if="!readOnly" v-model="assetDialogVisible" :title="`更新${resourceLabel}`" width="520px">
      <el-form label-width="96px" label-position="left">
        <el-form-item label="项目名称：">{{ currentAsset?.name }}</el-form-item>
        <el-form-item label="开发进度：">
          <div class="slider-container">
            <el-slider v-model="newAssetProgress" :min="0" :max="100" show-stops :step="1" class="custom-slider" />
            <span class="progress-value">{{ newAssetProgress }}%</span>
          </div>
        </el-form-item>
        <el-form-item label="状态方式：">
          <el-radio-group v-model="assetStatusMode">
            <el-radio-button value="auto">随进度自动</el-radio-button>
            <el-radio-button value="manual">手动指定</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="assetStatusMode === 'manual'" label="手动状态：">
          <el-select v-model="newAssetStatus" style="width: 100%">
            <el-option v-for="status in LIFECYCLE_STATUSES" :key="status" :label="status" :value="status" />
          </el-select>
        </el-form-item>
        <el-form-item label="保存后状态：">
          <span class="chip" :class="statusChip(pendingAssetStatus)">{{ pendingAssetStatus }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assetDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="assetUpdating" @click="updateAsset">确认更新</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.lifecycle-summary { grid-template-columns: repeat(5, minmax(130px, 1fr)); }
.summary-breakdown {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 9px;
  margin-top: 7px;
  color: var(--brand-muted);
  font-size: 11px;
  line-height: 1.4;
}
.summary-breakdown span { white-space: nowrap; }
.progress-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.resource-tabs { flex: none; }
.progress-search { width: min(360px, 100%); }
.record-id {
  flex: none;
  color: var(--brand-muted);
  font-family: var(--brand-mono);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.admin-page.is-embedded { max-width: none; }
.read-only-label {
  flex: none;
  color: var(--brand-muted);
  font-size: 12px;
  white-space: nowrap;
}
.admin-empty { color: var(--brand-muted); text-align: center; padding: 40px 0; font-size: 14px; }
.section-note { margin: -4px 0 16px; color: var(--brand-muted); font-size: 13px; }
.status-source-note { color: var(--brand-muted); font-size: 13px; line-height: 1.6; }
.slider-container { display: flex; align-items: center; gap: 14px; width: 100%; }
.custom-slider { flex: 1; }
.progress-value { width: 46px; text-align: center; font-weight: 600; color: var(--brand-violet); }
.asset-meta { margin-left: 4px; color: var(--brand-muted); font-size: 12px; white-space: nowrap; }
@media (max-width: 900px) {
  .lifecycle-summary { grid-template-columns: repeat(2, minmax(130px, 1fr)); }
  .progress-toolbar { align-items: stretch; flex-direction: column; }
  .progress-search { width: 100%; }
  .asset-meta { display: none; }
}
</style>
