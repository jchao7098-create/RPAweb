<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  fetchUserLearningHistory,
  fetchUserTrend,
  fetchWeeklyStats,
  loadLearningProfile,
  returnLearningReport,
} from '@/api/learning'
import LearningTrendChart from '@/components/charts/LearningTrendChart.vue'
import { canManageLearning } from '@/utils/learningSession'

const stats = ref(null)
const selected = ref(null)
const trend = ref([])
const historyRecords = ref([])
const weekStart = ref('')
const returnTarget = ref(null)
const returnReason = ref('')
const returnDeadline = ref('')
const error = ref('')
const learningProfile = ref(null)

const monday = (value) => {
  const date = value ? new Date(`${value}T00:00:00`) : new Date()
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7))
  return date.toISOString().slice(0, 10)
}
const formatDate = (value) => {
  if (!value) return '—'
  const [year, month, day] = String(value).slice(0, 10).split('-')
  return `${year}/${Number(month)}/${Number(day)}`
}
const stateLabel = (state) => ({
  missing: '未提交',
  draft: '未提交',
  submitted: '已提交',
  returned: '退回修改中',
  return_expired: '退回逾期',
}[state] || state || '未提交')
const rows = computed(() => stats.value?.rows || stats.value?.roster || [])
const canReturnReports = computed(() => canManageLearning(learningProfile.value))
const metrics = computed(() => [
  ['已提交', stats.value?.submitted_count ?? 0],
  ['未提交', stats.value?.unsubmitted_count ?? 0],
  ['程序总数', stats.value?.total_program_count ?? 0],
  ['平均进度', stats.value?.average_completion == null ? '—' : `${stats.value.average_completion}%`],
])

async function loadDetails(row) {
  const [trendValue, historyValue] = await Promise.all([
    fetchUserTrend(row.user_id, { from_week: undefined, to_week: weekStart.value || undefined }),
    fetchUserLearningHistory(row.user_id),
  ])
  trend.value = trendValue?.points || trendValue?.items || []
  historyRecords.value = historyValue?.items || historyValue || []
}
async function loadStats() {
  error.value = ''
  stats.value = await fetchWeeklyStats({ week_start: weekStart.value || undefined })
  weekStart.value = stats.value?.week_start || weekStart.value || monday()
  if (selected.value) await loadDetails(selected.value)
}
async function loadTrend(row) {
  if (selected.value?.user_id === row.user_id) {
    selected.value = null
    trend.value = []
    historyRecords.value = []
    return
  }
  selected.value = row
  try {
    await loadDetails(row)
  } catch (value) {
    error.value = value?.response?.data?.error || '历史记录加载失败'
  }
}
async function changeWeek() {
  weekStart.value = monday(weekStart.value)
  await loadStats()
}
function openReturn(row) {
  returnTarget.value = row
  returnReason.value = ''
  returnDeadline.value = ''
}
async function confirmReturn() {
  error.value = ''
  if (!returnReason.value.trim() || !returnDeadline.value || new Date(returnDeadline.value) <= new Date()) {
    error.value = '请填写退回原因，并选择晚于当前时间的截止时间。'
    return
  }
  try {
    await returnLearningReport(returnTarget.value.report_id, {
      reason: returnReason.value.trim(),
      edit_deadline: returnDeadline.value,
    })
    returnTarget.value = null
    await loadStats()
  } catch (value) {
    error.value = value?.response?.data?.error || '退回失败'
  }
}
onMounted(async () => {
  weekStart.value = monday()
  try {
    const [profile] = await Promise.all([loadLearningProfile(), loadStats()])
    learningProfile.value = profile
  } catch (value) {
    error.value = value?.response?.data?.error || '统计加载失败'
  }
})
</script>

