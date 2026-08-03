<!-- 新版首页功能保持不变，首屏粒子球视觉按最初版本呈现。 -->
<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import http from '@/api/http'
import { fetchPublicAssets } from '@/api/assets'
import { departmentFromProjectName } from '@/utils/departments'

/* 设计规范（taste-skill，VARIANCE 8 / MOTION 7 / DENSITY 4）：
   全页浅色单主题，配色参考 OpenAI 的克制感（米白底 + 近黑文字，标题强调词用淡紫渐变），
   字体 Inter 负责西文/数字，中文走系统黑体；
   圆角体系：按钮与状态章为胶囊，容器 16px；
   Hero 视觉：全宽 canvas 铺三颗粒子星球（RPA / Skill / Python，费波那契球面撒点），
   持续自转，半径随对应数量实时变化，且恒被 Hero 容器尺寸钳制，永远不会撑出版面；
   每球自带彩色柔光光晕；球体后方空白处飘着缓慢漂移的"数据传输"粒子（带尾迹），
   画在最底层，被球体自然遮挡，球与球之间不连线，背景保持干净；
   球心叠加名字，轻量鼠标视差贯穿整个 Hero；标题居中叠在星球之上；
   部门卡片聚光灯悬停；
   logo 用原图 frontend/public/logo.png（1:1，不用自绘替身），仅导航与页脚小尺寸。 */

const projects = ref([])
const publicAssets = ref([])
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
   首屏视觉沿用最初版本的“左侧黑色大球、右上淡紫小球、右下蓝绿中球”构图；
   性能优化、实时数量和数量变化脉冲功能保持不变。 */
