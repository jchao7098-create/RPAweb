<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ASSET_TYPES, ASSET_STATUS_TAG_TYPES } from '@/config/assetTypes'
import { validateFileName } from '@/utils/fileValidation'
import { DEPARTMENT_OPTIONS } from '@/utils/departments'
import { submitAsset, fetchMyAssets } from '@/api/assets'
import AssetEditDialog from './AssetEditDialog.vue'

const props = defineProps({
  // 对应 ASSET_TYPES 里的键，由路由以 props 形式传入
  assetTypeId: {
    type: String,
    required: true,
    validator: (v) => v in ASSET_TYPES,
  },
})

const config = computed(() => ASSET_TYPES[props.assetTypeId])

const userId = ref('')
const form = ref({ name: '', department: '', submitter: '', version: '', description: '', fileName: '' })
const submitting = ref(false)

const myAssets = ref([])
const listLoading = ref(false)
const listLoadFailed = ref(false)
const editVisible = ref(false)
const editingAsset = ref(null)

const resetForm = () => {
  form.value = { name: '', department: '', submitter: '', version: '', description: '', fileName: '' }
}

const loadMyAssets = async () => {
  if (!userId.value) return
  listLoading.value = true
  listLoadFailed.value = false
  try {
    const res = await fetchMyAssets({
      userId: userId.value,
      assetType: config.value.apiType,
    })
    myAssets.value = res.data?.data ?? []
  } catch (err) {
    myAssets.value = []
    listLoadFailed.value = true
  } finally {
    listLoading.value = false
  }
}

onMounted(() => {
  const uid = localStorage.getItem('user_id')
  if (!uid) {
    ElMessage.error('请先登录')
    return
  }
  userId.value = uid
  loadMyAssets()
})

// 同一个组件挂在两条路由上，切换菜单时实例会被复用，必须清空上一类的状态
watch(
  () => props.assetTypeId,
  () => {
    resetForm()
    loadMyAssets()
  }
)

const handleSubmit = async () => {
  if (!userId.value) {
    ElMessage.error('请先登录')
    return
  }
  const name = form.value.name.trim()
  const department = form.value.department.trim()
  const submitter = form.value.submitter.trim()
  if (!name || !department || !submitter) {
    ElMessage.error('名称、部门和提交人姓名不能为空')
    return
  }
  const description = form.value.description.trim()
  if (!description) {
    ElMessage.error(`说明不能为空，请填写${config.value.label}的用途与使用方式`)
    return
  }
  const fileName = form.value.fileName.trim()
  const fileNameError = validateFileName(fileName, config.value)
  if (fileNameError) {
    ElMessage.error(fileNameError)
    return
  }

  submitting.value = true
  try {
    await submitAsset({
      userId: userId.value,
      assetType: config.value.apiType,
      name,
      department,
      submitter,
      version: form.value.version.trim(),
      description,
      fileName,
    })
    ElMessage.success('提交成功，可前往“需求审核”处理')
    resetForm()
    loadMyAssets()
  } catch (err) {
    ElMessage.error('提交失败，请稍后再试')
  } finally {
    submitting.value = false
  }
}

const openEdit = (asset) => {
  editingAsset.value = asset
  editVisible.value = true
}

const handleEdited = (updated) => {
  if (updated) {
    const index = myAssets.value.findIndex((item) => item.id === updated.id)
    if (index !== -1) myAssets.value[index] = updated
  } else {
    loadMyAssets()
  }
}
</script>

<template>
  <div class="admin-page asset-submission">
    <div class="admin-page-head">
      <h2 class="admin-page-title">上传{{ config.label }}</h2>
      <p class="admin-page-sub">登记{{ config.label }}资产，随后可在“需求审核”中自助审核并进入公开看板</p>
    </div>

    <div class="panel form-card">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="暂不支持文件上传"
        description="当前仅登记文件名称，不会上传文件内容。请先将文件保存到约定位置，再填写对应的完整文件名（包含扩展名）后提交。"
        style="margin-bottom: 20px"
      />

      <el-form :model="form" label-width="120px">
        <el-form-item :label="`*${config.label}名称`">
          <el-input v-model="form.name" maxlength="100" show-word-limit />
          <div class="form-note">{{ config.nameHint }}</div>
        </el-form-item>

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

        <el-form-item label="*提交人姓名">
          <el-input v-model="form.submitter" maxlength="50" />
          <div class="form-note">请填写您的真实姓名，以便后续沟通联系</div>
        </el-form-item>

        <el-form-item label="版本号">
          <el-input v-model="form.version" maxlength="20" placeholder="例如：1.0.0" />
        </el-form-item>

        <el-form-item label="*说明">
          <el-input v-model="form.description" type="textarea" :rows="4" maxlength="2000" show-word-limit />
          <div class="form-note">{{ config.descriptionHint }}</div>
        </el-form-item>

        <el-form-item label="*文件名称">
          <el-input
            v-model="form.fileName"
            maxlength="100"
            show-word-limit
            placeholder="请输入包含扩展名的完整文件名"
          />
          <div class="form-note">
            支持 {{ config.allowedExtensions.join(' / ') }} 格式；请只填写文件名，无需选择或上传文件
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">
            提交
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <h3 class="admin-section-title">我提交的{{ config.label }}</h3>
    <div class="panel">
      <el-alert
        v-if="listLoadFailed"
        type="info"
        :closable="false"
        show-icon
        title="提交记录加载失败，请稍后刷新重试"
        style="margin: 12px"
      />

      <el-table v-loading="listLoading" :data="myAssets" empty-text="暂无提交记录">
        <el-table-column label="数据库编号" width="130">
          <template #default="{ row }">{{ config.label }} #{{ row.id }}</template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="version" label="版本" width="90" />
        <el-table-column prop="file_name" label="文件名" min-width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="ASSET_STATUS_TAG_TYPES[row.status] || 'info'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="170" />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">修改</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <AssetEditDialog
      v-if="editingAsset"
      v-model="editVisible"
      :asset="editingAsset"
      :asset-type-id="props.assetTypeId"
      :user-id="userId"
      @saved="handleEdited"
    />
  </div>
</template>

<style scoped>
.asset-submission { max-width: 860px; }
.form-card { padding: 24px 28px 8px; }
.panel :deep(.el-table) { border-radius: 16px; overflow: hidden; }

.form-note {
  font-size: 12px;
  color: var(--brand-muted);
  margin-top: 5px;
  line-height: 1.5;
  padding-left: 8px;
  border-left: 3px solid var(--brand-violet);
}
</style>
