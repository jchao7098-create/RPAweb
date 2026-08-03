<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  fetchCurrentReport,
  fetchReport,
  fetchReportHistory,
  fetchSubmissionHistory,
  saveCurrentDraft,
  saveReturnedDraft,
  submitCurrentReport,
  submitReturnedReport,
} from '@/api/learning'

const report = ref(null)
const history = ref([])
const submissionHistory = ref([])
const form = ref({ record_date: '', certificate: '', progress: '', program_count: '', blockers: '' })
const historyEditor = ref(null)
const saving = ref(false)
const submitting = ref(false)
const message = ref('')
const error = ref('')

const asReport = (value) => value?.report || value || {}
const copyForm = (value) => ({
  record_date: value?.record_date || value?.week_start || '',
  certificate: value?.certificate || '',
  progress: value?.progress ?? value?.completion ?? '',
  program_count: value?.program_count ?? '',
  blockers: value?.blockers ?? value?.remark ?? value?.content ?? '',
})
const requestPayload = () => ({ ...form.value, draft_revision: report.value?.draft_revision })
const formalHistory = computed(() => submissionHistory.value)
const formatDate = (value) => {
  if (!value) return '—'
  const [year, month, day] = String(value).slice(0, 10).split('-')
  return `${year}/${Number(month)}/${Number(day)}`
}
const stateLabel = (state) => ({
  draft: '草稿',
  submitted: '已提交',
  returned: '退回修改中',
  return_expired: '退回逾期',
}[state] || state || '—')

async function loadCurrent() {
  report.value = asReport(await fetchCurrentReport())
  form.value = copyForm(report.value)
}
async function loadHistory() {
  const [reportsValue, submissionsValue] = await Promise.all([
    fetchReportHistory(),
    fetchSubmissionHistory(),
  ])
  history.value = reportsValue?.items || reportsValue || []
  submissionHistory.value = submissionsValue?.items || submissionsValue || []
}
const editableReportFor = (record) => history.value.find(
  (item) => (item.id || item.report_id) === record.report_id && item.is_editable,
)
function showError(value) {
  error.value = value?.response?.data?.error || value?.response?.data?.message || '操作失败，请稍后重试'
}
async function saveDraft() {
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    report.value = asReport(await saveCurrentDraft(requestPayload()))
    form.value = copyForm(report.value)
    message.value = '草稿已保存'
  } catch (value) {
    showError(value)
  } finally {
    saving.value = false
  }
}
async function submit() {
  submitting.value = true
  error.value = ''
  message.value = ''
  try {
    report.value = asReport(await saveCurrentDraft(requestPayload()))
    form.value = copyForm(report.value)
    await submitCurrentReport({ draft_revision: report.value.draft_revision })
    message.value = '进度记录已正式提交'
    await Promise.all([loadCurrent(), loadHistory()])
  } catch (value) {
    showError(value)
  } finally {
    submitting.value = false
  }
}
async function openHistory(item) {
  const detail = asReport(await fetchReport(item.id || item.report_id))
  historyEditor.value = { ...detail, ...copyForm(detail) }
}
const returnedPayload = () => ({
  record_date: historyEditor.value.record_date,
  certificate: historyEditor.value.certificate,
  progress: historyEditor.value.progress,
  program_count: historyEditor.value.program_count,
  blockers: historyEditor.value.blockers,
  draft_revision: historyEditor.value.draft_revision,
})
async function saveReturned() {
  error.value = ''
  try {
    const saved = asReport(await saveReturnedDraft(historyEditor.value.id, returnedPayload()))
    historyEditor.value = { ...saved, ...copyForm(saved) }
    message.value = '退回记录草稿已保存'
    await loadHistory()
  } catch (value) {
    showError(value)
  }
}
async function submitReturned() {
  error.value = ''
  try {
    const saved = asReport(await saveReturnedDraft(historyEditor.value.id, returnedPayload()))
    await submitReturnedReport(saved.id, { draft_revision: saved.draft_revision })
    historyEditor.value = null
    message.value = '退回记录已重新提交'
    await loadHistory()
  } catch (value) {
    showError(value)
  }
}

onMounted(async () => {
  try {
    await Promise.all([loadCurrent(), loadHistory()])
  } catch (value) {
    showError(value)
  }
})
defineExpose({ report })
</script>

