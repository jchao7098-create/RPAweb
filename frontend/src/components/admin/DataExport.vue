<template>
  <div class="export-container">
    <h2>全平台数据导出</h2>
    <p class="export-hint">
      导出范围覆盖全平台所有人员、项目和学习数据。CSV 带 UTF-8 BOM，可直接用 Excel 打开。
    </p>

    <div class="export-cards">
      <el-card shadow="hover" class="export-card export-card-featured">
        <h3 class="export-card-title">全平台完整数据包</h3>
        <p class="export-card-desc">
          一次下载全部平台数据：用户、RPA 需求与项目、开发和维护记录、
          Skill / Python 资产、实习生全部学习周报及提交历史等多份 CSV。
        </p>
        <el-button
          data-test="full-export"
          type="primary"
          :loading="downloading === 'full'"
          @click="download(`${apiPrefix}/export/full_archive`, `AI_Tools全平台数据_${today()}.zip`, 'full')"
        >
          下载完整数据包
        </el-button>
        <p class="export-security-note">
          安全说明：不导出网站密码、需求登录密码、邮箱授权码或令牌密钥。
        </p>
      </el-card>

      <el-card shadow="hover" class="export-card">
        <h3 class="export-card-title">全平台近 7 天数据统计</h3>
        <p class="export-card-desc">
          新增需求（含审核状态分布）、新增项目、开发日志、维护记录、
          新增注册用户，以及 Skill / Python 插件的提交与通过数量。
        </p>
        <el-button
          type="primary"
          :loading="downloading === 'stats'"
          @click="download(`${apiPrefix}/export/weekly_stats`, `近7天数据统计_${today()}.csv`, 'stats')"
        >
          下载统计报表
        </el-button>
      </el-card>

      <el-card shadow="hover" class="export-card">
        <h3 class="export-card-title">全平台上传名称清单</h3>
        <p class="export-card-desc">
          全部上传记录的名称明细：RPA 程序（需求）、Skill 文件、Python 插件，
          含文件名、部门、提交人、状态与提交时间。
        </p>
        <el-button
          type="primary"
          :loading="downloading === 'names'"
          @click="download(`${apiPrefix}/export/upload_names`, `上传名称清单_${today()}.csv`, 'names')"
        >
          下载名称清单
        </el-button>
      </el-card>

      <el-card v-if="includeLearningExport" shadow="hover" class="export-card">
        <h3 class="export-card-title">全部实习生 RPA 学习数据</h3>
        <p class="export-card-desc">
          导出所有统计周、全部实习生的提交状态及每一次正式提交历史，
          包含证书、进度、程序数、学习卡点和提交时间。
        </p>
        <el-button
          data-test="learning-export"
          type="primary"
          :loading="downloading === 'learning'"
          @click="download(`${apiPrefix}/export/intern_learning`, `实习生RPA学习全部数据_${today()}.csv`, 'learning')"
        >
          下载全部学习数据
        </el-button>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import http from '@/api/http'

defineProps({
  apiPrefix: { type: String, default: '/admin' },
  includeLearningExport: { type: Boolean, default: true },
})

const downloading = ref('')

const today = () => new Date().toISOString().slice(0, 10)

// 用 blob 方式下载：后端与前端不同源，直接 <a href> 会丢 CORS 头，
// 走共享 http 实例还能吃到统一的 30s 超时
const download = async (path, filename, key) => {
  if (downloading.value) return
  downloading.value = key
  try {
    const res = await http.get(path, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已开始下载')
  } catch (e) {
    ElMessage.error('导出失败，请稍后再试')
  } finally {
    downloading.value = ''
  }
}
</script>

<style scoped>
.export-container { padding: 0 8px; }
.export-hint { color: #909399; font-size: 13px; margin: 6px 0 18px; }
.export-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  max-width: 900px;
}
.export-card { border-radius: 8px; }
.export-card-featured { border-color: #b9cdfc; background: #f8faff; }
.export-card-title { margin: 0 0 10px; font-size: 16px; color: #303133; }
.export-card-desc { color: #606266; font-size: 13.5px; line-height: 1.7; margin: 0 0 16px; min-height: 66px; }
.export-security-note { color: #909399; font-size: 12px; line-height: 1.55; margin: 12px 0 0; }
</style>