const SPHERES = [
  {
    key: 'rpa',
    palette: ['20,20,19', '20,20,19', '20,20,19', '20,20,19'],
    glow: '20,20,19',
    textColor: '#141413',
    shortLabel: 'RPA',
    colorPhase: 0.4,
    anchor: [0.13, 0.58],
    spin: 0.0026,
    tilt: 0.30,
  },
  {
    key: 'skill',
    palette: ['110,123,217', '110,123,217', '110,123,217', '110,123,217'],
    glow: '110,123,217',
    textColor: '#4a4fb0',
    shortLabel: 'Skill',
    colorPhase: 2.2,
    anchor: [0.90, 0.24],
    spin: -0.0032,
    tilt: -0.24,
  },
  {
    key: 'plugin',
    palette: ['74,158,168', '74,158,168', '74,158,168', '74,158,168'],
    glow: '74,158,168',
    textColor: '#2f7a82',
    shortLabel: 'Python',
    colorPhase: 4.1,
    anchor: [0.84, 0.80],
    spin: 0.0021,
    tilt: 0.40,
  },
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
    const skillAssets = (skillRes.data?.data ?? []).map((asset) => ({
      ...asset,
      asset_type: 'skill',
    }))
    const pluginAssets = (pluginRes.data?.data ?? []).map((asset) => ({
      ...asset,
      asset_type: 'python_plugin',
    }))
    publicAssets.value = [...skillAssets, ...pluginAssets]
    const next = {
      rpa: projects.value.length,
      skill: skillAssets.length,
      plugin: pluginAssets.length,
    }
    const prev = assetCounts.value
    if (!isFirstLoad) {
      SPHERES.forEach(({ key }) => {
        if (prev[key] !== next[key]) triggerPulse(key)
      })
    }
    assetCounts.value = next
    if (!isFirstLoad && countUpStarted) {
      displayStats.value = { ...stats.value }
    }
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
  let lastDrawAt = -Infinity

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
    const count = Math.max(24, Math.min(48, Math.round((cw * ch) / 18000)))
    ambientDots = Array.from({ length: count }, () => ({
      x: Math.random() * cw,
      y: Math.random() * ch,
      vx: 0.18 + Math.random() * 0.22,
      vy: (Math.random() - 0.5) * 0.05,
      r: 0.5 + Math.random() * 0.6,
      a: 0.14 + Math.random() * 0.18,
      phase: Math.random() * Math.PI * 2,
    }))
  }

  const resizeCanvas = () => {
    if (!canvas) return
    // 粒子点云不需要按文字级清晰度渲染；限制 DPR 可显著降低高分屏首帧像素量。
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
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
    // 球体尺寸与参考版一致：最大半径不超过画面短边的 30%，并受各自可用空间约束。
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
      const ambientColor = '100,104,145'
      const ambientAlpha = d.a * (0.72 + Math.sin(now * 0.0012 + d.phase) * 0.28)
      ctx.fillStyle = `rgba(${ambientColor},${Math.max(0.04, ambientAlpha).toFixed(3)})`
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
      // 首帧直接使用目标半径，避免加载阶段半径增长时连续重算整颗球的点集。
      st.radius = !st.radius || !interactive
        ? desiredR
        : st.radius + (desiredR - st.radius) * 0.08
      st.cx = cx + parallaxX
      st.cy = cy + parallaxY

      const n = Math.max(160, Math.min(560, Math.round(st.radius * 3.8)))
      if (Math.abs(n - st.n) > 10 || st.pts.length === 0) {
        st.pts = fibonacciSphere(n)
        st.n = n
      }
    })

    // 第二遍：每颗球周围的柔光光晕（参考截图里球体透出的色彩光斑），画在最底层
    SPHERES.forEach((cfg) => {
      const st = sphereState[cfg.key]
      if (st.radius < 2) return
      const glowR = st.radius * 1.7
      const glowBreath = 0.085 + Math.sin(now * 0.00075 + cfg.colorPhase) * 0.012
      const grad = ctx.createRadialGradient(st.cx, st.cy, st.radius * 0.15, st.cx, st.cy, glowR)
      grad.addColorStop(0, `rgba(${cfg.glow},${glowBreath.toFixed(3)})`)
      grad.addColorStop(0.45, `rgba(${cfg.glow},${(glowBreath * 0.46).toFixed(3)})`)
      grad.addColorStop(1, `rgba(${cfg.glow},0)`)
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
      const colorTime = now * 0.00004

      for (let i = 0; i < st.pts.length; i++) {
        const [x, y, z] = st.pts[i]
        const rx = x * cosA + z * sinA
        const rz = -x * sinA + z * cosA
        const fy = y * cosT - rz * sinT
        const fz = y * sinT + rz * cosT
        const depth = (fz + 1) / 2
        const px = st.cx + rx * st.radius * (1 + pulseBoost * 0.05)
        const py = st.cy + fy * st.radius * (1 + pulseBoost * 0.05)
        const alpha = (0.06 + Math.pow(depth, 1.35) * 0.94) * (1 + pulseBoost * 0.5)
        // 两层低频波把相邻粒子聚成缓慢流动的色块，避免随机彩点造成噪声。
        const colorWave =
          Math.sin((x * 1.9 + y * 0.75 + z * 1.25) * 3.1 + cfg.colorPhase + colorTime)
          + Math.sin((x * -0.8 + y * 1.65 + z * 0.55) * 5.2 - colorTime * 0.72) * 0.55
        const colorIndex = Math.max(
          0,
          Math.min(
            cfg.palette.length - 1,
            Math.floor(((colorWave + 1.55) / 3.1) * cfg.palette.length)
          )
        )
        ctx.fillStyle = `rgba(${cfg.palette[colorIndex]},${Math.min(1, alpha).toFixed(3)})`
        const size = 0.45 + depth * 1.15
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
    // 点云限制到约 24fps；慢速自转无需 60fps，低功耗设备也更稳定。
    if (document.visibilityState !== 'hidden' && now - lastDrawAt >= 1000 / 24) {
      drawSpheres(now)
      lastDrawAt = now
    }
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

const departmentOf = departmentFromProjectName

const RESOURCE_LABELS = {
  rpa: 'RPA',
  skill: 'Skill',
  python_plugin: 'Python',
}

/* ---------- 数据加工：RPA、Skill、Python 使用同一套首页进度口径 ---------- */
const processedProjects = computed(() => [
  ...projects.value.map((project) => ({
    ...project,
    rowKey: `rpa-${project.id}`,
    resourceType: 'rpa',
    resourceLabel: RESOURCE_LABELS.rpa,
    department: departmentOf(project.name),
    progress: Number(project.progress || 0),
  })),
  ...publicAssets.value.map((asset) => ({
    ...asset,
    rowKey: `${asset.asset_type}-${asset.id}`,
    resourceType: asset.asset_type,
    resourceLabel: RESOURCE_LABELS[asset.asset_type] || '其他',
    department: asset.department || '未指定部门',
    status: asset.lifecycle_status,
    progress: Number(asset.progress || 0),
  })),
])

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
      const dept = p.department || departmentOf(p.name)
      if (!groups[dept]) groups[dept] = []
      groups[dept].push(p)
    })
    const departments = Object.entries(groups)
      .map(([name, list]) => ({ name, projects: list }))
      .sort((a, b) => b.projects.length - a.projects.length)
    return {
      ...cat,
      total: items.length,
      typeCounts: {
        rpa: items.filter((item) => item.resourceType === 'rpa').length,
        skill: items.filter((item) => item.resourceType === 'skill').length,
        python: items.filter((item) => item.resourceType === 'python_plugin').length,
      },
      departments,
    }
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
    done: list.filter((p) => p.status === '使用').length,
    active: list.filter((p) => ['在编', '大修'].includes(p.status)).length,
    approved: requirements.value.filter((r) => r.status === '已通过').length,
  }
})

