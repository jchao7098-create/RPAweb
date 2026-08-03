<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ASSET_TYPES, ASSET_STATUS_TAG_TYPES } from '@/config/assetTypes'
import { formatFileSize } from '@/utils/format'
import { fetchPublicAssets } from '@/api/assets'

const props = defineProps({
  // 对应 ASSET_TYPES 里的键，由路由以 props 形式传入
  assetTypeId: {
    type: String,
    required: true,
    validator: (v) => v in ASSET_TYPES,
  },
})

const config = computed(() => ASSET_TYPES[props.assetTypeId])

const assets = ref([])
const loading = ref(false)
const loadFailed = ref(false)
const searchKeyword = ref('')

const showDetail = ref(false)
const currentAsset = ref(null)

const loadAssets = async () => {
  loading.value = true
  loadFailed.value = false
  try {
    const res = await fetchPublicAssets({ assetType: config.value.apiType })
    assets.value = res.data?.data ?? []
  } catch (err) {
    assets.value = []
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(loadAssets)

// Skill 页和插件页共用本组件，路由切换时实例被复用，需要重新拉数据
watch(
  () => props.assetTypeId,
  () => {
    showDetail.value = false
    loadAssets()
  }
)

const normalizedKeyword = computed(() => searchKeyword.value.trim().toLocaleLowerCase())
const filteredAssets = computed(() => {
  if (!normalizedKeyword.value) return assets.value
  return assets.value.filter((asset) =>
    [
      asset.department,
      asset.id,
      asset.name,
      asset.submitter,
      asset.version,
      asset.file_name,
      asset.status,
      asset.lifecycle_status,
      asset.description,
    ].some((value) =>
      String(value ?? '').toLocaleLowerCase().includes(normalizedKeyword.value)
    )
  )
})

const groupedByDepartment = computed(() => {
  const groups = {}
  filteredAssets.value.forEach((asset) => {
    const dept = asset.department || '未指定部门'
    if (!groups[dept]) {
      groups[dept] = []
    }
    groups[dept].push(asset)
  })
  return groups
})

const viewDetail = (row) => {
  currentAsset.value = row
  showDetail.value = true
}

const logoMissing = ref(false)
const STATUS_CHIP = { 在编: 'chip-amber', 使用: 'chip-blue', 大修: 'chip-violet', 停用: 'chip-gray' }
</script>

<template>
  <div class="aitools-page dept-assets">
    <nav class="aitools-nav">
      <div class="aitools-nav-inner">
        <router-link to="/" class="aitools-brand">
          <img v-if="!logoMissing" class="aitools-brand-logo" src="/logo.png" alt="公司 logo" @error="logoMissing = true" />
          <span class="aitools-brand-name">AI Tools web</span>
        </router-link>
        <div class="aitools-nav-links">
          <router-link class="aitools-nav-link" :class="{ 'is-active': assetTypeId === 'skill' }" to="/department-skills">各部门Skill情况</router-link>
          <router-link class="aitools-nav-link" :class="{ 'is-active': assetTypeId === 'pythonPlugin' }" to="/department-plugins">各部门Python插件情况</router-link>
          <router-link class="aitools-nav-link" to="/department">各部门RPA情况</router-link>
        </div>
        <div class="aitools-nav-actions">
          <router-link class="btn btn-gray" to="/">首页</router-link>
          <router-link class="btn btn-black" to="/login">进入统一工作台</router-link>
        </div>
      </div>
    </nav>

    <main class="dept-content">
      <h1 class="page-title">{{ config.publicTitle }}</h1>

      <section class="search-panel panel">
        <label class="search-label" :for="`asset-search-${assetTypeId}`">搜索{{ config.label }}</label>
        <div class="search-control">
          <input
            :id="`asset-search-${assetTypeId}`"
            v-model="searchKeyword"
            data-test="department-asset-search"
            type="search"
            class="search-input"
            :placeholder="`搜索部门、${config.label}名称、提交人或状态`"
          />
          <button v-if="searchKeyword" class="btn btn-gray btn-sm" type="button" @click="searchKeyword = ''">
            清空
          </button>
        </div>
        <span class="search-result">
          {{ searchKeyword ? `找到 ${filteredAssets.length} 个，共 ${assets.length} 个` : `共 ${assets.length} 个` }}
        </span>
      </section>

      <!-- 各部门数量汇总 -->
      <section class="summary panel">
        <span class="chip chip-violet">当前显示 {{ filteredAssets.length }} 个</span>
        <span v-for="(items, dept) in groupedByDepartment" :key="dept" class="chip chip-blue">
          {{ dept }} {{ items.length }}
        </span>
        <span v-if="filteredAssets.length === 0" class="chip chip-gray">
          {{ searchKeyword ? '没有匹配结果' : '暂无数据' }}
        </span>
      </section>

      <p v-if="loadFailed" class="load-alert">数据加载失败，请稍后刷新重试</p>

      <!-- 按部门分组的列表 -->
      <h2 class="section-title">{{ config.label }}列表（按部门分组）</h2>
      <div v-for="(items, dept) in groupedByDepartment" :key="dept" class="dept-block panel">
        <h3 class="dept-block-title">
          {{ dept }}
          <span class="dept-block-count">{{ items.length }} 个</span>
        </h3>

        <div class="table-wrap">
          <table class="clean-table">
            <thead>
              <tr>
                <th>数据库编号</th>
                <th>名称</th>
                <th>版本</th>
                <th>提交人</th>
                <th>进度</th>
                <th>状态</th>
                <th>提交时间</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in items" :key="row.id">
                <td class="td-mono">{{ config.label }} #{{ row.id }}</td>
                <td class="td-title">{{ row.name }}</td>
                <td>{{ row.version || '-' }}</td>
                <td>{{ row.submitter || '-' }}</td>
                <td class="td-mono">{{ row.progress ?? 0 }}%</td>
                <td><span class="chip" :class="STATUS_CHIP[row.lifecycle_status] || 'chip-gray'">{{ row.lifecycle_status || '在编' }}</span></td>
                <td class="td-mono">{{ row.created_at }}</td>
                <td><button class="btn btn-gray btn-sm" @click="viewDetail(row)">详情</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <p v-if="!loading && filteredAssets.length === 0" class="empty-note">
        {{ searchKeyword ? '没有找到匹配内容，请更换关键词' : `暂无${config.label}数据` }}
      </p>
    </main>

    <!-- 详情对话框 -->
    <Transition name="modal">
      <div v-if="showDetail" class="modal-overlay" @click.self="showDetail = false">
        <div class="modal-panel">
          <div class="modal-head">
            <h3>{{ config.label }}详情</h3>
            <button class="modal-close" @click="showDetail = false">✕</button>
          </div>
          <dl v-if="currentAsset" class="detail-list">
            <div class="detail-row"><dt>数据库编号</dt><dd>{{ config.label }} #{{ currentAsset.id }}</dd></div>
            <div class="detail-row"><dt>名称</dt><dd>{{ currentAsset.name }}</dd></div>
            <div class="detail-row"><dt>版本</dt><dd>{{ currentAsset.version || '-' }}</dd></div>
            <div class="detail-row"><dt>部门</dt><dd>{{ currentAsset.department || '未指定部门' }}</dd></div>
            <div class="detail-row"><dt>提交人</dt><dd>{{ currentAsset.submitter || '-' }}</dd></div>
            <div class="detail-row"><dt>说明</dt><dd>{{ currentAsset.description || '-' }}</dd></div>
            <div class="detail-row"><dt>文件名</dt><dd>{{ currentAsset.file_name || '-' }}</dd></div>
            <div class="detail-row"><dt>大小</dt><dd>{{ formatFileSize(currentAsset.file_size) }}</dd></div>
            <div class="detail-row"><dt>开发进度</dt><dd>{{ currentAsset.progress ?? 0 }}%</dd></div>
            <div class="detail-row">
              <dt>状态</dt>
              <dd><span class="chip" :class="STATUS_CHIP[currentAsset.lifecycle_status] || 'chip-gray'">{{ currentAsset.lifecycle_status || '在编' }}</span></dd>
            </div>
            <div class="detail-row"><dt>提交时间</dt><dd>{{ currentAsset.created_at || '-' }}</dd></div>
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

.summary {
  padding: 20px 22px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 32px;
}

.load-alert {
  background: #fff7e6;
  border: 1px solid #ecd9a8;
  color: #9a6700;
  border-radius: 12px;
  padding: 12px 18px;
  font-size: 13.5px;
  margin: 0 0 20px;
}

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
.detail-row dt { width: 96px; flex: none; color: var(--brand-muted); }
.detail-row dd { margin: 0; flex: 1; line-height: 1.65; }

.modal-enter-active, .modal-leave-active { transition: opacity 0.22s; }
.modal-enter-active .modal-panel, .modal-leave-active .modal-panel { transition: transform 0.22s cubic-bezier(0.22, 1, 0.36, 1); }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal-panel, .modal-leave-to .modal-panel { transform: translateY(12px) scale(0.98); }

@media (max-width: 900px) {
  .aitools-nav-links { display: none; }
  .dept-content { padding: 28px 20px 56px; }
  .search-panel { grid-template-columns: 1fr; gap: 8px; }
}
</style>
