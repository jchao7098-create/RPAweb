<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import http from '@/api/http'
import {
  departmentFromProjectName,
  departmentGroup,
  normalizeDepartment,
} from '@/utils/departments'

const projects = ref([])
const requirements = ref([])
const showDetail = ref(false)
const current = reactive({})
const logoMissing = ref(false)
const searchKeyword = ref('')

const normalizedKeyword = computed(() => searchKeyword.value.trim().toLocaleLowerCase())
const includesKeyword = (...values) => {
  if (!normalizedKeyword.value) return true
  return values.some((value) =>
    String(value ?? '').toLocaleLowerCase().includes(normalizedKeyword.value)
  )
}

const filteredRequirements = computed(() =>
  requirements.value.filter((req) =>
    includesKeyword(
      normalizeDepartment(req.department),
      departmentGroup(req.department),
      req.department,
      req.title,
      req.requester,
      req.status,
      req.platform
    )
  )
)
const filteredProjects = computed(() =>
  projects.value.filter((project) =>
    includesKeyword(
      departmentFromProjectName(project.name),
      project.id,
      project.name,
      project.status,
      ...(project.logs || []).map((log) => log.developer_name)
    )
  )
)

const groupedRequirements = computed(() => {
  const groups = {}
  filteredRequirements.value.forEach((req) => {
    const dept = departmentGroup(req.department)
    if (!groups[dept]) groups[dept] = []
    groups[dept].push(req)
  })
  return groups
})

const fetchAllData = async () => {
  try {
    const [projectsRes, requirementsRes] = await Promise.all([
      http.get('/public/projects'),
      http.get('/public/requirements'),
    ])
    projects.value = projectsRes.data.data || []
    requirements.value = requirementsRes.data || []
  } catch (error) {
    ElMessage.error('数据加载失败，请稍后重试')
  }
}

const STATUS_CHIP = {
  待审核: 'chip-amber',
  已通过: 'chip-green',
  已拒绝: 'chip-red',
  在编: 'chip-amber',
  使用: 'chip-blue',
  大修: 'chip-violet',
  停用: 'chip-gray',
  开发中: 'chip-blue',
  已完成: 'chip-green',
}
const chipClass = (status) => STATUS_CHIP[status] || 'chip-gray'

const viewDetail = (row) => {
  Object.assign(current, row)
  showDetail.value = true
}

const processedProjects = computed(() => filteredProjects.value)
const groupedProjects = computed(() => {
  const groups = {}
  processedProjects.value.forEach((project) => {
    const dept = departmentFromProjectName(project.name)
    if (!groups[dept]) groups[dept] = []
    groups[dept].push(project)
  })
  return groups
})

const projectSummary = computed(() => {
  const summary = {}
  processedProjects.value.forEach((project) => {
    const status = project.status || '未知'
    summary[status] = (summary[status] || 0) + 1
  })
  return summary
})

const requirementSummary = computed(() => {
  const summary = {}
  filteredRequirements.value.forEach((req) => {
    const status = req.status || '未知'
    summary[status] = (summary[status] || 0) + 1
  })
  return summary
})

onMounted(fetchAllData)
</script>

