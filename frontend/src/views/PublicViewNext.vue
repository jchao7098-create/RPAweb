<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import http from '@/api/http'
import { fetchPublicAssets } from '@/api/assets'
import { departmentFromProjectName } from '@/utils/departments'



const projects = ref([])
const requirements = ref([])
const loading = ref(true)
const loadFailed = ref(false)
const barsReady = ref(false)
const logoMissing = ref(false)

const showDetail = ref(false)
const currentReq = ref(null)

const displayStats = ref({ total: 0, done: 0, active: 0, approved: 0 })

const pageEl = ref(null)
const statsEl = ref(null)
const heroEl = ref(null)
const sphereCanvasEl = ref(null)

const prefersReducedMotion = () =>
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

const fetchAllData = async () => {
  try {
    const [projectsRes, requirementsRes] = await Promise.all([
      http.get('/public/projects'),
      http.get('/public/requirements'),
    ])
    projects.value = projectsRes.data.data || []
    requirements.value = requirementsRes.data || []
    setTimeout(() => { barsReady.value = true }, 120)
  } catch (err) {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

/* ---------- 实时资产计数：RPA 程序 / Skill 文件 / Python 插件 ----------
   每 30 秒静默轮询一次；数量变化时对应星球短暂泛光脉冲一次。
   费波那契球面撒点 + 正交投影，单个 canvas 画三颗球，全宽散布，球心自带名字；
   半径由计数实时驱动，且恒被容器尺寸钳制，绝不撑出版面。 */
const SPHERES = [
  { key: 'rpa', rgb: '20,20,19', textColor: '#141413', shortLabel: 'RPA', anchor: [0.13, 0.58], spin: 0.0026, tilt: 0.30 },
  { key: 'skill', rgb: '110,123,217', textColor: '#4a4fb0', shortLabel: 'Skill', anchor: [0.90, 0.24], spin: -0.0032, tilt: -0.24 },
  { key: 'plugin', rgb: '74,158,168', textColor: '#2f7a82', shortLabel: 'Python', anchor: [0.84, 0.80], spin: 0.0021, tilt: 0.4 },
]
const assetCounts = ref({ rpa: 0, skill: 0, plugin: 0 })
const pulsing = ref({ rpa: false, skill: false, plugin: false })
let pollTimer = null

const triggerPulse = (key) => {
  pulsing.value = { ...pulsing.value, [key]: true }
  setTimeout(() => { pulsing.value = { ...pulsing.value, [key]: false } }, 900)
}

const fetchAssetCounts = async (isFirstLoad = false) => {
  try {
    const [skillRes, pluginRes] = await Promise.all([
      fetchPublicAssets({ assetType: 'skill' }),
      fetchPublicAssets({ assetType: 'python_plugin' }),
    ])
    const next = {
      rpa: processedProjects.value.length,
      skill: (skillRes.data?.data ?? []).length,
      plugin: (pluginRes.data?.data ?? []).length,
    }
    const prev = assetCounts.value
    if (!isFirstLoad) {
      SPHERES.forEach(({ key }) => {
        if (prev[key] !== next[key]) triggerPulse(key)
      })
    }
    assetCounts.value = next
    // 减弱动态效果模式下没有渲染循环，数据变化需要主动补画一帧
    if (prefersReducedMotion() && redrawStaticSpheres) redrawStaticSpheres()
  } catch (err) {
    // 星球可视化是锦上添花的展示，静默失败即可，不打断主流程
  }
}

let redrawStaticSpheres = null

const fibonacciSphere = (n) => {
  const pts = []
  const golden = Math.PI * (3 - Math.sqrt(5))
  for (let i = 0; i < n; i++) {
    const y = n === 1 ? 0 : 1 - (i / (n - 1)) * 2
    const r = Math.sqrt(Math.max(0, 1 - y * y))
    const theta = golden * i
    pts.push([Math.cos(theta) * r, y, Math.sin(theta) * r])
  }
  return pts
}

let stopHeroScene = null

const initHeroSpheres = (interactive = true) => {
  const hero = heroEl.value
  const canvas = sphereCanvasEl.value
  if (!hero || !canvas) return null

  let targetX = 0.5
  let targetY = 0.5
  let curX = 0.5
  let curY = 0.5
  let hovering = false
  let t = Math.random() * 100
  let rafId = 0

  const clamp = (v) => Math.max(-0.1, Math.min(1.1, v))

  const onMove = (e) => {
    const r = hero.getBoundingClientRect()
    targetX = clamp((e.clientX - r.left) / r.width)
    targetY = clamp((e.clientY - r.top) / r.height)
    hovering = true
  }
  const onLeave = () => { hovering = false }

  if (interactive) {
    hero.addEventListener('pointermove', onMove)
    hero.addEventListener('pointerleave', onLeave)
  }

  // 星球渲染状态：每球缓存撒点、当前半径（惯性逼近目标值）、自转角
  const ctx = canvas ? canvas.getContext('2d') : null
  const sphereState = {}
  SPHERES.forEach((cfg) => {
    sphereState[cfg.key] = { pts: [], n: 0, radius: 0, angle: Math.random() * Math.PI * 2 }
  })
  let cw = 0
  let ch = 0
  let ro = null
  // 背景数据传输粒子：飘在球体后方空白区域的小光点，带缓慢漂移和淡尾迹，
  // 画在最底层，球体盖在上面时会自然遮挡，只在尺寸变化时重新撒点
  let ambientDots = []

  const genAmbientDots = () => {
    // 小而齐：统一朝右缓慢漂移（只在垂直方向留一点点随机抖动），不画尾迹，
    // 颗粒够小、方向统一，读起来是"整齐的粒子流"而不是"乱飞的虫子"
    const count = Math.max(36, Math.min(80, Math.round((cw * ch) / 12000)))
    ambientDots = Array.from({ length: count }, () => ({
      x: Math.random() * cw,
      y: Math.random() * ch,
      vx: 0.18 + Math.random() * 0.22,
      vy: (Math.random() - 0.5) * 0.05,
      r: 0.5 + Math.random() * 0.6,
      a: 0.14 + Math.random() * 0.18,
    }))
  }

  const resizeCanvas = () => {
    if (!canvas) return
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    cw = canvas.clientWidth
    ch = canvas.clientHeight
    canvas.width = cw * dpr
    canvas.height = ch * dpr
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    genAmbientDots()
  }
  if (canvas) {
    resizeCanvas()
    ro = new ResizeObserver(resizeCanvas)
    ro.observe(canvas)
  }

  const drawSpheres = (now) => {
    if (!ctx || !cw || !ch) return
    ctx.clearRect(0, 0, cw, ch)
    const counts = assetCounts.value
    const maxCount = Math.max(1, counts.rpa, counts.skill, counts.plugin)
    // 全局硬上限：无论数量多大，半径永远不超过面板短边的 30%，保证不会撑出容器
    const hardCap = Math.min(cw, ch) * 0.3
    const parallaxX = (curX - 0.5) * 16
    const parallaxY = (curY - 0.5) * 12

    // 第零遍：球体后方空白区域的数据传输粒子——统一朝右缓慢漂移，画在最底层，
    // 球体点云/光晕会自然盖在它们上面；飘出右边界从左边界重新进场
    for (let i = 0; i < ambientDots.length; i++) {
      const d = ambientDots[i]
      if (interactive) {
        d.x += d.vx
        d.y += d.vy
        if (d.x > cw + 6) d.x = -6
        if (d.y < -6) d.y = ch + 6
        else if (d.y > ch + 6) d.y = -6
      }
      ctx.fillStyle = `rgba(100,104,145,${d.a.toFixed(3)})`
      ctx.beginPath()
      ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2)
      ctx.fill()
    }

    // 第一遍：只算三球当前中心与半径（含视差），光晕/点云/传输粒子都要用，必须先定下来
    SPHERES.forEach((cfg) => {
      const st = sphereState[cfg.key]
      const cx = cfg.anchor[0] * cw
      const cy = cfg.anchor[1] * ch
      const localCap = Math.min(cx, cw - cx, cy, ch - cy) * 0.94
      const maxR = Math.min(hardCap, localCap)
      const minR = maxR * 0.4
      const count = counts[cfg.key] || 0
      const desiredR = minR + (count / maxCount) * (maxR - minR)
      // 静态帧（减弱动态效果）直接跳到目标半径，交互模式下才做惯性逼近
      st.radius = interactive ? st.radius + (desiredR - st.radius) * 0.05 : desiredR
      st.cx = cx + parallaxX
      st.cy = cy + parallaxY

      const n = Math.max(140, Math.min(560, Math.round(st.radius * 5.2)))
      if (Math.abs(n - st.n) > 10 || st.pts.length === 0) {
        st.pts = fibonacciSphere(n)
        st.n = n
      }
    })

    // 第二遍：每颗球周围的柔光光晕（参考截图里球体透出的色彩光斑），画在最底层
    SPHERES.forEach((cfg) => {
      const st = sphereState[cfg.key]
      if (st.radius < 2) return
      const glowR = st.radius * 2.6
      const grad = ctx.createRadialGradient(st.cx, st.cy, st.radius * 0.15, st.cx, st.cy, glowR)
      grad.addColorStop(0, `rgba(${cfg.rgb},0.14)`)
      grad.addColorStop(0.45, `rgba(${cfg.rgb},0.06)`)
      grad.addColorStop(1, `rgba(${cfg.rgb},0)`)
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(st.cx, st.cy, glowR, 0, Math.PI * 2)
      ctx.fill()
    })

    // 第三遍：三球点云叠在光晕与背景传输粒子之上，点更密看起来更实体
    SPHERES.forEach((cfg) => {
      const st = sphereState[cfg.key]
      st.angle += cfg.spin
      // 鼠标带来的轻量视差倾斜，叠加在球体固有轴倾角之上
      const tilt = cfg.tilt + (curY - 0.5) * 0.5
      const pulseBoost = pulsing.value[cfg.key] ? (Math.sin(now * 0.02) + 1) / 2 * 0.55 : 0
      const cosA = Math.cos(st.angle)
      const sinA = Math.sin(st.angle)
      const cosT = Math.cos(tilt)
      const sinT = Math.sin(tilt)

      for (let i = 0; i < st.pts.length; i++) {
        const [x, y, z] = st.pts[i]
        const rx = x * cosA + z * sinA
        const rz = -x * sinA + z * cosA
        const fy = y * cosT - rz * sinT
        const fz = y * sinT + rz * cosT
        const depth = (fz + 1) / 2
        const px = st.cx + rx * st.radius * (1 + pulseBoost * 0.05)
        const py = st.cy + fy * st.radius * (1 + pulseBoost * 0.05)
        const alpha = (0.24 + depth * 0.62) * (1 + pulseBoost * 0.5)
        const size = 0.55 + depth * 1.05
        ctx.fillStyle = `rgba(${cfg.rgb},${Math.min(1, alpha).toFixed(3)})`
        ctx.beginPath()
        ctx.arc(px, py, size, 0, Math.PI * 2)
        ctx.fill()
      }
    })
  }

  const step = (now) => {
    if (!hovering) {
      t += 0.006
      targetX = 0.5 + Math.cos(t) * 0.16
      targetY = 0.5 + Math.sin(t * 0.85) * 0.12
    }
    curX += (targetX - curX) * 0.055
    curY += (targetY - curY) * 0.055
    drawSpheres(now)
    if (interactive) rafId = requestAnimationFrame(step)
  }

  if (!interactive) {
    // 减弱动态效果：只画静态帧（球体大小仍反映真实数量），不自转、不跟随鼠标；
    // 数据轮询更新时由 fetchAssetCounts 调用 redrawStaticSpheres 补画一帧
    drawSpheres(performance.now())
    redrawStaticSpheres = () => drawSpheres(performance.now())
    return () => {
      if (ro) ro.disconnect()
      redrawStaticSpheres = null
    }
  }

  step(performance.now())

  return () => {
    cancelAnimationFrame(rafId)
    hero.removeEventListener('pointermove', onMove)
    hero.removeEventListener('pointerleave', onLeave)
    if (ro) ro.disconnect()
  }
}

/* 部门卡片聚光灯：高光位置跟随光标（直接写 DOM 样式） */
const cardSpot = (e) => {
  const el = e.currentTarget
  const r = el.getBoundingClientRect()
  el.style.setProperty('--sx', `${e.clientX - r.left}px`)
  el.style.setProperty('--sy', `${e.clientY - r.top}px`)
}

/* ---------- 滚动入场 + 数字滚动（IntersectionObserver） ---------- */
let revealObserver = null
let statsObserver = null
let countUpStarted = false

const startCountUp = () => {
  if (countUpStarted) return
  countUpStarted = true
  const target = stats.value
  if (prefersReducedMotion()) {
    displayStats.value = { ...target }
    return
  }
  const duration = 1100
  const start = performance.now()
  const tick = (now) => {
    const t = Math.min((now - start) / duration, 1)
    const ease = 1 - Math.pow(1 - t, 3)
    displayStats.value = {
      total: Math.round(target.total * ease),
      done: Math.round(target.done * ease),
      active: Math.round(target.active * ease),
      approved: Math.round(target.approved * ease),
    }
    if (t < 1) requestAnimationFrame(tick)
  }
  requestAnimationFrame(tick)
  setTimeout(() => { displayStats.value = { ...target } }, duration + 200)
}

onMounted(async () => {
  await fetchAllData()
  await fetchAssetCounts(true)
  pollTimer = setInterval(() => fetchAssetCounts(false), 30000)

  // 减弱动态效果时仍渲染一次静态星球（尺寸如实反映数量），只是不自转、不跟手
  stopHeroScene = initHeroSpheres(!prefersReducedMotion())

  const reveals = pageEl.value ? pageEl.value.querySelectorAll('.reveal') : []
  if (prefersReducedMotion()) {
    reveals.forEach((el) => el.classList.add('in'))
    startCountUp()
    return
  }
  revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('in')
          revealObserver.unobserve(e.target)
        }
      })
    },
    // threshold 必须为 0（任意一像素进入视口即显形）：
    // 若用比例阈值，高度超过视口数倍的区块（如需求列表长表格、展开后的项目分组）
    // 永远达不到该比例，会一直隐身但占位，表现为页面中大片"空白"
    { threshold: 0 }
  )
  reveals.forEach((el) => revealObserver.observe(el))

  if (statsEl.value) {
    statsObserver = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          startCountUp()
          statsObserver.disconnect()
        }
      },
      { threshold: 0.4 }
    )
    statsObserver.observe(statsEl.value)
  }
})

