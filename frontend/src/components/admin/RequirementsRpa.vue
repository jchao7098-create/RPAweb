<!-- RPA 程序（开发需求）审核面板：由 Requirements.vue 审核中心以标签页方式嵌入。
     需求按部门分组折叠展示，含待审核数徽标，默认展开有待办的部门。 -->
<template>
  <div class="admin-page">
    <!-- 统计卡片 -->
    <div class="admin-stats">
      <div class="admin-stat">
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-blue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/></svg></span>
          <span class="admin-stat-label">总需求数</span>
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

    <!-- 按部门分组 -->
    <p v-if="!loading && requirements.length === 0" class="admin-empty">暂无需求数据</p>

    <div v-for="group in groupedByDept" :key="group.name" class="dept-group">
      <button class="dept-group-head" @click="toggle(group.name)">
        <span class="dept-group-name">{{ group.name }}</span>
        <span class="dept-group-count">{{ group.items.length }} 条需求</span>
        <span v-if="group.pending > 0" class="chip chip-amber">待审核 {{ group.pending }}</span>
        <span class="dept-group-spacer"></span>
        <span class="dept-group-chev" :class="{ open: isOpen(group.name) }"></span>
      </button>

      <div v-if="isOpen(group.name)" class="dept-group-body">
        <table class="admin-table">
          <thead>
            <tr>
              <th>项目标题</th>
              <th>需求人</th>
              <th>紧急程度</th>
              <th>期望完成</th>
              <th>状态</th>
              <th style="text-align:right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in group.items" :key="row.id">
              <td class="admin-td-title">{{ row.title }}</td>
              <td>{{ row.requester }}</td>
              <td><span class="chip" :class="urgencyChip(row.urgency)">{{ row.urgency || '—' }}</span></td>
              <td class="admin-td-mono">{{ row.expected_time || '—' }}</td>
              <td><span class="chip" :class="statusChip(row.status)">{{ row.status }}</span></td>
              <td style="text-align:right">
                <button class="btn-mini btn-mini-gray" @click="viewDetail(row)">详情</button>
                <button class="btn-mini btn-mini-green" :disabled="row.status !== '待审核' || approvingId === row.id" @click="approve(row.id)">通过</button>
                <button class="btn-mini btn-mini-red" :disabled="row.status !== '待审核'" @click="openRejectDialog(row)">拒绝</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 详情对话框 -->
    <el-dialog v-model="showDetail" title="需求详情" width="600px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="项目标题">{{ current.title }}</el-descriptions-item>
        <el-descriptions-item label="描述">{{ current.description }}</el-descriptions-item>
        <el-descriptions-item label="需求人">{{ current.requester }}</el-descriptions-item>
        <el-descriptions-item label="部门">{{ current.department }}</el-descriptions-item>
        <el-descriptions-item label="紧急程度">{{ current.urgency }}</el-descriptions-item>
        <el-descriptions-item label="期望完成时间">{{ current.expected_time }}</el-descriptions-item>
        <el-descriptions-item label="反馈时间">{{ current.feedback_time }}</el-descriptions-item>
        <el-descriptions-item label="操作平台">{{ current.platform }}</el-descriptions-item>
        <el-descriptions-item label="操作链接">{{ current.operation_link }}</el-descriptions-item>
        <el-descriptions-item label="登录账号密码">{{ current.credentials }}</el-descriptions-item>
        <el-descriptions-item label="附件">
          <a v-if="current.attachment" :href="current.attachment" target="_blank">点击查看</a>
          <span v-else>无</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 拒绝弹窗 -->
    <el-dialog v-model="rejectDialogVisible" title="拒绝理由">
      <el-input v-model="rejectReason" type="textarea" placeholder="请输入拒绝理由" rows="4" />
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="rejecting" @click="submitReject">确认拒绝</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import http from '@/api/http'
import { departmentGroup } from '@/utils/departments'

const props = defineProps({
  apiPrefix: { type: String, default: '/admin' },
})

const requirements = ref([])
const loading = ref(true)
const approvingId = ref(null) // 正在提交"通过"的需求 id
const rejecting = ref(false)
const showDetail = ref(false)
const current = reactive({})
const rejectDialogVisible = ref(false)
const rejectReason = ref('')
const rejectTargetId = ref(null)

const stats = reactive({ total: 0, pending: 0, approved: 0, rejected: 0 })

