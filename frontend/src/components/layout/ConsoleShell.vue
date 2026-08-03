<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

// 用户端 / 管理员端控制台的共享外壳：顶部导航 + 无子路由时的欢迎页栏目卡片 +
// 跟随内容流动的页脚。此前 UserView 与 AdminView 各自复制一份完全相同的模板和样式，
// 改一处漏一处，故收拢到这里；两个视图只负责传入自己的栏目清单与文案。
const props = defineProps({
  // 导航上的角色徽章文字，如 "用户端" / "管理员端"
  roleLabel: { type: String, required: true },
  // 栏目清单 [{ path, label, desc }]，顶部导航与欢迎页卡片共用
  sections: { type: Array, required: true },
  // 欢迎页可选分组 [{ key, label, desc }]；顶部导航仍按 sections 的业务顺序展示
  sectionGroups: { type: Array, default: () => [] },
  // 欢迎页大标题与副标题
  welcomeTitle: { type: String, required: true },
  welcomeSub: { type: String, required: true },
  // 可选：同时传入 rootPath 与 backLabel 时，进入子页面后右上角按钮
  // 从"返回首页"变为返回工作台（如用户端的"回到用户工作台"→ /main）；
  // 位于工作台首页时仍显示"返回首页"。不传则始终显示"返回首页"。
  rootPath: { type: String, default: '' },
  backLabel: { type: String, default: '' },
})

const route = useRoute()
const onChildPage = computed(
  () => !!(props.rootPath && props.backLabel) && route.path.replace(/\/+$/, '') !== props.rootPath
)

const groupedSections = computed(() => {
  if (!props.sectionGroups.length) {
    return [{ key: 'all', label: '', desc: '', sections: props.sections }]
  }

  const groups = props.sectionGroups
    .map((group) => ({
      ...group,
      sections: props.sections.filter((section) => section.group === group.key),
    }))
    .filter((group) => group.sections.length)
  const ungrouped = props.sections.filter(
    (section) => !props.sectionGroups.some((group) => group.key === section.group)
  )
  if (ungrouped.length) {
    groups.push({ key: 'other', label: '其他', desc: '', sections: ungrouped })
  }
  return groups
})

const logoMissing = ref(false)
const navRail = ref(null)
const navLinks = ref(null)
const navHasOverflow = ref(false)
const navCanScrollLeft = ref(false)
const navCanScrollRight = ref(false)
let navResizeObserver = null

const updateNavScrollState = () => {
  const element = navLinks.value
  if (!element) return
  const maxScrollLeft = Math.max(0, element.scrollWidth - element.clientWidth)
  const availableWidth = navRail.value?.clientWidth || element.clientWidth
  const nextHasOverflow = element.scrollWidth > availableWidth + 2
  const overflowChanged = navHasOverflow.value !== nextHasOverflow
  navHasOverflow.value = nextHasOverflow
  navCanScrollLeft.value = element.scrollLeft > 2
  navCanScrollRight.value = element.scrollLeft < maxScrollLeft - 2
  if (overflowChanged) nextTick(updateNavScrollState)
}

const scrollNav = (direction) => {
  const element = navLinks.value
  if (!element) return
  const distance = Math.max(180, Math.round(element.clientWidth * 0.72))
  const behavior = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    ? 'auto'
    : 'smooth'
  if (typeof element.scrollBy === 'function') {
    element.scrollBy({ left: direction * distance, behavior })
  } else {
    element.scrollLeft += direction * distance
    updateNavScrollState()
  }
}

const revealActiveSection = () => {
  const element = navLinks.value
  if (!element) return
  const activeLink = element.querySelector('.is-active')
  if (typeof activeLink?.scrollIntoView === 'function') {
    activeLink.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' })
  }
  updateNavScrollState()
}

const refreshNav = async () => {
  await nextTick()
  updateNavScrollState()
  revealActiveSection()
}