onBeforeUnmount(() => {
  if (stopHeroScene) stopHeroScene()
  if (revealObserver) revealObserver.disconnect()
  if (statsObserver) statsObserver.disconnect()
  if (pollTimer) clearInterval(pollTimer)
})

/* ---------- 数据加工（与旧版首页同一套规则） ---------- */
const processedProjects = computed(() => projects.value)

const departmentOf = departmentFromProjectName

const PROGRESS_CATEGORIES = [
  { key: 'notStarted', label: '未开始', min: 0, max: 0 },
  { key: 'early', label: '初期阶段 1-30%', min: 1, max: 30 },
  { key: 'mid', label: '中期阶段 31-70%', min: 31, max: 70 },
  { key: 'late', label: '后期阶段 71-99%', min: 71, max: 99 },
  { key: 'done', label: '已完成 100%', min: 100, max: 100 },
]

const categorized = computed(() =>
  PROGRESS_CATEGORIES.map((cat) => {
    const items = processedProjects.value.filter(
      (p) => (p.progress || 0) >= cat.min && (p.progress || 0) <= cat.max
    )
    const groups = {}
    items.forEach((p) => {
      const dept = departmentOf(p.name)
      if (!groups[dept]) groups[dept] = []
      groups[dept].push(p)
    })
    const departments = Object.entries(groups)
      .map(([name, list]) => ({ name, projects: list }))
      .sort((a, b) => b.projects.length - a.projects.length)
    return { ...cat, total: items.length, departments }
  })
)

