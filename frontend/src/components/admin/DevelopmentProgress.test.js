// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DevelopmentProgress from './DevelopmentProgress.vue'

const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
const assetApi = vi.hoisted(() => ({
  fetchAdminAssets: vi.fn(),
  updateAssetProgress: vi.fn(),
}))
vi.mock('@/api/http', () => ({ default: http }))
vi.mock('@/api/assets', () => assetApi)

const project = {
  id: 1,
  name: '客服部-日报',
  progress: 50,
  status: '在编',
  logs: [],
  is_owned: false,
  can_edit: false,
}
const asset = {
  id: 8,
  asset_type: 'skill',
  name: '日报 Skill',
  department: '客服部',
  submitter: '员工',
  status: '已通过',
  progress: 20,
  lifecycle_status: '停用',
  is_owned: false,
  can_edit: false,
}
const pythonAsset = {
  ...asset,
  id: 10,
  asset_type: 'python_plugin',
  name: '数据清洗插件',
  department: '项目部',
  lifecycle_status: '使用',
}

describe('DevelopmentProgress unified lifecycle management', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    http.get.mockResolvedValue({
      data: {
        data: [
          project,
          { ...project, id: 2, status: '大修', progress: 100, is_owned: true, can_edit: true },
        ],
      },
    })
    http.post.mockResolvedValue({
      data: { success: true, progress: 50, status: '大修' },
    })
    assetApi.fetchAdminAssets.mockResolvedValue({
      data: {
        data: [
          { ...asset, is_owned: true, can_edit: true },
          pythonAsset,
          { ...asset, id: 9, status: '已拒绝', lifecycle_status: '在编' },
        ],
      },
    })
    assetApi.updateAssetProgress.mockResolvedValue({
      data: { progress: 40, lifecycle_status: '停用' },
    })
  })

  it('includes approved Skill and Python assets in the total and four-state summary', async () => {
    const wrapper = mount(DevelopmentProgress)
    await flushPromises()

    const values = wrapper.findAll('.admin-stat-value').map((node) => node.text())
    expect(values).toEqual(['4', '1', '1', '1', '1'])
    const breakdowns = wrapper.findAll('.summary-breakdown').map((node) => node.text())
    expect(breakdowns).toEqual([
      'RPA 2Skill 1Python 1',
      'RPA 1Skill 0Python 0',
      'RPA 0Skill 0Python 1',
      'RPA 1Skill 0Python 0',
      'RPA 0Skill 1Python 0',
    ])
    expect(wrapper.text()).toContain('Skill 文件（1）')
    expect(wrapper.text()).toContain('Python 插件（1）')
  })

  it('searches the selected resource by name, department, status, or person', async () => {
    const wrapper = mount(DevelopmentProgress)
    await flushPromises()
    const state = wrapper.vm.$.setupState

    state.resourceTab = 'python_plugin'
    state.searchKeyword = '项目部'
    state.toggle('python_plugin', { name: '项目部', inDevelopment: 0 })
    await flushPromises()

    expect(wrapper.findAll('.proj-name').map((node) => node.text())).toEqual(['数据清洗插件'])

    state.searchKeyword = '不存在'
    await flushPromises()

    expect(wrapper.text()).toContain('没有匹配的Python 插件')
    expect(wrapper.findAll('.proj-name')).toHaveLength(0)
  })

  it('submits a manually selected RPA lifecycle status', async () => {
    const wrapper = mount(DevelopmentProgress)
    await flushPromises()
    const state = wrapper.vm.$.setupState
    state.openProjectDialog(project)
    state.newProjectStatus = '大修'
    state.newProgress = 50
    state.newRemark = '进入大修'

    await state.updateProjectProgress()

    expect(http.post).toHaveBeenCalledWith('/admin/update_progress', {
      project_id: 1,
      progress: 50,
      status: '大修',
      remark: '进入大修',
    })
  })

  it('updates Skill progress and lifecycle independently from review status', async () => {
    const wrapper = mount(DevelopmentProgress)
    await flushPromises()
    const state = wrapper.vm.$.setupState
    state.openAssetDialog(asset)
    state.assetStatusMode = 'manual'
    state.newAssetStatus = '停用'
    state.newAssetProgress = 40

    await state.updateAsset()

    expect(assetApi.updateAssetProgress).toHaveBeenCalledWith({
      id: 8,
      progress: 40,
      lifecycleStatus: '停用',
      apiPrefix: '/admin',
    })
  })

  it('requests all development resources for the user workbench read view', async () => {
    const wrapper = mount(DevelopmentProgress, {
      props: { apiPrefix: '/user/manage', selfService: true, readScope: 'all' },
    })
    await flushPromises()

    expect(wrapper.find('.admin-page-sub').text()).toBe(
      '查看全平台进度；普通用户仅可更新本人上传内容，管理员可更新全部'
    )
    expect(http.get).toHaveBeenCalledWith('/user/manage/get_projects', {
      params: { scope: 'all' },
    })
    expect(assetApi.fetchAdminAssets).toHaveBeenCalledWith({
      apiPrefix: '/user/manage',
      scope: 'all',
    })

    const rpaUpdateButtons = wrapper.findAll('.btn-mini').filter((button) => button.text() === '更新')
    expect(rpaUpdateButtons).toHaveLength(1)
    const state = wrapper.vm.$.setupState
    state.openProjectDialog(project)
    expect(state.projectDialogVisible).toBe(false)
    await rpaUpdateButtons[0].trigger('click')
    expect(state.projectDialogVisible).toBe(true)
    state.newProjectStatus = '大修'
    state.newProgress = 55
    state.newRemark = '工作台协作更新'
    await state.updateProjectProgress()
    expect(http.post).toHaveBeenCalledWith('/user/manage/update_progress', {
      project_id: 2,
      progress: 55,
      status: '大修',
      remark: '工作台协作更新',
    })

    state.resourceTab = 'skill'
    state.toggle('skill', { name: '客服部', inDevelopment: 0 })
    await flushPromises()

    const assetUpdateButton = wrapper.findAll('.btn-mini').find((button) => button.text() === '更新')
    expect(assetUpdateButton).toBeTruthy()
    await assetUpdateButton.trigger('click')
    expect(state.assetDialogVisible).toBe(true)
    state.assetStatusMode = 'manual'
    state.newAssetStatus = '大修'
    state.newAssetProgress = 60
    await state.updateAsset()
    expect(assetApi.updateAssetProgress).toHaveBeenCalledWith({
      id: 8,
      progress: 60,
      lifecycleStatus: '大修',
      apiPrefix: '/user/manage',
    })
  })
})
