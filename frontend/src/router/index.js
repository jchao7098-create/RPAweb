import { createRouter, createWebHistory } from 'vue-router'
import { loadLearningProfile } from '@/api/learning'
import { canManageLearning, canViewLearningStats, canViewReport, getLearningToken } from '@/utils/learningSession'

// 首页是绝大多数访问的入口，保持同步引入以便随入口包立即可用；
// 其余页面一律路由级懒加载（vite 会按路由拆包），
// 新用户首次打开登录页时不再下载整站代码。
import PublicView from '../views/PublicView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'Public',
      component: PublicView
    },
    {
      path: '/department',
      name: 'department',
      component: () => import('../components/department/DepartmentSort.vue')
    },
    {
      path: '/department-skills',
      name: 'departmentSkills',
      component: () => import('../components/department/DepartmentAssets.vue'),
      props: { assetTypeId: 'skill' },
    },
    {
      path: '/department-plugins',
      name: 'departmentPlugins',
      component: () => import('../components/department/DepartmentAssets.vue'),
      props: { assetTypeId: 'pythonPlugin' },
    },
    // 登录/注册：用户端与管理员端共用同一组件，差异由 audience 属性驱动
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/LoginView.vue'),
      props: { audience: 'user' },
    },
    {
      path: '/register',
      name: 'Register',
      component: () => import('../views/RegisterView.vue'),
      props: { audience: 'user' },
    },
    {
      path: '/forgot-password',
      name: 'ForgotPassword',
      component: () => import('../views/ForgotPasswordView.vue'),
      props: { audience: 'user' },
    },
    {
      path: '/adminLogin',
      name: 'adminLogin',
      component: () => import('../views/LoginView.vue'),
      props: { audience: 'admin' },
    },
    {
      path: '/adminregister',
      name: 'adminRegister',
      component: () => import('../views/RegisterView.vue'),
      props: { audience: 'admin' },
    },
    {
      path: '/admin-forgot-password',
      name: 'adminForgotPassword',
      component: () => import('../views/ForgotPasswordView.vue'),
      props: { audience: 'admin' },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
      children: [
        {
          path: 'DevelopmentProgress',
          name: 'DevelopmentProgress',
          component: () => import('../components/admin/DevelopmentProgress.vue'),
        },
        {
          path: 'MaintenanceProgress',
          name: 'MaintenanceProgress',
          component: () => import('../components/admin/MaintenanceProgress.vue'),
        },
        {
          // 审核中心：RPA 程序需求 + Skill/插件资产合并在同一页（标签切换）
          path: 'Requirements',
          name: 'Requirements',
          component: () => import('../components/admin/Requirements.vue'),
        },
        {
          path: 'DataExport',
          name: 'DataExport',
          component: () => import('../components/admin/DataExport.vue'),
        },
        { path: 'LearningStats', name: 'LearningStats', component: () => import('../components/admin/LearningStats.vue'), meta: { learningAudience: 'stats' } },
        { path: 'RoleManagement', name: 'RoleManagement', component: () => import('../components/admin/RoleManagement.vue'), meta: { learningAudience: 'manage' } },
      ]
    },
    {
      path: '/main',
      name: 'main',
      component: () => import('../views/UserView.vue'),
      children: [
        {
          path: 'RpaProgress',
          name: 'RpaProgress',
          component: () => import('../components/user/RpaProgress.vue'),
        },
        {
          path: 'RpaRequirement',
          name: 'RpaRequirement',
          component: () => import('../components/user/RpaRequirement.vue'),
        },
        {
          path: 'RpaMaintance',
          name: 'RpaMaintance',
          component: () => import('../components/user/RpaMaintance.vue'),
        },
        {
          path: 'SkillUpload',
          name: 'SkillUpload',
          component: () => import('../components/user/AssetSubmission.vue'),
          props: { assetTypeId: 'skill' },
        },
        {
          path: 'PluginUpload',
          name: 'PluginUpload',
          component: () => import('../components/user/AssetSubmission.vue'),
          props: { assetTypeId: 'pythonPlugin' },
        },
        {
          path: 'RequirementReview',
          name: 'UserRequirementReview',
          component: () => import('../components/admin/Requirements.vue'),
          props: {
            apiPrefix: '/user/manage',
            selfService: true,
          },
        },
        {
          path: 'DevelopmentManagement',
          name: 'UserDevelopmentManagement',
          component: () => import('../components/admin/DevelopmentProgress.vue'),
          props: {
            apiPrefix: '/user/manage',
            selfService: true,
            readScope: 'all',
          },
        },
        {
          path: 'MaintenanceManagement',
          name: 'UserMaintenanceManagement',
          component: () => import('../components/admin/MaintenanceProgress.vue'),
          props: {
            apiPrefix: '/user/manage',
            selfService: true,
          },
        },
        {
          path: 'DataExport',
          name: 'UserDataExport',
          component: () => import('../components/admin/DataExport.vue'),
          props: {
            apiPrefix: '/user/manage',
            includeLearningExport: true,
          },
        },
        { path: 'LearningReport', name: 'LearningReport', component: () => import('../components/user/LearningReport.vue'), meta: { learningAudience: 'report' } },
      ]
    }
  ]
})

const capabilityChecks = {
  stats: canViewLearningStats,
  manage: canManageLearning,
  report: canViewReport,
}

router.beforeEach(async (to) => {
  const audience = to.meta.learningAudience
  if (!audience) return true
  const isAdminRoute = audience === 'stats' || audience === 'manage'
  const loginPath = isAdminRoute ? '/adminLogin' : '/login'
  const rootPath = isAdminRoute ? '/admin' : '/main'
  if (!getLearningToken()) return loginPath
  try {
    const profile = await loadLearningProfile({ force: true })
    return capabilityChecks[audience]?.(profile) ? true : rootPath
  } catch {
    return getLearningToken() ? rootPath : loginPath
  }
})

export default router