const countBy = (list, field) => {
  const summary = {}
  list.forEach((item) => {
    const key = item[field] || '未知'
    summary[key] = (summary[key] || 0) + 1
  })
  return summary
}

const projectSummary = computed(() => countBy(processedProjects.value, 'status'))
const requirementSummary = computed(() => countBy(requirements.value, 'status'))
const requirementGroups = computed(() => [
  {
    key: 'approved',
    title: '已通过',
    rows: requirements.value.filter((requirement) => requirement.status === '已通过'),
  },
  {
    key: 'not-approved',
    title: '未通过',
    rows: requirements.value.filter((requirement) => requirement.status !== '已通过'),
  },
])

const stats = computed(() => {
  const list = processedProjects.value
  return {
    total: list.length,
    done: list.filter((p) => (p.progress || 0) >= 100).length,
    active: list.filter((p) => (p.progress || 0) > 0 && (p.progress || 0) < 100).length,
    approved: requirements.value.filter((r) => r.status === '已通过').length,
  }
})

/* 跑马灯内容：各部门项目数（真实数据） */
const marqueeItems = computed(() => {
  const groups = countBy(
    processedProjects.value.map((p) => ({ dept: departmentOf(p.name) })),
    'dept'
  )
  return Object.entries(groups).map(([dept, n]) => `${dept} ${n} 个项目`)
})

