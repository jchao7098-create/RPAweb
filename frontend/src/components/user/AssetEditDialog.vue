<script setup>
import { computed, reactive, watch } from 'vue'
import { ASSET_TYPES } from '@/config/assetTypes'
import { updateMyAsset } from '@/api/assets'
import { validateFileName } from '@/utils/fileValidation'
import { DEPARTMENT_OPTIONS } from '@/utils/departments'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  asset: { type: Object, default: null },
  assetTypeId: {
    type: String,
    required: true,
    validator: (value) => value in ASSET_TYPES,
  },
  userId: { type: [String, Number], required: true },
})

const emit = defineEmits(['update:modelValue', 'saved'])
const config = computed(() => ASSET_TYPES[props.assetTypeId])
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})
const form = reactive({
  name: '',
  department: '',
  submitter: '',
  version: '',
  description: '',
  fileName: '',
})
const saving = reactive({ active: false })

watch(
  () => [props.modelValue, props.asset],
  ([isVisible, asset]) => {
    if (!isVisible || !asset) return
    Object.assign(form, {
      name: asset.name || '',
      department: asset.department || '',
      submitter: asset.submitter || '',
      version: asset.version || '',
      description: asset.description || '',
      fileName: asset.file_name || '',
    })
  },
  { immediate: true },
)

const save = async () => {
  const name = form.name.trim()
  const department = form.department.trim()
  const submitter = form.submitter.trim()
  const description = form.description.trim()
  const fileName = form.fileName.trim()
  if (!name || !department || !submitter || !description) {
    ElMessage.error('名称、部门、提交人和说明不能为空')
    return
  }
  const fileNameError = validateFileName(fileName, config.value)
  if (fileNameError) {
    ElMessage.error(fileNameError)
    return
  }

  saving.active = true
  try {
    const response = await updateMyAsset({
      id: props.asset.id,
      userId: props.userId,
      name,
      department,
      submitter,
      version: form.version.trim(),
      description,
      fileName,
    })
    ElMessage.success(response.data?.message || '修改已提交，可前往“需求审核”重新处理')
    emit('saved', response.data?.data)
    visible.value = false
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '修改失败，请稍后重试')
  } finally {
    saving.active = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="`修改${config.label}`"
    width="620px"
    :teleported="false"
    destroy-on-close
  >
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="保存后将重新进入待审核"
      description="已通过内容修改后会暂时退出公开看板，开发进度与生命周期需要重新确认。"
      style="margin-bottom: 18px"
    />

    <el-form :model="form" label-width="110px">
      <el-form-item :label="`*${config.label}名称`">
        <el-input v-model="form.name" data-test="edit-name" maxlength="100" show-word-limit />
      </el-form-item>
      <el-form-item label="*部门名称">
        <el-select
          v-model="form.department"
          data-test="edit-department"
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
      </el-form-item>
      <el-form-item label="*提交人姓名">
        <el-input v-model="form.submitter" data-test="edit-submitter" maxlength="50" />
      </el-form-item>
      <el-form-item label="版本号">
        <el-input v-model="form.version" data-test="edit-version" maxlength="20" placeholder="例如：1.0.0" />
      </el-form-item>
      <el-form-item label="*说明">
        <el-input
          v-model="form.description"
          data-test="edit-description"
          type="textarea"
          :rows="4"
          maxlength="2000"
          show-word-limit
        />
      </el-form-item>
      <el-form-item label="*文件名称">
        <el-input
          v-model="form.fileName"
          data-test="edit-file-name"
          maxlength="100"
          show-word-limit
          placeholder="请输入包含扩展名的完整文件名"
        />
        <div class="edit-note">支持 {{ config.allowedExtensions.join(' / ') }} 格式</div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button data-test="save-asset-edit" type="primary" :loading="saving.active" @click="save">
        保存并重新提交审核
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.edit-note {
  color: var(--brand-muted);
  font-size: 12px;
  line-height: 1.5;
  margin-top: 5px;
}
</style>
