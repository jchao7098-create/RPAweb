// 员工代码资产（Skill 文件 / Python 插件）的声明式配置。
// 页面组件 AssetSubmission.vue 按这里的配置渲染表单和校验规则，
// 以后要新增一类资产（比如 Bot 模板），在这里加一条记录、router 加一个路由即可。
// 资产审核状态对应的 el-tag 颜色，提交页和公开页共用
export const ASSET_STATUS_TAG_TYPES = {
  待审核: 'warning',
  已通过: 'success',
  已拒绝: 'danger',
}

export const ASSET_TYPES = {
  skill: {
    // 提交给后端的类型标识
    apiType: 'skill',
    label: 'Skill 文件',
    publicTitle: '各部门Skill情况',
    allowedExtensions: ['.md', '.txt', '.json', '.yaml', '.yml', '.zip'],
    maxSizeMB: 10,
    nameHint: '命名模板：部门-功能简介-skill，例如：客服部-工单自动分类-skill',
    descriptionHint:
      '请说明该 Skill 的用途、触发方式和使用前提；zip 包请在此列出包内文件清单',
  },
  pythonPlugin: {
    apiType: 'python_plugin',
    label: 'Python 插件',
    publicTitle: '各部门Python插件情况',
    allowedExtensions: ['.py', '.zip', '.whl'],
    maxSizeMB: 20,
    nameHint: '命名模板：部门-功能简介-插件，例如：运营部-报表数据清洗-插件',
    descriptionHint:
      '请说明插件功能、适用的 Python 版本、第三方依赖（requirements）以及入口函数/用法',
  },
}
