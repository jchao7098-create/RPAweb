<script setup>
import { computed, onMounted, ref } from 'vue'
import ConsoleShell from '@/components/layout/ConsoleShell.vue'
import { canViewReport } from '@/utils/learningSession'
import { loadLearningProfile } from '@/api/learning'

// 用户端栏目清单；外壳（导航/欢迎页/页脚）在 ConsoleShell 里与管理员端共享
const sections = [
  { path: '/main/RpaProgress', label: '项目进度', desc: '跟踪我的需求审核状态与开发进展日志', group: 'tracking' },
  { path: '/main/RpaRequirement', label: '上传RPA程序', desc: '提交 RPA 程序开发需求，附带平台、链接与账号信息', note: '目前只支持上传文件名', group: 'submission' },
  { path: '/main/SkillUpload', label: '上传 Skill', desc: '提交 Skill 文件资产，沉淀给各部门复用', note: '目前只支持上传文件名', group: 'submission' },
  { path: '/main/PluginUpload', label: '上传插件', desc: '提交 Python 插件资产并跟踪审核结果', note: '目前只支持上传文件名', group: 'submission' },
  { path: '/main/RpaMaintance', label: '维护记录', desc: '查看我名下的历史维护工单与处理详情', group: 'tracking' },
  { path: '/main/RequirementReview', label: '需求审核', desc: '审核本人提交的 RPA、Skill 与 Python 插件', group: 'management' },
  { path: '/main/DevelopmentManagement', label: '开发进度管理', desc: '查看全平台开发进度，并更新本人项目的进度与生命周期状态', group: 'management' },
  { path: '/main/MaintenanceManagement', label: '维护管理', desc: '管理本人参与项目的维护处理记录', group: 'management' },
  { path: '/main/DataExport', label: '数据导出', desc: '导出全平台项目、资产、维护及实习生学习数据', group: 'data' },
]

const sectionGroups = [
  { key: 'tracking', label: '进度与记录', desc: '先查看当前状态和历史处理记录' },
  { key: 'submission', label: '提交中心', desc: '按文件类型选择对应入口' },
  { key: 'management', label: '审核与管理', desc: '审核需求并更新开发、维护进度' },
  { key: 'data', label: '数据与学习', desc: '导出统计或填写学习记录' },
]

const learningProfile = ref(null)
const visibleSections = computed(() => learningProfile.value && canViewReport(learningProfile.value)
  ? [...sections, { path: '/main/LearningReport', label: 'RPA 学习情况记录', desc: '保存本周学习草稿、正式提交并查看退回记录', group: 'data' }]
  : sections)
onMounted(async () => { try { learningProfile.value = await loadLearningProfile() } catch { learningProfile.value = null } })
</script>

<template>
  <ConsoleShell
    role-label="用户端"
    :sections="visibleSections"
    :section-groups="sectionGroups"
    welcome-title="用户工作台"
    welcome-sub="提交、审核、更新一体化 · 选择一个栏目开始"
    root-path="/main"
    back-label="回到用户工作台"
  />
</template>