<template>
  <section class="admin-page learning-report">
    <header class="page-head">
      <div>
        <p class="eyebrow">RPA learning progress</p>
        <h1>实习 RPA 进度表</h1>
        <p>每个自然周填写一条学习进度及卡点记录。</p>
      </div>
      <span class="chip">{{ stateLabel(report?.state || 'draft') }}</span>
    </header>

    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <p v-if="message" class="form-success" role="status">{{ message }}</p>

    <div v-if="report" class="panel">
      <div v-if="report.has_unsubmitted_changes" data-test="unsubmitted-changes" class="state-banner">
        有未提交修改；管理员看到的仍是最近一次正式版本。
      </div>
      <div v-if="report.state === 'returned'" class="state-banner warning">
        已退回：{{ report.return_history?.[0]?.reason || '请按要求修改' }}，截止 {{ report.return_deadline }}
      </div>
      <div v-if="report.state === 'return_expired'" class="state-banner danger">
        退回修改期限已过，当前记录不可编辑。
      </div>

      <div v-if="report.latest_submission" class="formal-version">
        <strong>最近正式版本</strong>
        <span>{{ formatDate(report.latest_submission.record_date) }}</span>
        <span>{{ report.latest_submission.certificate || '—' }}</span>
        <span>进度 {{ report.latest_submission.progress ?? '—' }}%</span>
        <span>程序 {{ report.latest_submission.program_count ?? '—' }} 个</span>
      </div>

      <div class="field-grid four-fields">
        <label>
          时间
          <input
            v-model="form.record_date"
            data-test="record-date"
            type="date"
            :disabled="!report.is_editable"
          />
        </label>
        <label>
          证书
          <input
            v-model="form.certificate"
            data-test="certificate"
            type="text"
            placeholder="例如：初级 / 中级"
            :disabled="!report.is_editable"
          />
        </label>
        <label>
          进度（%）
          <input
            v-model="form.progress"
            data-test="progress"
            type="number"
            min="0"
            max="100"
            :disabled="!report.is_editable"
          />
        </label>
        <label>
          已编/在编程序数
          <input
            v-model="form.program_count"
            data-test="program-count"
            type="number"
            min="0"
            max="9999"
            step="1"
            :disabled="!report.is_editable"
          />
        </label>
      </div>
      <label>
        学习卡点
        <textarea
          v-model="form.blockers"
          data-test="blockers"
          placeholder="没有卡点时可填写“无”"
          :disabled="!report.is_editable"
        />
      </label>
      <div class="actions">
        <button data-test="save-draft" class="btn btn-gray" :disabled="!report.is_editable || saving" @click="saveDraft">
          {{ saving ? '保存中…' : '保存草稿' }}
        </button>
        <button data-test="submit" class="btn btn-black" :disabled="!report.is_editable || submitting" @click="submit">
          {{ submitting ? '提交中…' : '正式提交' }}
        </button>
      </div>
    </div>

    <section class="panel history">
      <div class="section-head">
        <div>
          <p class="eyebrow">History</p>
          <h2>学习进度以及卡点</h2>
        </div>
      </div>
      <div class="table-wrap">
        <table data-test="progress-history">
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
            <tr v-for="item in formalHistory" :key="item.submission_id">
              <td>
                {{ formatDate(item.record_date || item.week_start) }}
                <small>{{ stateLabel(item.state) }}</small>
              </td>
              <td>{{ item.certificate || '—' }}</td>
              <td>{{ item.progress ?? '—' }}%</td>
              <td>{{ item.program_count ?? '—' }}</td>
              <td class="blockers-cell">
                {{ item.blockers || '无' }}
                <button
                  v-if="editableReportFor(item)"
                  class="inline-action"
                  @click="openHistory(editableReportFor(item))"
                >
                  修改
                </button>
              </td>
            </tr>
            <tr v-if="!formalHistory.length">
              <td colspan="5" class="empty-cell">暂无正式提交记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="historyEditor" class="panel">
      <div class="section-head">
        <h2>退回记录编辑</h2>
        <button class="inline-action" @click="historyEditor = null">关闭</button>
      </div>
      <div class="field-grid four-fields">
        <label>时间<input v-model="historyEditor.record_date" type="date" /></label>
        <label>证书<input v-model="historyEditor.certificate" type="text" /></label>
        <label>进度（%）<input v-model="historyEditor.progress" type="number" min="0" max="100" /></label>
        <label>已编/在编程序数<input v-model="historyEditor.program_count" type="number" min="0" step="1" /></label>
      </div>
      <label>学习卡点<textarea v-model="historyEditor.blockers" /></label>
      <div class="actions">
        <button class="btn btn-gray" @click="saveReturned">保存退回草稿</button>
        <button class="btn btn-black" @click="submitReturned">重新提交</button>
      </div>
    </section>
  </section>
</template>

<style scoped>
.admin-page { max-width: 1080px; margin: 0 auto; }
.page-head,.section-head { display:flex; justify-content:space-between; gap:16px; align-items:start; }
.page-head h1,.section-head h2 { margin:4px 0; }
.eyebrow { color:#7c5cff; margin:0; font-weight:700; }
.panel { padding:24px; margin-top:18px; border:1px solid var(--brand-line); border-radius:16px; background:var(--brand-raised); }
.panel label { display:block; margin-top:14px; font-weight:600; }
.panel input,.panel textarea { box-sizing:border-box; width:100%; margin-top:7px; padding:10px; border:1px solid var(--brand-line); border-radius:8px; font:inherit; }
.panel textarea { min-height:112px; resize:vertical; }
.field-grid { display:grid; gap:14px; }
.four-fields { grid-template-columns:1.1fr 1fr .8fr 1.2fr; }
.actions { display:flex; gap:10px; margin-top:18px; }
.state-banner { margin:0 0 14px; padding:12px; border-radius:9px; background:#f2efff; }
.formal-version { display:flex; flex-wrap:wrap; gap:8px 18px; margin:0 0 14px; padding:12px; border-radius:9px; background:#f2efff; }
.formal-version strong { width:100%; }
.warning { background:#fff7e6; }
.danger,.form-error { color:#b42318; background:#fff0ee; }
.form-error,.form-success { padding:10px; border-radius:8px; }
.form-success { color:#157347; background:#edf8f0; }
.table-wrap { overflow:auto; margin-top:14px; }
table { width:100%; min-width:760px; border-collapse:collapse; text-align:left; }
th,td { padding:12px; border:1px solid var(--brand-line); vertical-align:top; }
th { background:var(--brand-soft); white-space:nowrap; }
td small { display:block; margin-top:4px; color:var(--brand-muted); }
.blockers-cell { min-width:260px; white-space:pre-wrap; }
.inline-action { border:0; background:none; color:#6547d9; font:inherit; font-weight:700; cursor:pointer; }
.blockers-cell .inline-action { display:block; margin-top:8px; padding:0; }
.empty-cell { color:var(--brand-muted); text-align:center; }
@media (max-width:760px) {
  .four-fields { grid-template-columns:1fr 1fr; }
  .page-head { flex-direction:column; }
}
@media (max-width:520px) {
  .four-fields { grid-template-columns:1fr; }
  .actions .btn { flex:1; }
}
</style>
