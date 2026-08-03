<script setup>
import { computed, onMounted, ref } from 'vue'
import ConsoleShell from '@/components/layout/ConsoleShell.vue'
import { canManageLearning, canViewLearningStats } from '@/utils/learningSession'
import { loadLearningProfile } from '@/api/learning'

// 管理员端栏目清单；外壳（导航/欢迎页/页脚）在 ConsoleShell 里与用户端共享
const sections = [
  { path: '/admin/Requirements', label: '需求审核', desc: '审核 RPA 程序、Skill 文件与 Python 插件的提交' },
  { path: '/admin/DevelopmentProgress', label: '开发进度', desc: '维护各项目的开发阶段、进度与日志' },
  { path: '/admin/MaintenanceProgress', label: '维护进度', desc: '管理系统维护记录与处理状态' },
  { path: '/admin/DataExport', label: '数据导出', desc: '下载全平台完整数据包及实习生学习情况' },
]

const learningProfile = ref(null)
const visibleSections = computed(() => {
  const result = [...sections]
  if (canViewLearningStats(learningProfile.value)) {
    result.push({ path: '/admin/LearningStats', label: '学习统计', desc: '查看实习生周报提交、学习时长与个人趋势' })
  }
  if (canManageLearning(learningProfile.value)) {
    result.push({ path: '/admin/RoleManagement', label: '人员权限', desc: '调整学习模块角色并查看角色审计记录' })
  }
  return result
})
onMounted(async () => { try { learningProfile.value = await loadLearningProfile() } catch { learningProfile.value = null } })
</script>

<template>
  <ConsoleShell
    role-label="管理员端"
    :sections="visibleSections"
    welcome-title="管理后台"
    welcome-sub="需求审核、开发与维护进度、数据导出 · 选择一个栏目开始"
    root-path="/admin"
    back-label="回到管理后台"
  />
</template>