/* 跑马灯内容：各部门项目数（真实数据） */
const marqueeItems = computed(() => {
  const groups = countBy(
    processedProjects.value.map((p) => ({ dept: p.department || departmentOf(p.name) })),
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

/* 1:1 公司 logo：把原图保存为 frontend/public/logo.png 即可生效（换图请保持此文件名不变） */
const LOGO_SRC = '/logo.png'

const viewDetail = (row) => {
  currentReq.value = row
  showDetail.value = true
}

const scrollToProjects = () => {
  document.getElementById('projects-section')?.scrollIntoView({
    behavior: prefersReducedMotion() ? 'auto' : 'smooth',
  })
}
</script>

<template>
  <div ref="pageEl" class="oa-page">
    <nav class="nav" aria-label="首页导航">
      <div class="nav-inner">
        <router-link class="brand" to="/" aria-label="AI Tools web 首页">
          <img
            v-if="!logoMissing"
            class="brand-logo"
            :src="LOGO_SRC"
            alt="公司 logo"
            @error="logoMissing = true"
          />
          <span class="brand-name">AI Tools web</span>
        </router-link>
        <div class="nav-links">
          <a class="nav-link is-active" href="#overview">数据总览</a>
          <router-link class="nav-link" to="/department">RPA 项目</router-link>
          <router-link class="nav-link" to="/department-skills">Skill</router-link>
          <router-link class="nav-link" to="/department-plugins">Python</router-link>
        </div>
        <div class="nav-actions">
          <router-link class="btn btn-black" to="/login">
            进入工作台
            <span aria-hidden="true">↗</span>
          </router-link>
        </div>
      </div>
    </nav>

    <main>
      <header ref="heroEl" class="hero">
        <canvas ref="sphereCanvasEl" class="hero-canvas" aria-hidden="true"></canvas>
        <div class="sphere-labels" aria-hidden="true">
          <span
            v-for="cfg in SPHERES"
            :key="cfg.key"
            class="sphere-name"
            :style="{
              left: cfg.anchor[0] * 100 + '%',
              top: cfg.anchor[1] * 100 + '%',
              color: cfg.textColor,
            }"
          >
            {{ cfg.shortLabel }}
            <b class="sphere-count">{{ assetCounts[cfg.key] }}</b>
          </span>
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

      <div class="content">
        <section id="overview" ref="statsEl" class="section overview-section reveal">
          <div class="section-heading">
            <div>
              <p class="section-kicker">DATA OVERVIEW</p>
              <h2 class="section-title">一页看清平台数据</h2>
            </div>
            <p class="section-description">
              项目总数由 RPA、Skill 和 Python 共同组成，统一使用同一套进度与状态口径。
            </p>
          </div>

          <div class="overview-grid">
            <article class="total-card">
              <div class="card-topline">
                <span>平台项目总数</span>
                <span class="data-badge">
                  <span class="live-dot" aria-hidden="true"></span>
                  实时
                </span>
              </div>
              <div class="stat-num">{{ displayStats.total }}</div>
              <div class="stat-label">个自动化项目</div>
              <div class="stat-detail">
                RPA {{ assetCounts.rpa }} · Skill {{ assetCounts.skill }} · Python {{ assetCounts.plugin }}
              </div>
              <div class="total-substats">
                <div>
                  <strong>{{ displayStats.done }}</strong>
                  <span>已完成</span>
                </div>
                <div>
                  <strong>{{ displayStats.active }}</strong>
                  <span>进行中</span>
                </div>
                <div>
                  <strong>{{ displayStats.approved }}</strong>
                  <span>需求已通过</span>
                </div>
              </div>
            </article>

            <div class="resource-grid">
              <router-link class="resource-card resource-rpa-card" to="/department">
                <div class="resource-card-head">
                  <span class="resource-chip resource-rpa">RPA</span>
                  <span class="resource-arrow" aria-hidden="true">↗</span>
                </div>
                <strong class="resource-count">{{ assetCounts.rpa }}</strong>
                <span class="resource-unit">个 RPA 项目</span>
                <p>查看各部门 RPA 项目、进度与运行状态。</p>
              </router-link>

              <router-link class="resource-card resource-skill-card" to="/department-skills">
                <div class="resource-card-head">
                  <span class="resource-chip resource-skill">Skill</span>
                  <span class="resource-arrow" aria-hidden="true">↗</span>
                </div>
                <strong class="resource-count">{{ assetCounts.skill }}</strong>
                <span class="resource-unit">个 Skill 文件</span>
                <p>查看各部门 Skill 文件与开发进度。</p>
              </router-link>

              <router-link class="resource-card resource-python-card" to="/department-plugins">
                <div class="resource-card-head">
                  <span class="resource-chip resource-python_plugin">Python</span>
                  <span class="resource-arrow" aria-hidden="true">↗</span>
                </div>
                <strong class="resource-count">{{ assetCounts.plugin }}</strong>
                <span class="resource-unit">个 Python 文件</span>
                <p>查看各部门 Python 插件与开发进度。</p>
              </router-link>
            </div>
          </div>

          <div class="status-panel">
            <div class="status-panel-title">
              <span>当前项目状态</span>
              <span>RPA、Skill、Python 合并统计</span>
            </div>
            <div class="status-grid">
              <div class="status-item">
                <span class="status-dot dot-amber" aria-hidden="true"></span>
                <span>在编</span>
                <strong>{{ projectSummary['在编'] || 0 }}</strong>
              </div>
              <div class="status-item">
                <span class="status-dot dot-blue" aria-hidden="true"></span>
                <span>使用</span>
                <strong>{{ projectSummary['使用'] || 0 }}</strong>
              </div>
              <div class="status-item">
                <span class="status-dot dot-violet" aria-hidden="true"></span>
                <span>大修</span>
                <strong>{{ projectSummary['大修'] || 0 }}</strong>
              </div>
              <div class="status-item">
                <span class="status-dot dot-gray" aria-hidden="true"></span>
                <span>停用</span>
                <strong>{{ projectSummary['停用'] || 0 }}</strong>
              </div>
              <div class="status-item status-item-requirement">
                <span class="status-dot dot-green" aria-hidden="true"></span>
                <span>已通过需求</span>
                <strong>{{ requirementSummary['已通过'] || 0 }}</strong>
              </div>
            </div>
          </div>
        </section>

        <div v-if="loadFailed" class="load-alert reveal">数据加载失败，请稍后刷新重试</div>

        <section id="projects-section" class="section reveal">
          <div class="section-heading">
            <div>
              <p class="section-kicker">PROJECT PROGRESS</p>
              <h2 class="section-title">开发项目进度</h2>
            </div>
            <p class="section-description">
              先看五个进度阶段的数量分布，再按需展开部门和项目明细。
            </p>
          </div>

          <div class="progress-overview">
            <div v-for="cat in categorized" :key="`summary-${cat.key}`" class="progress-card">
              <div class="progress-card-top">
                <span>{{ cat.label }}</span>
                <strong>{{ cat.total }}</strong>
              </div>
              <div class="progress-mini-track" aria-hidden="true">
                <span
                  :style="{
                    width: (
                      cat.total && stats.total
                        ? Math.max(4, Math.round((cat.total / stats.total) * 100))
                        : 0
                    ) + '%'
                  }"
                ></span>
              </div>
              <small>
                RPA {{ cat.typeCounts.rpa }} · Skill {{ cat.typeCounts.skill }} · Python {{ cat.typeCounts.python }}
              </small>
            </div>
          </div>

          <div class="project-directory">
            <div class="directory-heading">
              <span>项目明细</span>
              <span>点击进度阶段展开</span>
            </div>
            <details
              v-for="cat in categorized"
              :key="cat.key"
              class="progress-group"
              :open="cat.key === 'notStarted'"
            >
              <summary class="progress-group-summary">
                <span class="progress-group-name">
                  <span class="group-chevron" aria-hidden="true"></span>
                  {{ cat.label }}
                </span>
                <span class="progress-group-meta">
                  <span>{{ cat.total }} 个项目</span>
                  <span class="category-types">
                    RPA {{ cat.typeCounts.rpa }} · Skill {{ cat.typeCounts.skill }} · Python {{ cat.typeCounts.python }}
                  </span>
                </span>
              </summary>

              <div class="progress-group-body">
                <p v-if="!loading && cat.total === 0" class="empty-note">暂无项目</p>
                <template v-if="loading">
                  <div class="skeleton row-skeleton"></div>
                </template>

                <div
                  v-for="dept in cat.departments"
                  :key="dept.name"
                  class="dept-card"
                  @pointermove="cardSpot"
                >
                  <button
                    class="dept-head"
                    :aria-expanded="isExpanded(cat, dept.name)"
                    @click="toggleGroup(cat, dept.name)"
                  >
                    <span class="dept-name">{{ dept.name }}</span>
                    <span class="dept-count">{{ dept.projects.length }} 个项目</span>
                    <span class="chev" :class="{ open: isExpanded(cat, dept.name) }"></span>
                  </button>

                  <div v-if="isExpanded(cat, dept.name)" class="dept-body">
                    <div v-for="project in dept.projects" :key="project.rowKey" class="project-row">
                      <span class="project-id">{{ project.resourceLabel }} #{{ project.id }}</span>
                      <span class="project-name">{{ project.name }}</span>
                      <span class="resource-chip" :class="`resource-${project.resourceType}`">{{ project.resourceLabel }}</span>
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
            </details>
          </div>
        </section>

        <section class="section reveal">
          <div class="section-heading">
            <div>
              <p class="section-kicker">REQUIREMENTS</p>
              <h2 class="section-title">需求审核概览</h2>
            </div>
            <p class="section-description">
              需求按审核结果归类，展开后可查看提交部门、负责人和期望完成时间。
            </p>
          </div>

          <div class="requirement-overview">
            <div>
              <span>已通过</span>
              <strong>{{ requirementGroups[0].rows.length }}</strong>
            </div>
            <div>
              <span>未通过 / 待审核</span>
              <strong>{{ requirementGroups[1].rows.length }}</strong>
            </div>
            <router-link class="requirement-cta" to="/login">
              提交或审核需求
              <span aria-hidden="true">↗</span>
            </router-link>
          </div>

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
          <div class="footer-brand">
            <img v-if="!logoMissing" class="footer-logo" :src="LOGO_SRC" alt="" @error="logoMissing = true" />
            <span>AI Tools web</span>
          </div>
          <span>© 2026 上海焱坤网络科技</span>
        </footer>
      </div>
    </main>

    <Transition name="modal">
      <div v-if="showDetail" class="modal-overlay" @click.self="showDetail = false">
        <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="requirement-detail-title">
          <div class="modal-head">
            <h3 id="requirement-detail-title">需求详情</h3>
            <button class="modal-close" aria-label="关闭需求详情" @click="showDetail = false">✕</button>
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
  padding: 0 clamp(20px, 3.2vw, 72px);
  height: clamp(66px, 4.2vw, 76px);
  display: flex;
  align-items: center;
  gap: 26px;
}
.brand { display: flex; align-items: center; gap: 11px; flex-shrink: 0; }
/* logo 原图自带纯白背景，multiply 让白底融进浅色导航，消除色差 */
.brand-logo { width: 32px; height: 32px; border-radius: 8px; display: block; flex-shrink: 0; mix-blend-mode: multiply; }
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
  min-height: clamp(600px, 62vh, 840px);
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
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.01em;
  white-space: nowrap;
  text-shadow: 0 0 10px var(--bg), 0 0 18px var(--bg), 0 0 4px var(--bg);
}
/* 球心实时数量：RPA=项目数，Skill/Python=已通过的资产数（30 秒轮询刷新） */
.sphere-count {
  font-family: var(--mono);
  font-size: 16px;
  font-weight: 800;
  line-height: 1;
}

