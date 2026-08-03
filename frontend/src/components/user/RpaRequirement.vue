<script setup>
import { computed, ref, onMounted } from 'vue'
import http from '@/api/http'
import { fetchMyRequirements } from '@/api/requirements'
import RequirementEditDialog from './RequirementEditDialog.vue'
import { DEPARTMENT_OPTIONS } from '@/utils/departments'

const form = ref({
  user_id: '',             // ✅ 新增 user_id 字段
  department: '',
  requester: '',
  feedback_time: '',
  priority: '',
  title: '',
  description: '',
  expected_finish_time: '',
  platform: '',
  operation_link: '',
  account: '',
  password: ''
})

const fileList = ref([])
const submitting = ref(false)
const userId = ref('')
const myRequirements = ref([])
const listLoading = ref(false)
const listLoadFailed = ref(false)
const searchKeyword = ref('')
const editVisible = ref(false)
const editingRequirement = ref(null)

const normalizedKeyword = computed(() => searchKeyword.value.trim().toLocaleLowerCase())
const filteredRequirements = computed(() => {
  if (!normalizedKeyword.value) return myRequirements.value
  return myRequirements.value.filter((row) =>
    [
      row.id,
      row.title,
      row.department,
      row.requester,
      row.priority,
      row.status,
      row.platform,
      row.created_at,
    ].some((value) =>
      String(value ?? '').toLocaleLowerCase().includes(normalizedKeyword.value)
    )
  )
})

const statusTagType = (status) => ({
  待审核: 'warning',
  已通过: 'success',
  已拒绝: 'danger',
  已取消: 'info',
}[status] || 'info')

const priorityTagType = (priority) => ({
  高: 'danger',
  中: 'warning',
  低: 'success',
}[priority] || 'info')

const loadMyRequirements = async () => {
  if (!userId.value) return
  listLoading.value = true
  listLoadFailed.value = false
  try {
    const res = await fetchMyRequirements(userId.value)
    myRequirements.value = res.data?.data ?? []
  } catch {
    myRequirements.value = []
    listLoadFailed.value = true
  } finally {
    listLoading.value = false
  }
}

// 页面加载时从 localStorage 获取 user_id
onMounted(() => {
  const uid = localStorage.getItem('user_id')
  if (!uid) {
    ElMessage.error('请先登录')
  } else {
    userId.value = uid
    form.value.user_id = uid
    loadMyRequirements()
  }
})

