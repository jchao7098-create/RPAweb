<script setup>
import { ref } from 'vue'
import RequirementsRpa from './RequirementsRpa.vue'
import AssetReview from './AssetReview.vue'

// 审核中心：RPA 程序（开发需求）与代码资产（Skill / Python 插件）合并在一个栏目里，
// 顶部标签页切换；两个面板各自保留自己的统计卡与操作逻辑。
// AssetReview 用 :key 强制按类型重建实例，避免复用时状态串台。
defineProps({
  apiPrefix: { type: String, default: '/admin' },
  selfService: { type: Boolean, default: false },
})
const tab = ref('rpa')
</script>

<template>
  <div class="review-center">
    <h2 class="review-title">{{ selfService ? '我的需求审核' : '需求审核' }}</h2>
    <p v-if="selfService" class="review-sub">审核本人提交的 RPA、Skill 和 Python 插件；通过后进入开发进度管理。</p>

    <el-radio-group v-model="tab" class="review-tabs">
      <el-radio-button value="rpa">RPA 程序</el-radio-button>
      <el-radio-button value="skill">Skill 文件</el-radio-button>
      <el-radio-button value="python_plugin">Python 插件</el-radio-button>
    </el-radio-group>

    <RequirementsRpa v-if="tab === 'rpa'" :api-prefix="apiPrefix" />
    <AssetReview v-else :key="tab" :fixed-type="tab" :api-prefix="apiPrefix" />
  </div>
</template>

<style scoped>
.review-title { margin: 0 0 14px; }
.review-sub { margin: -8px 0 16px; color: var(--brand-muted); font-size: 13.5px; }
.review-tabs { margin-bottom: 18px; }
</style>