onMounted(() => {
  window.addEventListener('resize', updateNavScrollState)
  if (typeof ResizeObserver !== 'undefined' && navLinks.value) {
    navResizeObserver = new ResizeObserver(updateNavScrollState)
    navResizeObserver.observe(navLinks.value)
    if (navRail.value) navResizeObserver.observe(navRail.value)
  }
  refreshNav()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateNavScrollState)
  navResizeObserver?.disconnect()
})

watch(
  () => [route.fullPath, ...props.sections.map((section) => `${section.path}:${section.label}`)],
  refreshNav
)
</script>

<template>
  <div class="aitools-page console-page">
    <nav class="aitools-nav">
      <div class="aitools-nav-inner">
        <router-link to="/" class="aitools-brand">
          <img v-if="!logoMissing" class="aitools-brand-logo" src="/logo.png" alt="公司 logo" @error="logoMissing = true" />
          <span class="aitools-brand-name">AI Tools web</span>
        </router-link>
        <span class="chip chip-violet console-role">{{ roleLabel }}</span>
        <div ref="navRail" class="console-nav-scroller">
          <button
            v-show="navHasOverflow"
            type="button"
            class="console-nav-arrow"
            :disabled="!navCanScrollLeft"
            aria-label="向左查看更多功能"
            title="向左查看更多功能"
            aria-controls="console-primary-navigation"
            @click="scrollNav(-1)"
          ><span aria-hidden="true">‹</span></button>
          <div
            id="console-primary-navigation"
            ref="navLinks"
            class="aitools-nav-links console-nav-links"
            :tabindex="navHasOverflow ? 0 : -1"
            @keydown.left.self.prevent="scrollNav(-1)"
            @keydown.right.self.prevent="scrollNav(1)"
            @scroll.passive="updateNavScrollState"
          >
            <router-link
              v-for="s in sections"
              :key="s.path"
              class="aitools-nav-link"
              active-class="is-active"
              :to="s.path"
            >{{ s.label }}</router-link>
          </div>
          <button
            v-show="navHasOverflow"
            type="button"
            class="console-nav-arrow"
            :disabled="!navCanScrollRight"
            aria-label="向右查看更多功能"
            title="向右查看更多功能"
            aria-controls="console-primary-navigation"
            @click="scrollNav(1)"
          ><span aria-hidden="true">›</span></button>
        </div>
        <div class="aitools-nav-actions">
          <router-link v-if="onChildPage" class="btn btn-gray" :to="rootPath">{{ backLabel }}</router-link>
          <router-link v-else class="btn btn-gray" to="/">返回首页</router-link>
        </div>
      </div>
    </nav>

    <main class="console-main">
      <RouterView v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" v-if="Component" :key="$route.path" />
          <div v-else class="console-welcome">
            <h1 class="console-title">{{ welcomeTitle }}</h1>
            <p class="console-sub">{{ welcomeSub }}</p>
            <div class="console-groups">
              <section v-for="group in groupedSections" :key="group.key" class="console-group">
                <div v-if="group.label" class="console-group-head">
                  <h2>{{ group.label }}</h2>
                  <p v-if="group.desc">{{ group.desc }}</p>
                </div>
                <div class="console-grid">
                  <router-link v-for="s in group.sections" :key="s.path" class="console-card" :to="s.path">
                    <span class="console-card-title">{{ s.label }}</span>
                    <span class="console-card-desc">{{ s.desc }}</span>
                    <span v-if="s.note" class="console-card-note">备注：{{ s.note }}</span>
                    <span class="console-card-arrow">→</span>
                  </router-link>
                </div>
              </section>
            </div>
          </div>
        </Transition>
      </RouterView>

      <!-- 页脚跟随内容流动：折叠/展开项目时随内容底部移动，避免下方大片留白没有收尾 -->
      <footer class="console-footer">
        <img v-if="!logoMissing" class="console-footer-logo" src="/logo.png" alt="" @error="logoMissing = true" />
        <span>© 2026 上海焱坤网络科技 AI Tools web</span>
      </footer>
    </main>
  </div>
</template>