// 提交需求
const submitRequirement = async () => {
  if (!form.value.department || !form.value.title || !form.value.requester) {
    ElMessage.error('部门、标题和需求人姓名不能为空')
    return
  }

  const formData = new FormData()

  for (const key in form.value) {
    if (form.value[key]) {
      formData.append(key, form.value[key])
    }
  }

  fileList.value.forEach(file => {
    formData.append('attachments', file.raw)
  })

  submitting.value = true
  try {
    await http.post('/user/submit_requirement', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    ElMessage.success('需求提交成功')
    resetForm()
    await loadMyRequirements()
  } catch (err) {
    ElMessage.error('提交失败，请稍后再试')
  } finally {
    submitting.value = false
  }
}

// 重置表单和文件列表
const resetForm = () => {
  fileList.value = []
  form.value = {
    user_id: localStorage.getItem('user_id') || '', // 保留 user_id
    department: '',
    requester: '',
    feedback_time: '',
    priority: '',
    title: '',
    description: '',
    expected_finish_time: '',
    platform: '',
    operation_link: '',
    account: '',
    password: ''
  }
}

const openEdit = (requirement) => {
  if (!requirement?.editable) return
  editingRequirement.value = requirement
  editVisible.value = true
}

const handleEdited = (updated) => {
  if (!updated) {
    loadMyRequirements()
    return
  }
  const index = myRequirements.value.findIndex((item) => item.id === updated.id)
  if (index !== -1) myRequirements.value[index] = updated
}
</script>


<template>
  <div class="admin-page form-page">
    <div class="admin-page-head">
      <h2 class="admin-page-title">上传 RPA 程序</h2>
      <p class="admin-page-sub">提交 RPA 程序开发需求，随后可在“需求审核”中自助审核并进入开发</p>
    </div>

    <div class="panel form-card">
      <el-form :model="form" label-width="120px">
    <!-- 基本信息 -->
    <el-form-item label="*部门名称">
      <el-select
        v-model="form.department"
        filterable
        allow-create
        default-first-option
        placeholder="请选择部门"
        style="width: 100%"
      >
        <el-option
          v-for="option in DEPARTMENT_OPTIONS"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <div class="form-note">请优先选择标准部门；选择“其他”时可直接输入实际部门名称</div>
    </el-form-item>

    <el-form-item label="*需求人姓名">
      <el-input v-model="form.requester" />
      <div class="form-note">请填写您的真实姓名，以便后续沟通联系</div>
    </el-form-item>

    <el-form-item label="*反馈时间">
      <el-date-picker
        v-model="form.feedback_time"
        type="datetime"
        placeholder="选择时间"
        format="YYYY-MM-DD HH:mm:ss"
        value-format="YYYY-MM-DD HH:mm:ss"
      />
      <div class="form-note">请选择您提出需求的具体日期和时间</div>
    </el-form-item>

    <el-form-item label="*紧急程度">
      <el-select v-model="form.priority" placeholder="请选择">
        <el-option label="高" value="高" />
        <el-option label="中" value="中" />
        <el-option label="低" value="低" />
      </el-select>
      <div class="form-note">高：需立即处理；中：2周内处理；低：一个月内处理</div>
    </el-form-item>

    <!-- 需求内容 -->
    <el-form-item label="*需求标题">
      <el-input v-model="form.title" />
      <div class="form-note">严格按照模板填写（部门-需求简介-日报）日报可替换为周报月报，案例：客服部-售后数据获取-日报</div>
    </el-form-item>

    <el-form-item label="*需求描述">
      <el-input type="textarea" v-model="form.description" />
      <div class="form-note">详细描述您的需求，包括当前流程和期望效果</div>
      
    </el-form-item>

    <el-form-item label="*期望完成时间">
      <el-date-picker
        v-model="form.expected_finish_time"
        type="datetime"
        placeholder="选择时间"
        format="YYYY-MM-DD HH:mm:ss"
        value-format="YYYY-MM-DD HH:mm:ss"
      />
      <div class="form-note">请提供您期望完成的时间，我们将根据实际情况安排</div>
    </el-form-item>

    <!-- 平台与账号信息 -->
    <el-form-item label="RPA平台/软件">
      <el-input v-model="form.platform" />
      <div class="form-note">请输入需要自动化的系统/软件名称及版本</div>
    </el-form-item>

    <el-form-item label="操作链接">
      <el-input v-model="form.operation_link" />
      <div class="form-note">请输入系统登录或操作页面的完整URL</div>
    </el-form-item>

    <el-form-item label="登录账号">
      <el-input v-model="form.account" />
      <div class="form-note">请输入测试或生产环境账号</div>
    </el-form-item>

    <el-form-item label="登录密码">
      <el-input v-model="form.password" show-password />
      <div class="form-note">请输入对应账号的密码</div>
      <el-tag type="success">如有多个账号请您在附件中写明</el-tag>
    </el-form-item>

    <!-- 附件上传 -->
    <el-form-item label="附件上传">
      <el-upload
        v-model:file-list="fileList"
        :limit="5"
        :auto-upload="false"
        :on-remove="(file, fileList) => fileList"
        :before-upload="() => false"
        accept="video/*,application/pdf,image/*,.xlsx,.xls,.doc,.docx"
        multiple
      >
        <el-button type="primary">选择文件</el-button>
        <template #tip>
          <div class="el-upload__tip">支持上传 PDF、Word、Excel、图片和视频（如 .mp4、.mov）</div>
          <div class="form-note">目前暂不支持文件直接上传，请上传至公盘Z:\运营共享\RPAweb项目\部门，并创建一个文件夹（名字为按照模板需求编写的名称）</div>
          <div class="form-note">建议上传操作视频、相关文档（包含截图操作），大小不超过50MB</div>
          <el-tag type="success">最好是录屏操作以及说明文档，以便最大化开发效率</el-tag>
        </template>
      </el-upload>
    </el-form-item>

    <el-form-item>
      <el-button type="primary" :loading="submitting" @click="submitRequirement">提交需求</el-button>
    </el-form-item>
      </el-form>
    </div>

    <div class="submission-list-head">
      <h3 class="admin-section-title">我上传的 RPA 程序</h3>
      <el-input
        v-model="searchKeyword"
        clearable
        aria-label="搜索我上传的 RPA 程序"
        placeholder="搜索提交编号、标题、部门、状态或人员"
      />
    </div>
    <div class="panel submission-list">
      <el-alert
        v-if="listLoadFailed"
        type="info"
        :closable="false"
        show-icon
        title="上传记录加载失败，请稍后刷新重试"
        style="margin: 12px"
      />

      <el-table
        v-loading="listLoading"
        :data="filteredRequirements"
        :empty-text="searchKeyword ? '没有匹配的上传记录' : '暂无上传记录'"
      >
        <el-table-column label="提交编号" width="125">
          <template #default="{ row }">提交 #{{ row.id }}</template>
        </el-table-column>
        <el-table-column prop="title" label="需求标题" min-width="220" show-overflow-tooltip />
        <el-table-column prop="department" label="部门" min-width="120" show-overflow-tooltip />
        <el-table-column prop="requester" label="提出人" min-width="110" show-overflow-tooltip />
        <el-table-column label="优先级" width="90">
          <template #default="{ row }">
            <el-tag :type="priorityTagType(row.priority)">{{ row.priority || '—' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="155" />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :disabled="!row.editable"
              :title="row.editable ? '修改需求信息' : '已通过或已取消的需求不能修改'"
              @click="openEdit(row)"
            >
              修改
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <RequirementEditDialog
      v-if="editingRequirement"
      v-model="editVisible"
      :requirement="editingRequirement"
      :user-id="userId"
      @saved="handleEdited"
    />
  </div>
</template>

<style scoped>
.form-page { max-width: 1080px; }
.form-card { padding: 28px 32px 12px; }
.submission-list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-top: 28px;
}
.submission-list-head :deep(.admin-section-title) { margin: 0; }
.submission-list-head :deep(.el-input) { width: min(420px, 100%); }
.submission-list { overflow: hidden; }
.submission-list :deep(.el-table) { border-radius: 16px; overflow: hidden; }

.form-note {
  font-size: 12px;
  color: var(--brand-muted);
  margin-top: 5px;
  line-height: 1.5;
  padding-left: 8px;
  border-left: 3px solid var(--brand-violet);
}

@media (max-width: 640px) {
  .form-card { padding: 20px 18px 8px; }
  .submission-list-head { align-items: stretch; flex-direction: column; }
  .submission-list-head :deep(.el-input) { width: 100%; }
}
</style>