/* 折叠状态：已完成分类默认收起 */
const collapsedGroups = ref({})
const groupKey = (catKey, dept) => `${catKey}|${dept}`
const isExpanded = (cat, dept) => {
  const key = groupKey(cat.key, dept)
  if (key in collapsedGroups.value) return !collapsedGroups.value[key]
  return cat.key !== 'done'
}
const toggleGroup = (cat, dept) => {
  const key = groupKey(cat.key, dept)
  collapsedGroups.value[key] = isExpanded(cat, dept)
}

const PROJECT_STATUS_CLASS = {
  使用: 'st-blue',
  在编: 'st-amber',
  大修: 'st-violet',
  停用: 'st-gray',
  // 兼容迁移前的历史状态，数据库回填完成后不会再产生这些值。
  已完成: 'st-green',
  开发中: 'st-amber',
  新编: 'st-violet',
}
const REQ_STATUS_CLASS = {
  已通过: 'st-green',
  已拒绝: 'st-red',
  待审核: 'st-amber',
}

const PIPELINE_STAGES = ['需求提交', '用户自助审核', '机器人开发', '上线交付', '运行维护']

/* 1:1 公司 logo：把原图保存为 frontend/public/logo.png 即可生效 */
const LOGO_SRC = '/logo.png'

const viewDetail = (row) => {
  currentReq.value = row
  showDetail.value = true
}

const scrollToProjects = () => {
  document.getElementById('projects-section')?.scrollIntoView({ behavior: 'smooth' })
}
</script>

