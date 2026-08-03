<script setup>
import { reactive, ref, watch } from 'vue'
import { updateMyRequirement } from '@/api/requirements'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  requirement: { type: Object, required: true },
  userId: { type: [String, Number], required: true },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const saving = ref(false)
const form = reactive({
  title: '',
  description: '',
  department: '',
  requester: '',
  priority: '',
  feedbackTime: '',
  expectedFinishTime: '',
  platform: '',
  operationLink: '',
  account: '',
  password: '',
})

const populate = () => {
  const source = props.requirement || {}
  form.title = source.title || ''
  form.description = source.description || ''
  form.department = source.department || ''
  form.requester = source.requester || ''
  form.priority = source.priority || ''
  form.feedbackTime = source.feedback_time || ''
  form.expectedFinishTime = source.expected_finish_time || ''
  form.platform = source.platform || ''
  form.operationLink = source.operation_link || ''
  form.account = source.account || ''
  form.password = ''
}

watch(
  () => [props.modelValue, props.requirement],
  ([visible]) => {
    if (visible) populate()
  },
  { immediate: true },
)

const close = () => emit('update:modelValue', false)

const submit = async () => {
  const required = [
    form.title,
    form.description,
    form.department,
    form.requester,
    form.priority,
    form.feedbackTime,
    form.expectedFinishTime,
  ]
  if (required.some((value) => !String(value || '').trim())) {
    ElMessage.warning('请填写全部必填信息')
    return
  }

  saving.value = true
  try {
    const response = await updateMyRequirement({
      id: props.requirement.id,
      userId: props.userId,
      ...form,
    })
    ElMessage.success(response.data?.message || '需求修改成功')
    emit('saved', response.data?.data)
    close()
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '需求修改失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="修改 RPA 需求"
    width="min(760px, 92vw)"
    :close-on-click-modal="false"
    :teleported="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-alert
      class="edit-alert"
      type="warning"
      :closable="false"
      title="仅待审核或已拒绝的需求可以修改；保存后状态变为待审核。"
      show-icon
    />

    <el-form label-position="top">
      <div class="edit-grid">
        <el-form-item label="部门名称（必填）">
          <el-input v-model="form.department" />
        </el-form-item>
        <el-form-item label="需求人姓名（必填）">
          <el-input v-model="form.requester" />
        </el-form-item>
        <el-form-item label="反馈时间（必填）">
          <el-date-picker
            v-model="form.feedbackTime"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="期望完成时间（必填）">
          <el-date-picker
            v-model="form.expectedFinishTime"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="紧急程度（必填）">
          <el-select v-model="form.priority" style="width: 100%">
            <el-option label="高" value="高" />
            <el-option label="中" value="中" />
            <el-option label="低" value="低" />
          </el-select>
        </el-form-item>
        <el-form-item label="RPA平台/软件">
          <el-input v-model="form.platform" />
        </el-form-item>
      </div>

      <el-form-item label="需求标题（必填）">
        <el-input v-model="form.title" data-test="requirement-title" />
      </el-form-item>
      <el-form-item label="需求描述（必填）">
        <el-input v-model="form.description" type="textarea" :rows="4" />
      </el-form-item>
      <el-form-item label="操作链接">
        <el-input v-model="form.operationLink" />
      </el-form-item>

      <div class="edit-grid">
        <el-form-item label="登录账号">
          <el-input v-model="form.account" />
        </el-form-item>
        <el-form-item label="登录密码">
          <el-input v-model="form.password" type="password" show-password placeholder="留空表示不修改原密码" />
        </el-form-item>
      </div>
    </el-form>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存并重新审核</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.edit-alert { margin-bottom: 18px; }
.edit-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}
@media (max-width: 640px) {
  .edit-grid { grid-template-columns: 1fr; }
}
</style>