const reviewProgress = computed(() =>
  stats.total === 0 ? 0 : Math.round(((stats.approved + stats.rejected) / stats.total) * 100)
)

// 按部门分组：待办多的部门排前面；组内待审核优先
const groupedByDept = computed(() => {
  const groups = {}
  requirements.value.forEach((r) => {
    const dept = departmentGroup(r.department)
    if (!groups[dept]) groups[dept] = []
    groups[dept].push(r)
  })
  return Object.entries(groups)
    .map(([name, items]) => {
      const sorted = [...items].sort((a, b) => {
        if (a.status === '待审核' && b.status !== '待审核') return -1
        if (a.status !== '待审核' && b.status === '待审核') return 1
        return 0
      })
      return { name, items: sorted, pending: items.filter((i) => i.status === '待审核').length }
    })
    .sort((a, b) => b.pending - a.pending || b.items.length - a.items.length)
})

// 折叠状态：默认展开有待审核的部门
const collapsed = ref({})
const isOpen = (name) => {
  if (name in collapsed.value) return !collapsed.value[name]
  const g = groupedByDept.value.find((x) => x.name === name)
  return g ? g.pending > 0 : true
}
const toggle = (name) => { collapsed.value = { ...collapsed.value, [name]: isOpen(name) } }

const calculateStats = () => {
  stats.total = requirements.value.length
  stats.pending = requirements.value.filter((r) => r.status === '待审核').length
  stats.approved = requirements.value.filter((r) => r.status === '已通过').length
  stats.rejected = requirements.value.filter((r) => r.status === '已拒绝').length
}

const fetchRequirements = async () => {
  loading.value = true
  try {
    const res = await http.get(`${props.apiPrefix}/requirements`)
    if (res.data && Array.isArray(res.data)) {
      requirements.value = res.data.map((item) => ({
        id: item.id,
        title: item.title,
        description: item.description,
        requester: item.requester,
        department: item.department,
        urgency: item.urgency,
        expected_time: item.expected_time,
        platform: item.platform,
        status: item.status,
        feedback_time: item.feedback_time,
        operation_link: item.operation_link,
        credentials: item.credentials,
        attachment: item.attachments ? item.attachments[0] : '',
      }))
      calculateStats()
    } else {
      ElMessage.error('无法加载需求数据')
    }
  } catch (error) {
    console.error('获取需求数据失败:', error)
    ElMessage.error('获取需求数据失败')
  } finally {
    loading.value = false
  }
}

const statusChip = (status) =>
  ({ 待审核: 'chip-amber', 已通过: 'chip-green', 已拒绝: 'chip-red' }[status] || 'chip-gray')

const urgencyChip = (u) => ({ 高: 'chip-red', 中: 'chip-amber', 低: 'chip-green' }[u] || 'chip-gray')

const viewDetail = (row) => {
  Object.assign(current, row)
  showDetail.value = true
}

const approve = async (id) => {
  if (approvingId.value) return
  approvingId.value = id
  try {
    await http.post(`${props.apiPrefix}/requirements/approve`, { id })
    const item = requirements.value.find((r) => r.id === id)
    if (item) {
      item.status = '已通过'
      calculateStats()
      ElMessage.success('审核通过')
    }
  } catch (error) {
    console.error('通过操作失败:', error)
    ElMessage.error('通过操作失败')
  } finally {
    approvingId.value = null
  }
}

const openRejectDialog = (row) => {
  rejectTargetId.value = row.id
  rejectDialogVisible.value = true
}

const submitReject = async () => {
  if (!rejectReason.value.trim()) {
    ElMessage.warning('请填写拒绝理由')
    return
  }
  rejecting.value = true
  try {
    await http.post(`${props.apiPrefix}/requirements/reject`, {
      id: rejectTargetId.value,
      reason: rejectReason.value,
    })
    const item = requirements.value.find((r) => r.id === rejectTargetId.value)
    if (item) {
      item.status = '已拒绝'
      calculateStats()
      ElMessage.success('已拒绝需求')
    }
    rejectDialogVisible.value = false
    rejectReason.value = ''
    rejectTargetId.value = null
  } catch (error) {
    console.error('拒绝操作失败:', error)
    ElMessage.error('拒绝操作失败')
  } finally {
    rejecting.value = false
  }
}

onMounted(fetchRequirements)
</script>

<style scoped>
.admin-empty { color: var(--brand-muted); text-align: center; padding: 40px 0; font-size: 14px; }
</style>