<template>
  <div ref="pageEl" class="oa-page">
    <!-- 导航 -->
    <nav class="nav">
      <div class="nav-inner">
        <span class="brand">
          <img
            v-if="!logoMissing"
            class="brand-logo"
            :src="LOGO_SRC"
            alt="公司 logo"
            @error="logoMissing = true"
          />
          <span class="brand-name">AItools web</span>
        </span>
        <div class="nav-links">
          <router-link class="nav-link" to="/department-skills">各部门Skill情况</router-link>
          <router-link class="nav-link" to="/department-plugins">各部门Python插件情况</router-link>
          <router-link class="nav-link" to="/department">各部门RPA情况</router-link>
        </div>
        <div class="nav-actions">
          <router-link class="btn btn-black" to="/login">进入统一工作台</router-link>
        </div>
      </div>
    </nav>

    <main>
      <!-- Hero：全宽粒子星球背景 + 居中大字 -->
      <header ref="heroEl" class="hero">
        <canvas ref="sphereCanvasEl" class="hero-canvas"></canvas>
        <div class="sphere-labels">
          <span
            v-for="cfg in SPHERES"
            :key="cfg.key"
            class="sphere-name"
            :style="{ left: cfg.anchor[0] * 100 + '%', top: cfg.anchor[1] * 100 + '%', color: cfg.textColor }"
          >{{ cfg.shortLabel }}</span>
        </div>

        <div class="hero-copy-centered">
          <h1 class="hero-title">
            <span class="hero-line" style="--d: 0ms">让 AI 与机器人</span>
            <span class="hero-line" style="--d: 90ms">接管<em>重复工作</em></span>
          </h1>
          <p class="hero-sub hero-line" style="--d: 180ms">
            RPA 机器人、Skill 文件、Python 插件，全生命周期一站式管理。
          </p>
          <div class="hero-actions hero-line" style="--d: 260ms">
            <button class="btn btn-black btn-lg" @click="scrollToProjects">查看项目进度</button>
            <router-link class="btn btn-gray btn-lg" to="/login">提交需求</router-link>
          </div>
        </div>
      </header>

      <!-- 部门覆盖跑马灯（全页唯一，真实数据） -->
      <div v-if="marqueeItems.length" class="marquee" aria-hidden="true">
        <div class="marquee-track">
          <span v-for="(item, i) in marqueeItems" :key="'a' + i" class="marquee-item">{{ item }}</span>
          <span v-for="(item, i) in marqueeItems" :key="'b' + i" class="marquee-item">{{ item }}</span>
        </div>
      </div>

      <div class="content">
        <!-- 数字概览 -->
        <section ref="statsEl" class="stats reveal">
          <div class="stat" style="--i: 0">
            <div class="stat-num">{{ displayStats.total }}</div>
            <div class="stat-label">项目总数</div>
          </div>
          <div class="stat" style="--i: 1">
            <div class="stat-num">{{ displayStats.done }}</div>
            <div class="stat-label">已完成</div>
          </div>
          <div class="stat" style="--i: 2">
            <div class="stat-num">{{ displayStats.active }}</div>
            <div class="stat-label">进行中</div>
          </div>
          <div class="stat" style="--i: 3">
            <div class="stat-num">{{ displayStats.approved }}</div>
            <div class="stat-label">需求已通过</div>
          </div>
        </section>

        <div v-if="loadFailed" class="load-alert reveal">数据加载失败，请稍后刷新重试</div>

        <!-- 项目生命周期 -->
        <section class="section reveal" aria-hidden="true">
          <svg viewBox="0 0 1000 100" width="100%" preserveAspectRatio="xMidYMid meet">
            <path
              id="flowline"
              d="M40,40 H960"
              fill="none"
              stroke="#e3e3de"
              stroke-width="2"
              stroke-dasharray="7 7"
              class="flow-dash"
            />
            <g v-for="(stage, i) in PIPELINE_STAGES" :key="stage">
              <circle :cx="40 + i * 230" cy="40" r="7" fill="#fbfbf9" stroke="#c9c9c2" stroke-width="2" />
              <text :x="40 + i * 230" y="78" text-anchor="middle" class="pipe-label">{{ stage }}</text>
            </g>
            <circle r="5" fill="#141413">
              <animateMotion dur="8s" repeatCount="indefinite" rotate="none">
                <mpath href="#flowline" />
              </animateMotion>
            </circle>
          </svg>
        </section>

        <!-- 状态汇总 -->
        <section class="section reveal">
          <h2 class="section-title">状态汇总</h2>
          <div class="summary">
            <div class="summary-group">
              <span class="summary-label">开发项目</span>
              <div class="chip-row">
                <template v-if="loading">
                  <span v-for="n in 3" :key="n" class="skeleton chip-skeleton"></span>
                </template>
                <template v-else>
                  <span v-for="(count, status) in projectSummary" :key="status" class="chip" :class="PROJECT_STATUS_CLASS[status] || 'st-gray'">
                    {{ status }} {{ count }}
                  </span>
                  <span v-if="Object.keys(projectSummary).length === 0" class="chip st-gray">暂无项目数据</span>
                </template>
              </div>
            </div>
            <div class="summary-group">
              <span class="summary-label">需求</span>
              <div class="chip-row">
                <template v-if="loading">
                  <span v-for="n in 3" :key="n" class="skeleton chip-skeleton"></span>
                </template>
                <template v-else>
                  <span v-for="(count, status) in requirementSummary" :key="status" class="chip" :class="REQ_STATUS_CLASS[status] || 'st-gray'">
                    {{ status }} {{ count }}
                  </span>
                  <span v-if="Object.keys(requirementSummary).length === 0" class="chip st-gray">暂无需求数据</span>
                </template>
              </div>
            </div>
          </div>
        </section>

        <!-- 项目进度 -->
        <section id="projects-section" class="section reveal">
          <h2 class="section-title">开发项目进度</h2>

          <div v-for="cat in categorized" :key="cat.key" class="category-block">
            <div class="category-head">
              <span class="category-name">{{ cat.label }}</span>
              <span class="category-count">{{ cat.total }} 个项目</span>
            </div>

            <p v-if="!loading && cat.total === 0" class="empty-note">暂无项目</p>

            <div
              v-for="dept in cat.departments"
              :key="dept.name"
              class="dept-card"
              @pointermove="cardSpot"
            >
              <button class="dept-head" @click="toggleGroup(cat, dept.name)">
                <span class="dept-name">{{ dept.name }}</span>
                <span class="dept-count">{{ dept.projects.length }} 个</span>
                <span class="chev" :class="{ open: isExpanded(cat, dept.name) }"></span>
              </button>

              <div v-if="isExpanded(cat, dept.name)" class="dept-body">
                <div v-for="project in dept.projects" :key="project.id" class="project-row">
                  <span class="project-name">{{ project.name }}</span>
                  <span class="chip" :class="PROJECT_STATUS_CLASS[project.status] || 'st-gray'">{{ project.status }}</span>
                  <div class="bar-track">
                    <div
                      class="bar-fill"
                      :class="{ active: (project.progress || 0) > 0 && (project.progress || 0) < 100 }"
                      :style="{ width: (barsReady ? project.progress || 0 : 0) + '%' }"
                    ></div>
                  </div>
                  <span class="bar-num">{{ project.progress || 0 }}%</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 需求列表 -->
        <section class="section reveal">
          <h2 class="section-title">需求列表</h2>
          <div v-if="loading" class="table-wrap requirement-loading">
            <div class="skeleton row-skeleton"></div>
          </div>
          <div v-else-if="requirements.length" class="requirement-groups">
            <details v-for="group in requirementGroups" :key="group.key" class="requirement-group">
              <summary class="requirement-group-summary">
                <span class="requirement-group-title">
                  <span class="group-chevron" aria-hidden="true"></span>
                  {{ group.title }}
                </span>
                <span class="requirement-group-count">{{ group.rows.length }} 条需求</span>
              </summary>
              <div class="table-wrap requirement-table-wrap">
                <table class="req-table">
                  <thead>
                    <tr>
                      <th>需求标题</th>
                      <th>部门</th>
                      <th>提交人</th>
                      <th>状态</th>
                      <th>期望完成时间</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in group.rows" :key="row.id">
                      <td class="td-title">{{ row.title }}</td>
                      <td>{{ row.department }}</td>
                      <td>{{ row.requester }}</td>
                      <td><span class="chip" :class="REQ_STATUS_CLASS[row.status] || 'st-gray'">{{ row.status }}</span></td>
                      <td class="td-mono">{{ row.expected_time }}</td>
                      <td><button class="btn btn-gray btn-sm" @click="viewDetail(row)">详情</button></td>
                    </tr>
                    <tr v-if="group.rows.length === 0">
                      <td colspan="6" class="td-empty">暂无{{ group.title }}需求</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </details>
          </div>
          <div v-else class="table-wrap td-empty">
            暂无需求数据
          </div>
        </section>

        <footer class="footer">
          <img v-if="!logoMissing" class="footer-logo" :src="LOGO_SRC" alt="" @error="logoMissing = true" />
          <span>© 2026 上海焱坤网络科技 AItools web</span>
        </footer>
      </div>
    </main>

    <!-- 需求详情弹窗 -->
    <Transition name="modal">
      <div v-if="showDetail" class="modal-overlay" @click.self="showDetail = false">
        <div class="modal-panel">
          <div class="modal-head">
            <h3>需求详情</h3>
            <button class="modal-close" @click="showDetail = false">✕</button>
          </div>
          <dl v-if="currentReq" class="detail-list">
            <div class="detail-row"><dt>需求标题</dt><dd>{{ currentReq.title }}</dd></div>
            <div class="detail-row"><dt>部门</dt><dd>{{ currentReq.department || '-' }}</dd></div>
            <div class="detail-row"><dt>提交人</dt><dd>{{ currentReq.requester || '-' }}</dd></div>
            <div class="detail-row">
              <dt>状态</dt>
              <dd><span class="chip" :class="REQ_STATUS_CLASS[currentReq.status] || 'st-gray'">{{ currentReq.status }}</span></dd>
            </div>
            <div class="detail-row"><dt>期望完成时间</dt><dd class="td-mono">{{ currentReq.expected_time || '-' }}</dd></div>
            <div class="detail-row"><dt>需求描述</dt><dd>{{ currentReq.description || '-' }}</dd></div>
          </dl>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* ---------- 浅色单主题（OpenAI 参考系） ---------- */
