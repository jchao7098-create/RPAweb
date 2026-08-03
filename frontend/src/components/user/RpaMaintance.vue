<template>
  <div class="admin-page">
    <div class="admin-page-head">
      <h2 class="admin-page-title">我的维护记录</h2>
      <p class="admin-page-sub">查看我名下项目的维护工单，以及 Skill / 插件的审核结果</p>
    </div>

    <!-- 维护统计卡片 -->
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
          <span class="admin-stat-ic ic-green"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg></span>
          <span class="admin-stat-label">维护项目数</span>
        </div>
        <div class="admin-stat-value">{{ stats.projectsCount }}</div>
      </div>
    </div>

    <!-- 维护记录表格 -->
    <div class="panel" v-loading="loading">
      <table class="admin-table">
        <thead>
          <tr><th>项目名称</th><th>需求提出人</th><th>维护日期</th><th>维护详情</th><th style="text-align:right">操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in maintenanceRecords" :key="row.id">
            <td class="admin-td-title">{{ row.project_name }}</td>
            <td>{{ row.requester_name }}</td>
            <td class="admin-td-mono">{{ formatDate(row.maintenance_date) }}</td>
            <td class="detail-cell">{{ row.maintenance_details }}</td>
            <td style="text-align:right"><button class="btn-mini btn-mini-gray" @click="viewDetails(row)">详情</button></td>
          </tr>
          <tr v-if="!loading && maintenanceRecords.length === 0"><td colspan="5" class="empty-cell">暂无维护记录</td></tr>
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

    <!-- Skill / Python 插件审核记录：资产暂无独立维护流程，先呈现审核结论与拒绝理由 -->
    <h3 class="admin-section-title">Skill / Python 插件审核记录 ({{ assetRecords.length }})</h3>
    <div class="panel" v-loading="assetsLoading">
      <table class="admin-table">
        <thead>
          <tr><th>类型</th><th>名称</th><th>文件名</th><th>状态</th><th>拒绝理由</th><th>提交时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in assetRecords" :key="row.type_label + row.id">
            <td>{{ row.type_label }}</td>
            <td class="admin-td-title">{{ row.name }}</td>
            <td class="admin-td-mono">{{ row.file_name }}</td>
            <td><span class="chip" :class="assetChip(row.status)">{{ row.status }}</span></td>
            <td class="detail-cell">{{ row.reject_reason || '—' }}</td>
            <td class="admin-td-mono">{{ row.created_at }}</td>
          </tr>
          <tr v-if="!assetsLoading && assetRecords.length === 0"><td colspan="6" class="empty-cell">暂无 Skill / 插件提交记录</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 维护详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="维护记录详情" width="600px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="项目名称">{{ currentRecord.project_name }}</el-descriptions-item>
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
  import { ref, reactive, onMounted, computed } from 'vue'
  import http from '@/api/http'
  import dayjs from 'dayjs'
  import { fetchMyAssets } from '@/api/assets'

  // 数据状态
  const loading = ref(true)
  const assetRecords = ref([])
  const assetsLoading = ref(false)
  const maintenanceRecords = ref([])
  const currentPage = ref(1)
  const pageSize = ref(10)
  const totalRecords = ref(0)
  const detailDialogVisible = ref(false)
  const currentRecord = ref({})
  
  // 获取当前用户ID - 这里假设从本地存储或状态管理获取
  const getCurrentUserId = () => {
    // 实际项目中应该从登录状态或token中获取
    return localStorage.getItem('user_id') || 'current_user_id'
  }
  
  // 计算统计信息
  const stats = computed(() => {
    const now = new Date()
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
    
    // 计算最近7天的记录
    const recent7Days = maintenanceRecords.value.filter(record => 
      new Date(record.maintenance_date) >= sevenDaysAgo
    ).length
    
    // 计算维护的项目数量
    const projectsCount = new Set(
      maintenanceRecords.value.map(record => record.project_id)
    ).size
    
    return {
      total: maintenanceRecords.value.length,
      recent7Days,
      projectsCount
    }
  })
  
  // 资产审核状态 → chip 配色
  const assetChip = (status) =>
    ({ '待审核': 'chip-amber', '已通过': 'chip-green', '已拒绝': 'chip-red' }[status] || 'chip-gray')

  // 拉取我的 Skill / 插件提交记录（与维护记录互不影响，失败时静默留空表）
  const fetchAssetRecords = async () => {
    const userId = localStorage.getItem('user_id')
    if (!userId) return // 未登录：资产接口 int(user_id) 会 400，直接跳过
    assetsLoading.value = true
    try {
      const [skillRes, pluginRes] = await Promise.all([
        fetchMyAssets({ userId, assetType: 'skill' }),
        fetchMyAssets({ userId, assetType: 'python_plugin' }),
      ])
      assetRecords.value = [
        ...(skillRes.data?.data ?? []).map(a => ({ ...a, type_label: 'Skill 文件' })),
        ...(pluginRes.data?.data ?? []).map(a => ({ ...a, type_label: 'Python 插件' })),
      ]
    } catch (e) {
      assetRecords.value = []
    } finally {
      assetsLoading.value = false
    }
  }

  // 初始化加载数据
  onMounted(() => {
    fetchData()
    fetchAssetRecords()
  })
  
  // 获取当前用户的维护记录数据
  const fetchData = async () => {
    try {
      loading.value = true
      const userId = getCurrentUserId()
      const res = await http.get('/user/maintenance', {
        params: {
          user_id: userId,
          page: currentPage.value,
          per_page: pageSize.value
        }
      })
      maintenanceRecords.value = res.data.items || []
      totalRecords.value = res.data.total || 0
    } catch (error) {
      ElMessage.error('获取维护记录失败')
      console.error('Error fetching maintenance records:', error)
    } finally {
      loading.value = false
    }
  }
  
  // 日期格式化
  const formatDate = (date) => {
    return dayjs(date).format('YYYY-MM-DD')
  }
  
  const formatDateTime = (date) => {
    return dayjs(date).format('YYYY-MM-DD HH:mm')
  }
  
  // 查看详情
  const viewDetails = (record) => {
    currentRecord.value = record
    detailDialogVisible.value = true
  }
  </script>
  
  
  <style scoped>
  /* 统计卡 / 表格 / 段标题样式已提到 theme.css 共享（admin-* 系列） */
  .detail-cell {
    max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    color: var(--brand-muted);
  }
  .empty-cell { text-align: center; color: var(--brand-muted); padding: 34px 0; font-size: 13.5px; }
  .pagination-container { margin-top: 18px; display: flex; justify-content: flex-end; }
  </style>