.hero-copy-centered {
  position: relative;
  z-index: 1;
  box-sizing: border-box;
  width: min(82vw, 920px);
  max-width: none;
  margin: 0 auto;
  padding: 0 clamp(24px, 3vw, 56px);
  text-align: center;
}
.hero-title {
  font-size: clamp(42px, 5vw, 78px);
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
  font-size: clamp(17px, 1.2vw, 20px);
  line-height: 1.7;
  margin: 0 auto 34px;
  max-width: 36em;
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
  box-sizing: border-box;
  width: min(92vw, 1920px);
  max-width: none;
  margin: 0 auto;
  padding: 0 clamp(24px, 3vw, 64px) clamp(64px, 5vw, 96px);
}

/* 数字概览 */
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: clamp(24px, 4vw, 88px);
  padding: clamp(48px, 4vw, 72px) 0 clamp(44px, 3.5vw, 64px);
  border-bottom: 1px solid var(--line);
}
.stat-num {
  font-family: var(--mono);
  font-size: clamp(58px, 6.2vw, 112px);
  font-weight: 700;
  line-height: 1;
  letter-spacing: -2px;
  font-variant-numeric: tabular-nums;
}
.stat-label { color: var(--muted); font-size: 14.5px; margin-top: 12px; }
.stat-detail {
  margin-top: 7px;
  color: var(--muted);
  font-family: var(--mono);
  font-size: 11.5px;
  line-height: 1.5;
}

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
.section { margin-top: clamp(56px, 4vw, 80px); }
.section-title { font-size: clamp(28px, 1.8vw, 34px); font-weight: 700; margin: 0 0 26px; letter-spacing: 0.3px; }

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
.category-types {
  margin-left: auto;
  color: var(--muted);
  font-family: var(--mono);
  font-size: 11.5px;
}
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
.project-id {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.project-name {
  flex: 1;
  font-size: 14px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.resource-chip {
  min-width: 50px;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 11.5px;
  font-weight: 700;
  text-align: center;
  white-space: nowrap;
}
.resource-rpa { color: #3f3f3b; background: #ecece7; }
.resource-skill { color: #4f46b8; background: #eceafc; }
.resource-python_plugin { color: #247079; background: #e3f4f5; }
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
.footer-logo { width: 22px; height: 22px; border-radius: 6px; mix-blend-mode: multiply; }

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
  .hero-copy-centered { width: 100%; padding: 0 20px; }
  .sphere-name { font-size: 12px; }
  .stats { grid-template-columns: repeat(2, 1fr); }
  .content { width: 100%; padding: 0 20px 56px; }
  .summary-group { flex-direction: column; gap: 12px; }
  .bar-track { min-width: 90px; }
  .category-types { display: none; }
  .pipe-label { font-size: 16px; }
}

@media (max-width: 480px) {
  /* 窄屏放不下"品牌名 + 两个按钮"，先砍品牌文字，按钮再收紧一档，
     两个都不够时才会溢出——目前实测够用 */
  .nav-inner { padding: 0 16px; gap: 10px; }
  .brand-name { display: none; }
  .nav-actions .btn { padding: 8px 14px; font-size: 12.5px; }
  .hero-title { font-size: clamp(34px, 10vw, 42px); }
}

/* ---------- 首页编辑式视觉重构（2026） ---------- */
.oa-page {
  --bg: var(--brand-bg, #fbfbf9);
  --raised: var(--brand-raised, #ffffff);
  --text: var(--brand-text, #141413);
  --muted: var(--brand-muted, #6e6e73);
  --line: var(--brand-line, #e9e9e4);
  --violet: var(--brand-violet, #6e7bd9);
  --mono: var(--brand-mono, 'Cascadia Code', Consolas, monospace);
  overflow-x: clip;
}

.oa-page *,
.oa-page *::before,
.oa-page *::after {
  box-sizing: border-box;
}

.oa-page :where(a, button, summary):focus-visible {
  outline: 3px solid rgba(110, 123, 217, 0.3);
  outline-offset: 3px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.btn-soft {
  color: var(--text);
  background: #f1f1ed;
}

.btn-soft:hover {
  background: #e8e8e3;
  transform: translateY(-2px);
}

.nav {
  background: rgba(255, 255, 253, 0.9);
  border-bottom-color: rgba(20, 20, 19, 0.08);
}

.nav-inner {
  max-width: none;
  height: 72px;
  margin: 0;
  padding: 0 clamp(12px, 1.4vw, 24px);
}

.brand {
  color: var(--text);
  text-decoration: none;
}

.nav-links {
  gap: 4px;
  margin-left: 14px;
}

.nav-link {
  color: #4f4f50;
  font-size: 14px;
  font-weight: 500;
}

.nav-link.is-active {
  color: var(--text);
  background: #f1f1ed;
}

.nav-actions {
  align-items: center;
  margin-left: auto;
}

.hero {
  min-height: 640px;
  isolation: auto;
  background: var(--bg);
  animation: none;
}

@keyframes hero-color-drift {
  0% {
    background-position: -3% 48%, 102% -3%, 101% 103%, 0 0;
  }
  50% {
    background-position: 2% 52%, 98% 3%, 97% 96%, 0 0;
  }
  100% {
    background-position: -1% 46%, 103% 1%, 100% 99%, 0 0;
  }
}

.hero::after {
  content: none;
}

.hero-canvas {
  z-index: 0;
  opacity: 1;
}

.sphere-name {
  font-size: 14px;
  opacity: 1;
  letter-spacing: 0.01em;
  text-transform: none;
}

.sphere-count {
  font-size: 16px;
}

.hero-copy-centered {
  width: auto;
  max-width: 720px;
  padding: 0 32px;
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  margin: 0 0 32px;
  color: #464646;
  font-size: 14px;
  font-weight: 550;
  letter-spacing: 0.035em;
}

.eyebrow-dot,
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #2c9a65;
  box-shadow: 0 0 0 5px rgba(44, 154, 101, 0.1);
}

.hero-title {
  margin: 0 0 20px;
  color: var(--text);
  font-size: clamp(38px, 5.4vw, 62px);
  font-weight: 800;
  line-height: 1.16;
  letter-spacing: 0.5px;
  text-wrap: initial;
}

.hero-title span {
  display: block;
}

.hero-sub {
  max-width: 32em;
  margin: 0 auto 34px;
  color: var(--muted);
  font-size: 17px;
  line-height: 1.7;
  text-wrap: initial;
}

.hero-actions {
  gap: 14px;
}

.hero-data-line {
  position: absolute;
  right: clamp(24px, 4vw, 72px);
  bottom: 0;
  left: clamp(24px, 4vw, 72px);
  display: flex;
  align-items: center;
  min-height: 78px;
  border-top: 1px solid rgba(20, 20, 19, 0.12);
  color: #4f4f50;
  font-size: 13px;
}

.hero-data-caption,
.hero-data-item {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 0 22px;
  border-right: 1px solid rgba(20, 20, 19, 0.1);
  white-space: nowrap;
}

.hero-data-caption {
  padding-left: 0;
  color: var(--text);
  font-weight: 600;
}

.hero-data-item b {
  color: var(--text);
  font-family: var(--mono);
  font-size: 15px;
}

.hero-data-jump {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  margin-left: auto;
  padding: 10px 0 10px 18px;
  border: 0;
  color: var(--text);
  background: transparent;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.content {
  width: min(calc(100% - 48px), 1280px);
  padding: 0 0 96px;
}

.section {
  margin-top: clamp(88px, 9vw, 132px);
  scroll-margin-top: 120px;
}

.overview-section {
  margin-top: clamp(76px, 8vw, 112px);
}

.section-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 480px);
  align-items: end;
  gap: 42px;
  margin-bottom: 34px;
}

.section-kicker {
  margin: 0 0 10px;
  color: #777778;
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.15em;
}

.section-title {
  margin: 0;
  font-size: clamp(32px, 3.2vw, 48px);
  font-weight: 680;
  line-height: 1.08;
  letter-spacing: -0.045em;
}

.section-description {
  max-width: 480px;
  margin: 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.75;
}

.overview-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.78fr) minmax(0, 1.42fr);
  gap: 16px;
}

.total-card {
  min-height: 358px;
  padding: 34px;
  border-radius: 24px;
  color: #f8f8f5;
  background:
    radial-gradient(circle at 82% 18%, rgba(110, 123, 217, 0.38), transparent 32%),
    #141413;
}

.card-topline,
.status-panel-title,
.directory-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.card-topline {
  color: rgba(255, 255, 255, 0.68);
  font-size: 13px;
}

.data-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 9px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 999px;
  color: rgba(255, 255, 255, 0.76);
  font-size: 11px;
}

.data-badge .live-dot {
  width: 5px;
  height: 5px;
  box-shadow: none;
}

.total-card .stat-num {
  margin-top: 30px;
  font-size: clamp(72px, 8vw, 112px);
  font-weight: 650;
  letter-spacing: -0.07em;
}

.total-card .stat-label {
  margin-top: 6px;
  color: rgba(255, 255, 255, 0.72);
}

.total-card .stat-detail {
  margin-top: 12px;
  color: rgba(255, 255, 255, 0.58);
}

.total-substats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 34px;
  padding-top: 22px;
  border-top: 1px solid rgba(255, 255, 255, 0.14);
}

.total-substats div {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.total-substats strong {
  font-family: var(--mono);
  font-size: 22px;
}

.total-substats span {
  color: rgba(255, 255, 255, 0.56);
  font-size: 11px;
}

.resource-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.resource-card {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 358px;
  padding: 26px;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 24px;
  color: var(--text);
  text-decoration: none;
  background: var(--raised);
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.resource-card::before {
  content: '';
  position: absolute;
  top: -74px;
  right: -72px;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  opacity: 0.65;
  filter: blur(4px);
}

.resource-rpa-card::before {
  background: radial-gradient(circle, rgba(227, 170, 94, 0.34), rgba(227, 170, 94, 0));
}

.resource-skill-card::before {
  background: radial-gradient(circle, rgba(110, 123, 217, 0.32), rgba(110, 123, 217, 0));
}

.resource-python-card::before {
  background: radial-gradient(circle, rgba(74, 158, 168, 0.32), rgba(74, 158, 168, 0));
}

.resource-card:hover {
  transform: translateY(-4px);
  border-color: #d3d3cc;
  box-shadow: 0 18px 36px rgba(20, 20, 19, 0.07);
}

.resource-card-head {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.resource-arrow {
  font-size: 19px;
  transition: transform 0.2s ease;
}

.resource-card:hover .resource-arrow {
  transform: translate(3px, -3px);
}

.resource-count {
  position: relative;
  margin-top: 54px;
  font-family: var(--mono);
  font-size: clamp(44px, 4vw, 66px);
  font-weight: 650;
  line-height: 1;
  letter-spacing: -0.05em;
}

.resource-unit {
  margin-top: 10px;
  color: #49494b;
  font-size: 13px;
}

.resource-card p {
  margin: auto 0 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.65;
}

.status-panel {
  margin-top: 16px;
  padding: 22px 26px 24px;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: var(--raised);
}

.status-panel-title {
  padding-bottom: 18px;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
  font-weight: 650;
}

.status-panel-title span:last-child {
  color: var(--muted);
  font-size: 11px;
  font-weight: 400;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0;
  padding-top: 20px;
}

.status-item {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 8px 10px;
  padding: 3px 20px;
  border-left: 1px solid var(--line);
}

.status-item:first-child {
  padding-left: 0;
  border-left: 0;
}

.status-item > span:not(.status-dot) {
  color: var(--muted);
  font-size: 12px;
}

.status-item strong {
  grid-column: 2;
  font-family: var(--mono);
  font-size: 25px;
  font-weight: 620;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.dot-amber { background: #c98b12; }
.dot-blue { background: #3182b9; }
.dot-violet { background: #6e7bd9; }
.dot-gray { background: #8b8b87; }
.dot-green { background: #2c9a65; }

.progress-overview {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.progress-card {
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--raised);
}

.progress-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-height: 42px;
  color: #4f4f50;
  font-size: 12px;
  line-height: 1.4;
}

.progress-card-top strong {
  color: var(--text);
  font-family: var(--mono);
  font-size: 26px;
  line-height: 1;
}

.progress-mini-track {
  height: 4px;
  margin: 17px 0 13px;
  overflow: hidden;
  border-radius: 999px;
  background: #ededE8;
}

.progress-mini-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #141413;
}

.progress-card small {
  display: block;
  overflow: hidden;
  color: var(--muted);
  font-family: var(--mono);
  font-size: 9px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-directory {
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 22px;
  background: var(--raised);
}

.directory-heading {
  min-height: 58px;
  padding: 0 22px;
  color: var(--text);
  font-size: 13px;
  font-weight: 650;
}

.directory-heading span:last-child {
  color: var(--muted);
  font-size: 11px;
  font-weight: 400;
}

.progress-group {
  border-top: 1px solid var(--line);
}

.progress-group-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  min-height: 72px;
  padding: 0 22px;
  list-style: none;
  cursor: pointer;
  transition: background 0.18s ease;
}

.progress-group-summary::-webkit-details-marker {
  display: none;
}

.progress-group-summary:hover {
  background: #fafaf7;
}

.progress-group-name,
.progress-group-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-group-name {
  font-size: 14px;
  font-weight: 650;
}

.progress-group-meta {
  color: var(--muted);
  font-size: 12px;
}

.progress-group .group-chevron {
  width: 8px;
  height: 8px;
  border-right: 2px solid var(--muted);
  border-bottom: 2px solid var(--muted);
  transform: rotate(-45deg);
}

.progress-group[open] .group-chevron {
  transform: rotate(45deg);
}

.progress-group-body {
  padding: 0 16px 16px;
  border-top: 1px solid var(--line);
  background: #fafaf7;
}

.progress-group-body > .dept-card:first-of-type {
  margin-top: 14px;
}

.dept-card {
  margin-bottom: 8px;
  border-color: #e4e4de;
  box-shadow: none;
}

.dept-head {
  min-height: 54px;
  padding: 13px 16px;
}

.dept-body {
  padding: 0 16px 12px;
}

.project-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) auto auto minmax(150px, 260px) 48px;
  gap: 12px;
}

.bar-track {
  width: 100%;
  min-width: 0;
}

.st-amber {
  color: #925f00;
}

.requirement-overview {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  align-items: stretch;
  gap: 12px;
  margin-bottom: 16px;
}

.requirement-overview > div,
.requirement-cta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 86px;
  padding: 18px 22px;
  border: 1px solid var(--line);
  border-radius: 18px;
  color: var(--text);
  background: var(--raised);
  text-decoration: none;
}

.requirement-overview span {
  color: var(--muted);
  font-size: 13px;
}

.requirement-overview strong {
  font-family: var(--mono);
  font-size: 28px;
}

.requirement-cta {
  min-width: 220px;
  color: #f8f8f5;
  background: #141413;
  transition: transform 0.18s ease, background 0.18s ease;
}

.requirement-cta span {
  color: inherit;
  font-size: 18px;
}

.requirement-cta:hover {
  background: #30302e;
  transform: translateY(-2px);
}

.requirement-group,
.table-wrap {
  border-radius: 18px;
}

.requirement-group-summary {
  min-height: 64px;
  padding: 0 22px;
}

.footer {
  justify-content: space-between;
  margin-top: 108px;
  padding-top: 24px;
}

.footer-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text);
  font-weight: 650;
}

@media (prefers-reduced-motion: reduce) {
  .hero {
    animation: none;
  }
}

@media (max-width: 1100px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .total-card {
    min-height: 320px;
  }

  .resource-card {
    min-height: 290px;
  }

  .resource-count {
    margin-top: 38px;
  }

  .progress-overview {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .nav-inner {
    position: relative;
    height: 72px;
  }

  .nav-links {
    position: absolute;
    top: 72px;
    right: 0;
    left: 0;
    display: flex;
    gap: 4px;
    height: 48px;
    margin: 0;
    padding: 6px 20px;
    overflow-x: auto;
    border-bottom: 1px solid var(--line);
    background: rgba(255, 255, 253, 0.94);
    scrollbar-width: none;
  }

  .nav-links::-webkit-scrollbar {
    display: none;
  }

  .nav-link {
    flex: 0 0 auto;
  }

  .hero {
    min-height: 520px;
    padding-top: 0;
  }

  .hero-copy-centered {
    width: 100%;
    padding: 0 20px;
  }

  .hero-data-line {
    right: 24px;
    left: 24px;
  }

  .section-heading {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .section-description {
    max-width: 620px;
  }

  .status-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    row-gap: 22px;
  }

  .status-item:nth-child(4) {
    padding-left: 0;
    border-left: 0;
  }

  .project-row {
    grid-template-columns: minmax(150px, 1fr) auto auto minmax(120px, 180px) 44px;
  }
}

@media (max-width: 720px) {
  .nav-login {
    display: none;
  }

  .hero {
    min-height: 520px;
  }

  .hero-canvas {
    opacity: 1;
  }

  .sphere-name {
    display: flex;
    font-size: 12px;
    opacity: 1;
  }

  .sphere-count {
    font-size: 16px;
  }

  .hero-copy-centered {
    padding: 0 20px;
  }

  .hero-eyebrow {
    margin-bottom: 24px;
    font-size: 12px;
  }

  .hero-title {
    font-size: clamp(38px, 5.4vw, 62px);
  }

  .hero-sub {
    max-width: 32em;
    font-size: 17px;
  }

  .hero-data-caption,
  .hero-data-item {
    padding: 0 14px;
  }

  .hero-data-item:not(:nth-of-type(2)) {
    display: none;
  }

  .content {
    width: min(calc(100% - 32px), 1280px);
  }

  .section {
    margin-top: 82px;
  }

  .overview-section {
    margin-top: 72px;
  }

  .resource-grid {
    grid-template-columns: 1fr;
  }

  .resource-card {
    min-height: 210px;
  }

  .resource-count {
    margin-top: 28px;
  }

  .status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .status-item,
  .status-item:nth-child(4) {
    padding: 3px 16px;
    border-left: 1px solid var(--line);
  }

  .status-item:nth-child(odd) {
    padding-left: 0;
    border-left: 0;
  }

  .progress-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .progress-group-summary {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
    padding: 16px 18px;
  }

  .progress-group-meta {
    padding-left: 20px;
  }

  .project-row {
    grid-template-columns: auto auto minmax(0, 1fr) 44px;
    gap: 10px;
  }

  .project-name {
    grid-column: 1 / -1;
    white-space: normal;
  }

  .bar-track {
    grid-column: 1 / 4;
  }

  .bar-num {
    grid-column: 4;
  }

  .requirement-overview {
    grid-template-columns: 1fr 1fr;
  }

  .requirement-cta {
    grid-column: 1 / -1;
    min-width: 0;
  }
}

@media (max-width: 480px) {
  .nav-inner {
    padding: 0 14px;
  }

  .nav-actions .btn {
    min-height: 44px;
    padding: 8px 13px;
  }

  .hero-title {
    font-size: clamp(34px, 10vw, 42px);
  }

  .hero-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    width: 100%;
  }

  .hero-actions .btn {
    min-height: 48px;
    padding: 10px 12px;
    font-size: 13px;
    white-space: normal;
  }

  .hero-data-line {
    right: 16px;
    left: 16px;
  }

  .hero-data-jump {
    font-size: 12px;
  }

  .section-title {
    font-size: 34px;
  }

  .total-card {
    min-height: 0;
    padding: 26px;
  }

  .total-card .stat-num {
    font-size: 74px;
  }

  .total-substats strong {
    font-size: 18px;
  }

  .status-panel-title,
  .directory-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 5px;
  }

  .status-grid {
    grid-template-columns: 1fr;
  }

  .status-item,
  .status-item:nth-child(4),
  .status-item:nth-child(odd) {
    padding: 10px 0;
    border-top: 1px solid var(--line);
    border-left: 0;
  }

  .status-item:first-child {
    border-top: 0;
  }

  .progress-overview {
    grid-template-columns: 1fr;
  }

  .category-types {
    display: none;
  }

  .requirement-overview {
    grid-template-columns: 1fr;
  }

  .requirement-cta {
    grid-column: auto;
  }

  .footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
