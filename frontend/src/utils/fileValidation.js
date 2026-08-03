// 上传文件的前端校验。
// 注意：前端校验只是交互体验和第一道拦截，攻击者可以绕过浏览器直接调接口，
// 后端落地时必须重新做扩展名白名单、大小限制、内容扫描和存储路径隔离。

const FILENAME_MAX_LENGTH = 100

// 路径分隔符、Windows 保留字符、控制字符和 ".."，防止文件名被用来做路径穿越
const UNSAFE_FILENAME_PATTERN = new RegExp('[\\\\/:*?"<>|\\u0000-\\u001f]|\\.\\.')

export function getExtension(filename) {
  const idx = filename.lastIndexOf('.')
  return idx === -1 ? '' : filename.slice(idx).toLowerCase()
}

/**
 * 校验仅用于登记的文件名，不读取或上传文件内容。
 * @param {string} filename
 * @param {{ allowedExtensions: string[] }} rules
 * @returns {string|null}
 */
export function validateFileName(filename, { allowedExtensions }) {
  if (!filename) {
    return '请输入文件名称'
  }
  if (filename.length > FILENAME_MAX_LENGTH) {
    return `文件名过长（最多 ${FILENAME_MAX_LENGTH} 个字符），请重命名后再提交`
  }
  if (UNSAFE_FILENAME_PATTERN.test(filename)) {
    return '文件名包含非法字符（如 / \\ : * ? " < > | 或 ..），请重命名后再提交'
  }
  if (!allowedExtensions.includes(getExtension(filename))) {
    return `仅支持 ${allowedExtensions.join(' / ')} 格式`
  }
  return null
}

/**
 * 校验文件是否符合给定资产类型的限制。
 * @param {File} file
 * @param {{ allowedExtensions: string[], maxSizeMB: number }} rules
 * @returns {string|null} 不通过时返回展示给用户的错误信息，通过时返回 null
 */
export function validateFile(file, { allowedExtensions, maxSizeMB }) {
  if (!file || !file.name) {
    return '文件无效'
  }
  const filenameError = validateFileName(file.name, { allowedExtensions })
  if (filenameError) return filenameError.replace(/提交/g, '上传')
  if (file.size === 0) {
    return '文件内容为空'
  }
  if (file.size > maxSizeMB * 1024 * 1024) {
    return `文件大小不能超过 ${maxSizeMB}MB`
  }
  return null
}
