<!-- Skill / Python 插件审核面板。布局、统计和操作与 RPA 需求审核保持一致。 -->
<template>
  <div class="admin-page">
    <el-radio-group v-if="!fixedType" v-model="assetType" class="asset-type-tabs" @change="loadAssets">
      <el-radio-button value="">全部</el-radio-button>
      <el-radio-button value="skill">Skill 文件</el-radio-button>
      <el-radio-button value="python_plugin">Python 插件</el-radio-button>
    </el-radio-group>

    <div class="admin-stats">
      <div class="admin-stat">
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-blue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/></svg></span>
          <span class="admin-stat-label">总提交数</span>
        </div>
        <div class="admin-stat-value">{{ stats.total }}</div>
      </div>
      <div class="admin-stat">
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-amber"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></span>
          <span class="admin-stat-label">待审核</span>
        </div>
        <div class="admin-stat-value">{{ stats.pending }}</div>
      </div>
      <div class="admin-stat">
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-green"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6 9 17l-5-5"/></svg></span>
          <span class="admin-stat-label">已通过</span>
        </div>
        <div class="admin-stat-value">{{ stats.approved }}</div>
      </div>
      <div class="admin-stat">
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-red"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg></span>
          <span class="admin-stat-label">已拒绝</span>
        </div>
        <div class="admin-stat-value">{{ stats.rejected }}</div>
      </div>
      <div class="admin-stat">
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-violet"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="m7 14 4-4 3 3 5-6"/></svg></span>
          <span class="admin-stat-label">审核进度</span>
        </div>
        <div class="admin-stat-value">{{ reviewProgress }}%</div>
        <div class="admin-stat-bar"><div class="admin-stat-bar-fill" :style="{ width: reviewProgress + '%', background: 'var(--brand-violet)' }"></div></div>
      </div>
    </div>

    <p v-if="!loading && assets.length === 0" class="admin-empty">暂无{{ panelLabel }}提交数据</p>

    <div v-for="group in groupedByDept" :key="group.name" class="dept-group">
      <button class="dept-group-head" @click="toggle(group.name)">
        <span class="dept-group-name">{{ group.name }}</span>
        <span class="dept-group-count">{{ group.items.length }} 条提交</span>
        <span v-if="group.pending > 0" class="chip chip-amber">待审核 {{ group.pending }}</span>
        <span class="dept-group-spacer"></span>
        <span class="dept-group-chev" :class="{ open: isOpen(group.name) }"></span>
      </button>

      <div v-if="isOpen(group.name)" class="dept-group-body">
        <table class="admin-table">
          <thead>
            <tr>
              <th>数据库编号</th>
              <th>资产名称</th>
              <th>提交人</th>
              <th>版本</th>
              <th>文件名</th>
              <th>状态</th>
              <th style="text-align:right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in group.items" :key="row.id">
              <td class="admin-td-mono">{{ typeLabel(row.asset_type) }} #{{ row.id }}</td>
              <td class="admin-td-title">{{ row.name }}</td>
              <td>{{ row.submitter }}</td>
              <td class="admin-td-mono">{{ row.version || '—' }}</td>
              <td class="admin-td-mono">{{ row.file_name }}</td>
              <td><span class="chip" :class="statusChip(row.status)">{{ row.status }}</span></td>
              <td style="text-align:right">
                <button class="btn-mini btn-mini-gray" @click="viewDetail(row)">详情</button>
                <button class="btn-mini btn-mini-green" :disabled="row.status !== '待审核' || approvingId === row.id" @click="approve(row.id)">通过</button>
                <button class="btn-mini btn-mini-red" :disabled="row.status !== '待审核'" @click="openReject(row)">拒绝</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <el-dialog v-model="showDetail" :title="`${panelLabel}详情`" width="600px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="数据库编号">{{ typeLabel(current.asset_type) }} #{{ current.id }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ current.name }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ typeLabel(current.asset_type) }}</el-descriptions-item>
        <el-descriptions-item label="部门">{{ current.department }}</el-descriptions-item>
        <el-descriptions-item label="提交人">{{ current.submitter }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ current.version || '—' }}</el-descriptions-item>
        <el-descriptions-item label="文件名">{{ current.file_name }}</el-descriptions-item>
        <el-descriptions-item label="说明">{{ current.description || '—' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ current.status }}</el-descriptions-item>
        <el-descriptions-item label="开发进度">{{ current.progress ?? 0 }}%</el-descriptions-item>
        <el-descriptions-item label="生命周期">{{ current.lifecycle_status || '在编' }}</el-descriptions-item>
        <el-descriptions-item v-if="current.reject_reason" label="拒绝理由">{{ current.reject_reason }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ current.created_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog v-model="rejectVisible" title="拒绝理由" width="480px">
      <el-input v-model="rejectReason" type="textarea" :rows="4" placeholder="请输入拒绝理由" />
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" :loading="rejecting" @click="submitReject">确认拒绝</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { fetchAdminAssets, approveAsset, rejectAsset } from '@/api/assets'

const props = defineProps({
  fixedType: { type: String, default: '' },
  apiPrefix: { type: String, default: '/admin' },
})

const assets = ref([])
const loading = ref(false)
const assetType = ref(props.fixedType || '')
const approvingId = ref(null)
const rejecting = ref(false)
const showDetail = ref(false)
const current = reactive({})
const rejectVisible = ref(false)
const rejectReason = ref('')
const rejectTargetId = ref(null)
const collapsed = ref({})
const stats = reactive({ total: 0, pending: 0, approved: 0, rejected: 0 })

const typeLabel = (type) =>
  type === 'python_plugin' ? 'Python 插件' : type === 'skill' ? 'Skill 文件' : '代码资产'
const panelLabel = computed(() => typeLabel(assetType.value || props.fixedType))
const reviewProgress = computed(() =>
  stats.total === 0 ? 0 : Math.round(((stats.total - stats.pending) / stats.total) * 100)
)
const statusChip = (status) =>
  ({ 待审核: 'chip-amber', 已通过: 'chip-green', 已拒绝: 'chip-red', 停用: 'chip-gray' }[status] || 'chip-gray')

const groupedByDept = computed(() => {
  const groups = {}
  assets.value.forEach((asset) => {
    const dept = asset.department || '未指定部门'
    if (!groups[dept]) groups[dept] = []
    groups[dept].push(asset)
  })
  return Object.entries(groups)
    .map(([name, items]) => {
      const sorted = [...items].sort((a, b) => {
        if (a.status === '待审核' && b.status !== '待审核') return -1
        if (a.status !== '待审核' && b.status === '待审核') return 1
        return 0
      })
      return { name, items: sorted, pending: items.filter((item) => item.status === '待审核').length }
    })
    .sort((a, b) => b.pending - a.pending || b.items.length - a.items.length)
})
const isOpen = (name) => {
  if (name in collapsed.value) return !collapsed.value[name]
  const group = groupedByDept.value.find((item) => item.name === name)
  return group ? group.pending > 0 : true
}
const toggle = (name) => { collapsed.value = { ...collapsed.value, [name]: isOpen(name) } }

const calcStats = () => {
  stats.total = assets.value.length
  stats.pending = assets.value.filter((asset) => asset.status === '待审核').length
  stats.approved = assets.value.filter((asset) => asset.status === '已通过').length
  stats.rejected = assets.value.filter((asset) => asset.status === '已拒绝').length
}

const loadAssets = async () => {
  loading.value = true
  try {
    const params = {}
    if (assetType.value) params.assetType = assetType.value
    const res = await fetchAdminAssets({ ...params, apiPrefix: props.apiPrefix })
    assets.value = res.data?.data ?? []
    calcStats()
  } catch (error) {
    ElMessage.error('加载资产列表失败')
    assets.value = []
  } finally {
    loading.value = false
  }
}

const viewDetail = (row) => {
  Object.assign(current, row)
  showDetail.value = true
}

const approve = async (id) => {
  if (approvingId.value) return
  approvingId.value = id
  try {
    await approveAsset({ id, apiPrefix: props.apiPrefix })
    const item = assets.value.find((asset) => asset.id === id)
    if (item) {
      item.status = '已通过'
      item.reject_reason = null
    }
    calcStats()
    ElMessage.success('审核通过')
  } catch (error) {
    ElMessage.error('通过操作失败')
  } finally {
    approvingId.value = null
  }
}

const openReject = (row) => {
  rejectTargetId.value = row.id
  rejectReason.value = ''
  rejectVisible.value = true
}

const submitReject = async () => {
  if (!rejectReason.value.trim()) {
    ElMessage.warning('请填写拒绝理由')
    return
  }
  rejecting.value = true
  try {
    await rejectAsset({
      id: rejectTargetId.value,
      reason: rejectReason.value,
      apiPrefix: props.apiPrefix,
    })
    const item = assets.value.find((asset) => asset.id === rejectTargetId.value)
    if (item) {
      item.status = '已拒绝'
      item.reject_reason = rejectReason.value
    }
    calcStats()
    ElMessage.success('已拒绝提交')
    rejectVisible.value = false
    rejectReason.value = ''
    rejectTargetId.value = null
  } catch (error) {
    ElMessage.error('拒绝操作失败')
  } finally {
    rejecting.value = false
  }
}

onMounted(loadAssets)
</script>

<style scoped>
.asset-type-tabs { margin-bottom: 18px; }
.admin-empty { color: var(--brand-muted); text-align: center; padding: 40px 0; font-size: 14px; }
</style>