.oa-page {
  --bg: #fbfbf9;
  --raised: #ffffff;
  --text: #141413;
  --muted: #6e6e73;
  --line: #e9e9e4;
  --violet: #6e7bd9;
  --mono: 'Cascadia Code', Consolas, 'Courier New', monospace;

  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  /* Inter 接管西文与数字（更精致的字重与字距），中文交给系统黑体 */
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-feature-settings: 'cv11', 'ss01', 'tnum';
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

.oa-page h1, .oa-page h2, .oa-page h3 { letter-spacing: -0.01em; }

/* ---------- 按钮（胶囊；容器 16px，两套圆角规则全页统一） ---------- */
.btn {
  display: inline-block;
  font-size: 14px;
  font-weight: 500;
  border-radius: 999px;
  padding: 10px 20px;
  cursor: pointer;
  text-decoration: none;
  font-family: inherit;
  white-space: nowrap;
  border: none;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}
.btn:active { transform: scale(0.98); }
.btn-black { background: #141413; color: #fbfbf9; }
.btn-black:hover {
  background: #333331;
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(20, 20, 19, 0.16);
}
.btn-gray { background: #f0f0ec; color: var(--text); }
.btn-gray:hover { background: #e7e7e2; transform: translateY(-2px); }
.btn-lg { padding: 13px 28px; font-size: 15px; }
.btn-sm { padding: 4px 15px; font-size: 12.5px; }

/* ---------- 导航 ---------- */
.nav {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(251, 251, 249, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--line);
}
.nav-inner {
  /* 不设 max-width 居中：logo 和按钮要贴着视口左右两侧，只留一点内边距 */
  box-sizing: border-box;
  width: 100%;
  padding: 0 28px;
  height: 66px;
  display: flex;
  align-items: center;
  gap: 26px;
}
.brand { display: flex; align-items: center; gap: 11px; flex-shrink: 0; }
.brand-logo { width: 32px; height: 32px; border-radius: 8px; display: block; flex-shrink: 0; }
.brand-name { font-size: 19px; font-weight: 800; letter-spacing: 0.3px; white-space: nowrap; }
.nav-links { display: flex; gap: 2px; flex: 1; }
.nav-link {
  color: var(--muted);
  text-decoration: none;
  font-size: 14px;
  padding: 8px 12px;
  border-radius: 999px;
  transition: color 0.18s, background 0.18s;
}
.nav-link:hover { color: var(--text); background: #f0f0ec; }
.nav-actions { display: flex; gap: 10px; flex-shrink: 0; }

/* ---------- Hero：不对称分屏 ---------- */
/* ---------- Hero：全宽粒子星球背景 + 居中大字（呼应 OpenAI 首屏构图，
   但不用其配色/纹理，星球是我们自己的费波那契撒点球） ---------- */
.hero {
  position: relative;
  overflow: hidden;
  min-height: 640px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  border-bottom: 1px solid var(--line);
}
.hero-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.sphere-labels {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.sphere-name {
  position: absolute;
  transform: translate(-50%, -50%);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.01em;
  white-space: nowrap;
  text-shadow: 0 0 10px var(--bg), 0 0 18px var(--bg), 0 0 4px var(--bg);
}

.hero-copy-centered {
  position: relative;
  z-index: 1;
  max-width: 720px;
  margin: 0 auto;
  padding: 0 32px;
  text-align: center;
}
.hero-title {
  font-size: clamp(38px, 5.4vw, 62px);
  font-weight: 800;
  line-height: 1.16;
  letter-spacing: 0.5px;
  margin: 0 0 20px;
}
.hero-title span { display: block; }
.hero-title em {
  font-style: normal;
  background: linear-gradient(100deg, #7e8ce8, #9b8ce0 55%, #78aede);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.hero-sub {
  color: var(--muted);
  font-size: 17px;
  line-height: 1.7;
  margin: 0 auto 34px;
  max-width: 32em;
}
.hero-actions { display: flex; gap: 14px; justify-content: center; }

/* Hero 文案入场（加载时一次） */
.hero-line {
  animation: line-in 0.85s cubic-bezier(0.16, 1, 0.3, 1) both;
  animation-delay: var(--d, 0ms);
}
@keyframes line-in {
  from { opacity: 0; transform: translateY(26px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ---------- 跑马灯（全页唯一） ---------- */
.marquee {
  overflow: hidden;
  border-bottom: 1px solid var(--line);
  padding: 13px 0;
  background: var(--raised);
}
.marquee-track {
  display: inline-flex;
  white-space: nowrap;
  animation: marquee 26s linear infinite;
}
.marquee-item {
  font-family: var(--mono);
  font-size: 13px;
  color: var(--muted);
  padding: 0 34px;
  border-right: 1px solid var(--line);
}
@keyframes marquee {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

/* ---------- 主体 ---------- */
.content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 32px 72px;
}

/* 数字概览 */
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  padding: 56px 0 48px;
  border-bottom: 1px solid var(--line);
}
.stat-num {
  font-family: var(--mono);
  font-size: clamp(56px, 6.6vw, 92px);
  font-weight: 700;
  line-height: 1;
  letter-spacing: -2px;
  font-variant-numeric: tabular-nums;
}
.stat-label { color: var(--muted); font-size: 14.5px; margin-top: 12px; }

.load-alert {
  background: #fff7e6;
  border: 1px solid #ecd9a8;
  color: #9a6700;
  border-radius: 16px;
  padding: 12px 18px;
  font-size: 13.5px;
  margin: 18px 0;
}

/* 章节 */
.section { margin-top: 64px; }
.section-title { font-size: 28px; font-weight: 700; margin: 0 0 26px; letter-spacing: 0.3px; }

.flow-dash { animation: dash-march 1.4s linear infinite; }
@keyframes dash-march {
  from { stroke-dashoffset: 0; }
  to { stroke-dashoffset: -14; }
}
.pipe-label { font-size: 13px; fill: var(--muted); font-weight: 500; }

/* 状态汇总：无卡片，细线分组 */
.summary { border-top: 1px solid var(--line); }
.summary-group {
  display: flex;
  align-items: baseline;
  gap: 28px;
  padding: 20px 4px;
  border-bottom: 1px solid var(--line);
}
.summary-label { color: var(--muted); font-size: 14px; width: 72px; flex: none; }
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }

/* 状态章（胶囊，柔和粉彩底） */
.chip {
  font-size: 12.5px;
  font-weight: 600;
  padding: 4px 13px;
  border-radius: 999px;
  white-space: nowrap;
}
.st-green { color: #1a7f37; background: #e7f6ec; }
.st-blue { color: #0b6bab; background: #e0f0fe; }
.st-violet { color: #4f46b8; background: #eceafc; }
.st-amber { color: #9a6700; background: #fff4d6; }
.st-red { color: #cf222e; background: #ffebe9; }
.st-gray { color: var(--muted); background: #f0f0ec; }

/* 项目进度 */
.category-block { margin-bottom: 36px; }
.category-head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 12px; }
.category-name { font-size: 16.5px; font-weight: 700; }
.category-count { font-family: var(--mono); color: var(--muted); font-size: 12.5px; }
.empty-note { color: var(--muted); font-size: 13.5px; }

.dept-card {
  position: relative;
  background: var(--raised);
  border: 1px solid var(--line);
  border-radius: 16px;
  margin-bottom: 10px;
  overflow: hidden;
  transition: border-color 0.2s, transform 0.2s, box-shadow 0.2s;
}
.dept-card:hover {
  border-color: #d8d8d0;
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(20, 20, 19, 0.06);
}
/* 聚光灯：淡紫高光跟随光标 */
.dept-card::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.25s;
  background: radial-gradient(240px circle at var(--sx, 50%) var(--sy, 50%), rgba(110, 123, 217, 0.08), transparent 65%);
}
.dept-card:hover::after { opacity: 1; }

.dept-head {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 12px;
  padding: 16px 20px;
  background: none;
  border: none;
  color: var(--text);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  font-family: inherit;
}
.dept-count { font-family: var(--mono); color: var(--muted); font-size: 12.5px; font-weight: 400; flex: 1; text-align: left; }
.chev {
  width: 8px;
  height: 8px;
  border-right: 1.5px solid var(--muted);
  border-bottom: 1.5px solid var(--muted);
  transform: rotate(45deg);
  transition: transform 0.25s;
  margin-top: -4px;
}
.chev.open { transform: rotate(225deg); margin-top: 4px; }

.dept-body { padding: 2px 20px 14px; }
.project-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 0;
  border-top: 1px solid var(--line);
}
.project-row:first-child { border-top: none; }
.project-name {
  flex: 1;
  font-size: 14px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bar-track {
  width: 30%;
  min-width: 140px;
  height: 8px;
  background: #efefea;
  border-radius: 999px;
  overflow: hidden;
}
.bar-fill {
  position: relative;
  height: 100%;
  border-radius: 999px;
  background: #141413;
  transition: width 1s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
}
/* 进行中：光带扫过，表达"任务在跑" */
.bar-fill.active::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.45), transparent);
  transform: translateX(-100%);
  animation: sweep 2s ease-in-out infinite;
}
@keyframes sweep {
  to { transform: translateX(100%); }
}
.bar-num {
  width: 48px;
  text-align: right;
  font-family: var(--mono);
  font-size: 13px;
  color: var(--muted);
}

/* 需求表 */
.requirement-groups {
  display: grid;
  gap: 12px;
}
.requirement-group {
  background: var(--raised);
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}
.requirement-group-summary {
  min-height: 58px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  cursor: pointer;
  list-style: none;
  font-weight: 600;
  transition: background 0.15s;
}
.requirement-group-summary::-webkit-details-marker { display: none; }
.requirement-group-summary:hover { background: #fafaf7; }
.requirement-group-title {
  display: flex;
  align-items: center;
  gap: 10px;
}
.group-chevron {
  width: 8px;
  height: 8px;
  border-right: 2px solid var(--muted);
  border-bottom: 2px solid var(--muted);
  transform: rotate(-45deg);
  transition: transform 0.18s;
}
.requirement-group[open] .group-chevron { transform: rotate(45deg); }
.requirement-group-count {
  color: var(--muted);
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
}
.requirement-table-wrap {
  border: 0;
  border-top: 1px solid var(--line);
  border-radius: 0;
}
.requirement-loading { padding: 20px; }
.table-wrap {
  background: var(--raised);
  border: 1px solid var(--line);
  border-radius: 16px;
  overflow-x: auto;
}
.req-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.req-table th {
  text-align: left;
  color: var(--muted);
  font-weight: 500;
  font-size: 12.5px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
}
.req-table td { padding: 14px 20px; border-bottom: 1px solid var(--line); }
.req-table tbody tr { transition: background 0.15s; }
.req-table tbody tr:hover { background: #fafaf7; }
.req-table tbody tr:last-child td { border-bottom: none; }
.td-title { font-weight: 600; }
.td-mono { font-family: var(--mono); font-size: 13px; color: var(--muted); }
.td-empty { text-align: center; color: var(--muted); padding: 32px 0; }

.footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--muted);
  font-size: 13px;
  margin-top: 72px;
  padding-top: 26px;
  border-top: 1px solid var(--line);
}
.footer-logo { width: 22px; height: 22px; border-radius: 6px; }

/* 骨架屏 */
.skeleton {
  border-radius: 999px;
  background: linear-gradient(90deg, #efefea, #f7f7f3, #efefea);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}
.chip-skeleton { width: 84px; height: 26px; }
.row-skeleton { height: 18px; margin: 4px 0; border-radius: 6px; }
@keyframes shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

/* ---------- 弹窗 ---------- */
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
  background: var(--raised);
  border-radius: 16px;
  padding: 28px 32px;
  box-shadow: 0 24px 70px rgba(20, 20, 19, 0.18);
}
.modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.modal-head h3 { margin: 0; font-size: 18px; font-weight: 700; }
.modal-close {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 14px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 999px;
  transition: color 0.18s, background 0.18s;
}
.modal-close:hover { color: var(--text); background: #f0f0ec; }
.detail-list { margin: 0; }
.detail-row {
  display: flex;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
  font-size: 14px;
}
.detail-row:last-child { border-bottom: none; }
.detail-row dt { width: 96px; flex: none; color: var(--muted); }
.detail-row dd { margin: 0; flex: 1; line-height: 1.65; }

.modal-enter-active, .modal-leave-active { transition: opacity 0.22s; }
.modal-enter-active .modal-panel, .modal-leave-active .modal-panel { transition: transform 0.22s cubic-bezier(0.22, 1, 0.36, 1); }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal-panel, .modal-leave-to .modal-panel { transform: translateY(12px) scale(0.98); }

/* ---------- 滚动入场 ---------- */
.reveal {
  opacity: 0;
  transform: translateY(26px);
  transition: opacity 0.75s cubic-bezier(0.16, 1, 0.3, 1), transform 0.75s cubic-bezier(0.16, 1, 0.3, 1);
}
.reveal.in { opacity: 1; transform: translateY(0); }
.stats.reveal .stat {
  opacity: 0;
  transform: translateY(18px);
  transition: opacity 0.7s cubic-bezier(0.16, 1, 0.3, 1), transform 0.7s cubic-bezier(0.16, 1, 0.3, 1);
  transition-delay: calc(var(--i) * 80ms);
}
.stats.reveal.in .stat { opacity: 1; transform: translateY(0); }

/* ---------- 降级与响应式 ---------- */
@media (prefers-reduced-motion: reduce) {
  .hero-line, .marquee-track, .flow-dash, .bar-fill.active::after, .skeleton {
    animation: none !important;
  }
  .reveal, .stats.reveal .stat { opacity: 1; transform: none; transition: none; }
  .bar-fill { transition: none; }
  .dept-card::after { display: none; }
}

@media (max-width: 900px) {
  .nav-links { display: none; }
  .hero { min-height: 520px; }
  .hero-copy-centered { padding: 0 20px; }
  .sphere-name { font-size: 12px; }
  .stats { grid-template-columns: repeat(2, 1fr); }
  .content { padding: 0 20px 56px; }
  .summary-group { flex-direction: column; gap: 12px; }
  .bar-track { min-width: 90px; }
  .pipe-label { font-size: 16px; }
}

@media (max-width: 480px) {
  /* 窄屏放不下"品牌名 + 两个按钮"，先砍品牌文字，按钮再收紧一档，
     两个都不够时才会溢出——目前实测够用 */
  .nav-inner { padding: 0 16px; gap: 10px; }
  .brand-name { display: none; }
  .nav-actions .btn { padding: 8px 14px; font-size: 12.5px; }
}
</style>