<style scoped>
.console-role { flex-shrink: 0; }
.console-nav-scroller {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  min-width: 0;
  gap: 5px;
}
.console-nav-links {
  min-width: 0;
  overflow-x: auto;
  overscroll-behavior-inline: contain;
  scrollbar-width: none;
  scroll-behavior: smooth;
}
.console-nav-links::-webkit-scrollbar { display: none; }
.console-nav-links:focus-visible {
  outline: 2px solid #8587e8;
  outline-offset: 3px;
  border-radius: 10px;
}
.console-nav-arrow {
  display: inline-flex;
  flex: 0 0 30px;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  padding: 0;
  border: 1px solid var(--brand-line);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--brand-text);
  box-shadow: 0 3px 10px rgba(20, 20, 19, 0.06);
  cursor: pointer;
  transition: color 0.18s, background 0.18s, border-color 0.18s, opacity 0.18s, transform 0.18s;
}
.console-nav-arrow span {
  display: block;
  margin-top: -2px;
  font-family: Arial, sans-serif;
  font-size: 25px;
  line-height: 1;
}
.console-nav-arrow:hover:not(:disabled) {
  border-color: #d2d2ca;
  background: #f0f0ec;
  transform: translateY(-1px);
}
.console-nav-arrow:focus-visible {
  outline: 2px solid #8587e8;
  outline-offset: 2px;
}
.console-nav-arrow:disabled {
  opacity: 0.28;
  cursor: default;
  box-shadow: none;
}

.console-main {
  box-sizing: border-box;
  max-width: 1200px;
  margin: 0 auto;
  padding: 36px 28px 44px;
}

.console-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: 64px;
  padding-top: 24px;
  border-top: 1px solid var(--brand-line);
  color: var(--brand-muted);
  font-size: 13px;
}
.console-footer-logo { width: 20px; height: 20px; border-radius: 6px; mix-blend-mode: multiply; }

/* 无子路由时的欢迎页：标题 + 栏目卡片 */
.console-welcome {
  max-width: 980px;
  margin: 0 auto;
  padding-top: 44px;
  text-align: center;
}
.console-title {
  font-size: 34px;
  font-weight: 800;
  letter-spacing: -0.5px;
  margin: 0 0 10px;
}
.console-sub {
  color: var(--brand-muted);
  font-size: 15px;
  margin: 0 0 38px;
}
.console-groups {
  display: flex;
  flex-direction: column;
  gap: 32px;
}
.console-group-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin: 0 0 12px;
  text-align: left;
}
.console-group-head h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 750;
}
.console-group-head p {
  margin: 0;
  color: var(--brand-muted);
  font-size: 13px;
}
.console-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  text-align: left;
}
.console-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 22px 44px 24px 22px;
  background: var(--brand-raised);
  border: 1px solid var(--brand-line);
  border-radius: 16px;
  text-decoration: none;
  color: inherit;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.console-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 14px 34px rgba(20, 20, 19, 0.08);
  border-color: #dcdcd4;
}
.console-card-title { font-size: 16px; font-weight: 700; }
.console-card-desc { font-size: 13.5px; color: var(--brand-muted); line-height: 1.5; }
/* 栏目卡片上的备注小标签（如"目前只支持上传文件名"），浅琥珀色与描述区分 */
.console-card-note {
  align-self: flex-start;
  font-size: 12px;
  color: #9a6700;
  background: #fff7e6;
  border: 1px solid #f0e0b2;
  border-radius: 999px;
  padding: 3px 10px;
  margin-top: 2px;
}
.console-card-arrow {
  position: absolute;
  top: 20px;
  right: 20px;
  color: var(--brand-muted);
  font-family: var(--brand-mono);
  transition: transform 0.18s ease, color 0.18s;
}
.console-card:hover .console-card-arrow {
  transform: translateX(4px);
  color: var(--brand-text);
}

@media (max-width: 720px) {
  .console-main { padding: 24px 16px 56px; }
  .console-title { font-size: 26px; }
  .console-group-head { display: block; }
  .console-group-head p { margin-top: 4px; }
  .console-nav-scroller { gap: 3px; }
  .console-nav-arrow {
    flex-basis: 28px;
    width: 28px;
    height: 28px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .console-nav-links { scroll-behavior: auto; }
}
</style>