<template>
  <div class="aitools-page dept-sort">
    <nav class="aitools-nav">
      <div class="aitools-nav-inner">
        <router-link to="/" class="aitools-brand">
          <img v-if="!logoMissing" class="aitools-brand-logo" src="/logo.png" alt="公司 logo" @error="logoMissing = true" />
          <span class="aitools-brand-name">AI Tools web</span>
        </router-link>
        <div class="aitools-nav-links">
          <router-link class="aitools-nav-link" to="/department-skills">各部门Skill情况</router-link>
          <router-link class="aitools-nav-link" to="/department-plugins">各部门Python插件情况</router-link>
          <router-link class="aitools-nav-link is-active" to="/department">各部门RPA情况</router-link>
        </div>
        <div class="aitools-nav-actions">
          <router-link class="btn btn-gray" to="/">首页</router-link>
          <router-link class="btn btn-black" to="/login">进入统一工作台</router-link>
        </div>
      </div>
    </nav>

    <main class="dept-content">
      <h1 class="page-title">各部门RPA情况</h1>

      <section class="search-panel panel">
        <label class="search-label" for="rpa-department-search">搜索 RPA</label>
        <div class="search-control">
          <input
            id="rpa-department-search"
            v-model="searchKeyword"
            data-test="department-rpa-search"
            type="search"
            class="search-input"
            placeholder="搜索部门、需求标题、提交人、项目名称或状态"
          />
          <button v-if="searchKeyword" class="btn btn-gray btn-sm" type="button" @click="searchKeyword = ''">
            清空
          </button>
        </div>
        <span class="search-result">
          {{
            searchKeyword
              ? `需求 ${filteredRequirements.length}/${requirements.length}，项目 ${filteredProjects.length}/${projects.length}`
              : `需求 ${requirements.length} 个，项目 ${projects.length} 个`
          }}
        </span>
      </section>

      <section class="summary-group">
        <div class="panel summary">
          <span class="summary-label">开发项目</span>
          <div class="chip-row">
            <span v-for="(count, status) in projectSummary" :key="status" class="chip" :class="chipClass(status)">
              {{ status }} {{ count }}
            </span>
            <span v-if="Object.keys(projectSummary).length === 0" class="chip chip-gray">暂无项目数据</span>
          </div>
        </div>
        <div class="panel summary">
          <span class="summary-label">需求</span>
          <div class="chip-row">
            <span v-for="(count, status) in requirementSummary" :key="status" class="chip" :class="chipClass(status)">
              {{ status }} {{ count }}
            </span>
            <span v-if="Object.keys(requirementSummary).length === 0" class="chip chip-gray">暂无需求数据</span>
          </div>
        </div>
      </section>

      <h2 class="section-title">RPA 程序列表（按部门分组）</h2>
      <div v-for="(deptProjects, deptName) in groupedProjects" :key="`project-${deptName}`" class="dept-block panel">
        <h3 class="dept-block-title">
          {{ deptName || '未指定部门' }}
          <span class="dept-block-count">{{ deptProjects.length }} 个项目</span>
        </h3>
        <div class="table-wrap">
          <table class="clean-table" data-test="rpa-project-table">
            <thead>
              <tr>
                <th>数据库编号</th>
                <th>项目名称</th>
                <th>状态</th>
                <th>开发进度</th>
                <th>开发人员</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="project in deptProjects" :key="project.id">
                <td class="td-mono">RPA #{{ project.id }}</td>
                <td class="td-title">{{ project.name }}</td>
                <td><span class="chip" :class="chipClass(project.status)">{{ project.status }}</span></td>
                <td class="td-mono">{{ project.progress ?? 0 }}%</td>
                <td>{{ (project.logs || []).map((log) => log.developer_name).filter(Boolean).join('、') || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <p v-if="filteredProjects.length === 0" class="empty-note">
        {{ searchKeyword ? '没有找到匹配的 RPA 程序' : '暂无 RPA 程序数据' }}
      </p>

      <h2 class="section-title">需求列表（按部门分组）</h2>
      <div v-for="(deptReq, deptName) in groupedRequirements" :key="deptName" class="dept-block panel">
        <h3 class="dept-block-title">
          {{ deptName || '未指定部门' }}
          <span class="dept-block-count">{{ deptReq.length }} 个需求</span>
        </h3>

        <div class="table-wrap">
          <table class="clean-table" data-test="rpa-requirement-table">
            <thead>
              <tr>
                <th>需求标题</th>
                <th>提交人</th>
                <th>状态</th>
                <th>期望完成时间</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in deptReq" :key="row.id">
                <td class="td-title">{{ row.title }}</td>
                <td>{{ row.requester }}</td>
                <td><span class="chip" :class="chipClass(row.status)">{{ row.status }}</span></td>
                <td class="td-mono">{{ row.expected_time }}</td>
                <td><button class="btn btn-gray btn-sm" @click="viewDetail(row)">详情</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <p v-if="filteredRequirements.length === 0" class="empty-note">
        {{ searchKeyword ? '没有找到匹配内容，请更换关键词' : '暂无需求数据' }}
      </p>
    </main>

    <!-- 详情对话框 -->
    <Transition name="modal">
      <div v-if="showDetail" class="modal-overlay" @click.self="showDetail = false">
        <div class="modal-panel">
          <div class="modal-head">
            <h3>详情信息</h3>
            <button class="modal-close" @click="showDetail = false">✕</button>
          </div>
          <dl class="detail-list">
            <template v-for="(value, key) in current" :key="key">
              <div v-if="value && typeof value !== 'object'" class="detail-row">
                <dt>{{ key }}</dt>
                <dd>{{ value }}</dd>
              </div>
            </template>
          </dl>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.dept-content {
  max-width: 1000px;
  margin: 0 auto;
  padding: 40px 32px 72px;
}
.page-title { font-size: 30px; font-weight: 800; margin: 0 0 24px; }

.search-panel {
  display: grid;
  grid-template-columns: auto minmax(260px, 1fr) auto;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  margin-bottom: 16px;
}
.search-label { font-size: 14px; font-weight: 700; white-space: nowrap; }
.search-control { display: flex; align-items: center; gap: 8px; }
.search-input {
  box-sizing: border-box;
  width: 100%;
  height: 38px;
  padding: 0 13px;
  border: 1px solid var(--brand-line);
  border-radius: 10px;
  background: var(--brand-raised);
  color: var(--brand-text);
  font: inherit;
  outline: none;
}
.search-input:focus { border-color: #9fb6f3; box-shadow: 0 0 0 3px rgba(91, 124, 250, 0.12); }
.search-result { color: var(--brand-muted); font-size: 12.5px; white-space: nowrap; }

.summary-group { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 32px; }
.summary { padding: 20px 22px; }
.summary-label { color: var(--brand-muted); font-size: 13px; display: block; margin-bottom: 12px; }
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }

.section-title { font-size: 22px; font-weight: 700; margin: 0 0 18px; }

.dept-block { margin-bottom: 16px; overflow: hidden; }
.dept-block-title {
  font-size: 15.5px;
  font-weight: 700;
  margin: 0;
  padding: 16px 20px;
  border-bottom: 1px solid var(--brand-line);
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.dept-block-count { font-family: var(--brand-mono); color: var(--brand-muted); font-size: 12.5px; font-weight: 400; }

.table-wrap { overflow-x: auto; }
.clean-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.clean-table th {
  text-align: left;
  color: var(--brand-muted);
  font-weight: 500;
  font-size: 12.5px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--brand-line);
  white-space: nowrap;
}
.clean-table td { padding: 12px 20px; border-bottom: 1px solid var(--brand-line); white-space: nowrap; }
.clean-table tbody tr:last-child td { border-bottom: none; }
.clean-table tbody tr:hover { background: #fafaf7; }
.td-title { font-weight: 600; white-space: normal; }
.td-mono { font-family: var(--brand-mono); font-size: 13px; color: var(--brand-muted); }
.empty-note { color: var(--brand-muted); font-size: 14px; padding: 24px 0; text-align: center; }

/* 详情弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(20, 20, 19, 0.32);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.modal-panel {
  width: 100%;
  max-width: 560px;
  background: var(--brand-raised);
  border-radius: 16px;
  padding: 28px 32px;
  box-shadow: 0 24px 70px rgba(20, 20, 19, 0.18);
  max-height: 80vh;
  overflow-y: auto;
}
.modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.modal-head h3 { margin: 0; font-size: 18px; font-weight: 700; }
.modal-close {
  background: none;
  border: none;
  color: var(--brand-muted);
  font-size: 14px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 999px;
  transition: color 0.18s, background 0.18s;
}
.modal-close:hover { color: var(--brand-text); background: #f0f0ec; }
.detail-list { margin: 0; }
.detail-row {
  display: flex;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--brand-line);
  font-size: 14px;
}
.detail-row:last-child { border-bottom: none; }
.detail-row dt { width: 120px; flex: none; color: var(--brand-muted); }
.detail-row dd { margin: 0; flex: 1; line-height: 1.65; word-break: break-all; }

.modal-enter-active, .modal-leave-active { transition: opacity 0.22s; }
.modal-enter-active .modal-panel, .modal-leave-active .modal-panel { transition: transform 0.22s cubic-bezier(0.22, 1, 0.36, 1); }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal-panel, .modal-leave-to .modal-panel { transform: translateY(12px) scale(0.98); }

@media (max-width: 900px) {
  .aitools-nav-links { display: none; }
  .dept-content { padding: 28px 20px 56px; }
  .search-panel { grid-template-columns: 1fr; gap: 8px; }
  .summary-group { grid-template-columns: 1fr; }
}
</style>
