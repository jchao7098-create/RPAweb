<template>
  <div class="admin-page">
    <div class="admin-page-head">
      <h2 class="admin-page-title">系统维护记录</h2>
      <p class="admin-page-sub">
        {{ selfService ? '查看与管理本人参与项目的维护处理记录' : '查看与管理各项目的维护处理记录' }}
      </p>
    </div>

    <!-- 统计卡片 -->
    <div class="admin-stats">
      <div class="admin-stat">
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-blue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2-2z"/></svg></span>
          <span class="admin-stat-label">总维护记录</span>
        </div>
        <div class="admin-stat-value">{{ stats.total }}</div>
      </div>
      <div class="admin-stat">
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-violet"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></span>
          <span class="admin-stat-label">最近 7 天</span>
        </div>
        <div class="admin-stat-value">{{ stats.recent7Days }}</div>
      </div>
      <div class="admin-stat">
        <div class="admin-stat-top">
          <span class="admin-stat-ic ic-green"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/></svg></span>
          <span class="admin-stat-label">活跃维护人员</span>
        </div>
        <div class="admin-stat-value">{{ stats.activeMaintainers }}</div>
      </div>
    </div>

    <!-- 维护记录表格 -->
    <div class="dept-group" v-loading="loading">
      <table class="admin-table">
        <thead>
          <tr>
            <th>项目名称</th>
            <th>维护人员</th>
            <th>需求提出人</th>
            <th>维护日期</th>
            <th>维护详情</th>
            <th style="text-align:right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in maintenanceRecords" :key="row.id">
            <td class="admin-td-title">{{ row.project_name }}</td>
            <td>{{ row.maintainer_name }}</td>
            <td>{{ row.requester_name }}</td>
            <td class="admin-td-mono">{{ formatDate(row.maintenance_date) }}</td>
            <td class="detail-cell">{{ row.maintenance_details }}</td>
            <td style="text-align:right; white-space:nowrap">
              <button class="btn-mini btn-mini-gray" @click="viewDetails(row)">详情</button>
              <button class="btn-mini btn-mini-red" @click="confirmDelete(row.id)">删除</button>
            </td>
          </tr>
          <tr v-if="!loading && maintenanceRecords.length === 0">
            <td colspan="6" class="empty-cell">暂无维护记录</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div class="pagination-container">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="totalRecords"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </div>

    <!-- 维护详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="维护记录详情" width="600px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="项目名称">{{ currentRecord.project_name }}</el-descriptions-item>
        <el-descriptions-item label="维护人员">{{ currentRecord.maintainer_name }} (ID: {{ currentRecord.maintainer_id }})</el-descriptions-item>
        <el-descriptions-item label="需求提出人">{{ currentRecord.requester_name }} (ID: {{ currentRecord.requester_id }})</el-descriptions-item>
        <el-descriptions-item label="维护日期">{{ formatDateTime(currentRecord.maintenance_date) }}</el-descriptions-item>
        <el-descriptions-item label="记录创建时间">{{ formatDateTime(currentRecord.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="维护详情">
          <pre style="white-space: pre-wrap; margin: 0; font-family: inherit;">{{ currentRecord.maintenance_details }}</pre>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import http from '@/api/http'
import dayjs from 'dayjs'

const props = defineProps({
  apiPrefix: { type: String, default: '/admin' },
  selfService: { type: Boolean, default: false },
})

const loading = ref(true)
const maintenanceRecords = ref([])
const currentPage = ref(1)
const pageSize = ref(10)
const totalRecords = ref(0)
const detailDialogVisible = ref(false)
const currentRecord = ref({})

const stats = computed(() => {
  const now = new Date()
  const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
  const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
  const recent7Days = maintenanceRecords.value.filter((r) => new Date(r.maintenance_date) >= sevenDaysAgo).length
  const activeMaintainers = new Set(
    maintenanceRecords.value.filter((r) => new Date(r.maintenance_date) >= thirtyDaysAgo).map((r) => r.maintainer_id)
  ).size
  return { total: totalRecords.value || maintenanceRecords.value.length, recent7Days, activeMaintainers }
})

onMounted(() => { fetchData() })

const fetchData = async () => {
  try {
    loading.value = true
    const res = await http.get(`${props.apiPrefix}/maintenance`, {
      params: { page: currentPage.value, per_page: pageSize.value },
    })
    maintenanceRecords.value = res.data.items
    totalRecords.value = res.data.total
  } catch (error) {
    ElMessage.error('获取维护记录失败')
  } finally {
    loading.value = false
  }
}

const formatDate = (date) => dayjs(date).format('YYYY-MM-DD')
const formatDateTime = (date) => dayjs(date).format('YYYY-MM-DD HH:mm')

const viewDetails = (record) => {
  currentRecord.value = record
  detailDialogVisible.value = true
}

const confirmDelete = (id) => {
  ElMessageBox.confirm('确定要删除这条维护记录吗?', '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(async () => {
      try {
        await http.delete(`${props.apiPrefix}/maintenance/${id}`)
        ElMessage.success('删除成功')
        fetchData()
      } catch (error) {
        ElMessage.error('删除失败')
      }
    })
    .catch(() => {})
}
</script>

<style scoped>
.detail-cell {
  max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: var(--brand-muted);
}
.empty-cell { text-align: center; color: var(--brand-muted); padding: 40px 0; }
.pagination-container { margin-top: 20px; display: flex; justify-content: flex-end; }
</style>
