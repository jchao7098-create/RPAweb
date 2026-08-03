import http from './http'

// 员工代码资产（Skill 文件 / Python 插件）接口。
//
// 与后端的约定（后端待实现）：
//   POST /user/assets
//     multipart/form-data 字段：
//       user_id     提交人 id
//       asset_type  'skill' | 'python_plugin'
//       name        资产名称
//       department  部门名称
//       submitter   提交人姓名
//       version     版本号
//       description 说明
//       file_name   文件名称（当前仅登记名称，不传输文件内容）
//     返回：{ message: string }
//
//   GET /user/assets?user_id=&asset_type=
//     返回：{ data: [{ id, name, version, description, department, submitter,
//                      file_name, file_size, status, created_at }] }
//     status 是审核状态：待审核 / 已通过 / 已拒绝
//     lifecycle_status 是生命周期：在编 / 使用 / 大修 / 停用
//
//   PATCH /user/assets/:id
//     用户修改本人提交的信息；保存后统一回到待审核，拒绝理由清空，
//     已通过资产暂时退出公开看板，进度和生命周期由管理员重新确认。
//
//   GET /public/assets?asset_type=
//     公开看板用，返回结构同上。注意：这是匿名可访问的接口，
//     后端不要在这里返回文件下载地址或存储路径，避免未审核内容被直接拿到。

export function submitAsset({
  userId,
  assetType,
  name,
  department,
  submitter,
  version,
  description,
  fileName,
}) {
  const formData = new FormData()
  formData.append('user_id', userId)
  formData.append('asset_type', assetType)
  formData.append('name', name)
  formData.append('department', department)
  formData.append('submitter', submitter)
  formData.append('version', version)
  formData.append('description', description)
  formData.append('file_name', fileName)
  return http.post('/user/assets', formData)
}

export function fetchMyAssets({ userId, assetType }) {
  return http.get('/user/assets', {
    params: { user_id: userId, asset_type: assetType },
  })
}

export function updateMyAsset({
  id,
  userId,
  name,
  department,
  submitter,
  version,
  description,
  fileName,
}) {
  return http.patch(`/user/assets/${id}`, {
    user_id: userId,
    name,
    department,
    submitter,
    version,
    description,
    file_name: fileName,
  })
}

export function fetchPublicAssets({ assetType }) {
  return http.get('/public/assets', {
    params: { asset_type: assetType },
  })
}

// ===== 管理员：资产审核 =====

export function fetchAdminAssets({ assetType, status, scope, apiPrefix = '/admin' } = {}) {
  return http.get(`${apiPrefix}/assets`, {
    params: { asset_type: assetType, status, scope },
  })
}

export function approveAsset({ id, apiPrefix = '/admin' }) {
  return http.post(`${apiPrefix}/assets/approve`, { id })
}

export function rejectAsset({ id, reason, apiPrefix = '/admin' }) {
  return http.post(`${apiPrefix}/assets/reject`, { id, reason })
}

export function updateAssetProgress({
  id,
  progress,
  lifecycleStatus,
  apiPrefix = '/admin',
}) {
  return http.post(`${apiPrefix}/assets/progress`, {
    id,
    progress,
    lifecycle_status: lifecycleStatus,
  })
}