<template>
  <section class="admin-page learning-stats">
    <header class="page-head">
      <div>
        <p class="eyebrow">Learning insights</p>
        <h1>实习生 RPA 学习情况</h1>
      </div>
      <label>统计周<input v-model="weekStart" type="date" @change="changeWeek" /></label>
    </header>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>

    <div class="kpis">
      <article v-for="metric in metrics" :key="metric[0]" data-test="kpi-card" class="panel kpi">
        <span>{{ metric[0] }}</span>
        <strong>{{ metric[1] }}</strong>
      </article>
    </div>

    <section class="panel">
      <h2>实习生明细</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>人员</th>
              <th>状态</th>
              <th>时间</th>
              <th>证书</th>
              <th>进度</th>
              <th>已编/在编程序数</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in rows"
              :key="row.user_id"
              data-test="roster-row"
              tabindex="0"
              @click="loadTrend(row)"
            >
              <td>{{ row.username || row.name || row.user_id }}</td>
              <td>{{ stateLabel(row.state) }}</td>
              <td>{{ formatDate(row.record_date) }}</td>
              <td>{{ row.certificate || '—' }}</td>
              <td>{{ row.completion == null ? '—' : `${row.completion}%` }}</td>
              <td>{{ row.program_count ?? '—' }}</td>
              <td>
                <button
                  v-if="canReturnReports && row.report_id && row.state === 'submitted'"
                  data-test="return-report"
                  class="btn btn-gray"
                  @click.stop="openReturn(row)"
                >
                  退回修改
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="selected" class="panel detail-panel">
      <h2>{{ selected.username || selected.user_id }} 的趋势</h2>
      <p class="chart-hint">紫色柱为已编/在编程序数，橙色折线为学习进度。</p>
      <LearningTrendChart :points="trend" />

      <h3>历史学习记录</h3>
      <div class="table-wrap">
        <table data-test="admin-progress-history" class="history-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>证书</th>
              <th>进度</th>
              <th>已编/在编程序数</th>
              <th>学习卡点</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in historyRecords" :key="item.submission_id || `${item.report_id}-${item.submitted_at}`">
              <td>
                {{ formatDate(item.record_date || item.week_start) }}
                <small>{{ stateLabel(item.state) }}</small>
              </td>
              <td>{{ item.certificate || '—' }}</td>
              <td>{{ item.progress == null ? '—' : `${item.progress}%` }}</td>
              <td>{{ item.program_count ?? '—' }}</td>
              <td class="blockers-cell">{{ item.blockers || '无' }}</td>
            </tr>
            <tr v-if="!historyRecords.length">
              <td colspan="5" class="empty-cell">暂无正式提交记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="returnTarget" class="dialog-backdrop" role="dialog" aria-modal="true" aria-label="退回进度记录">
      <section class="panel dialog">
        <h2>退回修改</h2>
        <label>退回原因<textarea v-model="returnReason" /></label>
        <label>修改截止时间<input v-model="returnDeadline" type="datetime-local" /></label>
        <div class="actions">
          <button class="btn btn-gray" @click="returnTarget = null">取消</button>
          <button data-test="confirm-return" class="btn btn-black" @click="confirmReturn">确认退回</button>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.admin-page{max-width:1180px;margin:0 auto}
.page-head{display:flex;justify-content:space-between;gap:16px;align-items:end}
.page-head h1{margin:4px 0}
.page-head input{display:block;margin-top:6px;padding:8px;border:1px solid var(--brand-line);border-radius:8px}
.eyebrow{margin:0;color:#7c5cff;font-weight:700}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:18px}
.panel{padding:20px;margin-top:18px;border:1px solid var(--brand-line);border-radius:16px;background:var(--brand-raised)}
.kpi{margin:0;display:grid;gap:8px}
.kpi span{color:var(--brand-muted)}
.kpi strong{font-size:28px}
.table-wrap{overflow:auto}
table{width:100%;min-width:860px;border-collapse:collapse;text-align:left}
th,td{padding:12px;border-bottom:1px solid var(--brand-line);vertical-align:top}
th{white-space:nowrap}
tbody tr[data-test="roster-row"]{cursor:pointer}
.detail-panel h3{margin:24px 0 10px}
.chart-hint{margin:-4px 0 10px;color:var(--brand-muted);font-size:13px}
.history-table{min-width:760px}
.history-table th,.history-table td{border:1px solid var(--brand-line)}
.history-table th{background:var(--brand-soft)}
td small{display:block;margin-top:4px;color:var(--brand-muted)}
.blockers-cell{min-width:260px;white-space:pre-wrap}
.empty-cell{text-align:center;color:var(--brand-muted)}
.form-error{padding:10px;color:#b42318;background:#fff0ee;border-radius:8px}
.dialog-backdrop{position:fixed;inset:0;display:grid;place-items:center;padding:16px;background:rgba(0,0,0,.36);z-index:5}
.dialog{width:min(480px,100%);margin:0}
.dialog label{display:block;margin-top:12px}
.dialog input,.dialog textarea{box-sizing:border-box;width:100%;padding:9px;margin-top:5px;border:1px solid var(--brand-line);border-radius:8px}
.dialog textarea{min-height:90px}
.actions{display:flex;gap:10px;margin-top:18px}
@media(max-width:760px){
  .kpis{grid-template-columns:repeat(2,1fr)}
  .page-head{align-items:start;flex-direction:column}
}
</style>
