// 登录页"记住账号和密码"的本机存储：按账号名分别保存，
// 同一台电脑上多个账号各记各的密码，输对账号名即自动带出。
//
// 安全说明：密码经 base64 编码放在浏览器 localStorage，只是避免直视明文，
// 并不是加密——任何能打开这台浏览器的人都能用它登录。后端即使改为
// 哈希保存也无法保护浏览器里这份副本；若后续接入统一认证，此功能应
// 同步改造或下线。用户找回密码成功后会清除用户端与管理端记住的旧密码。

const STORAGE_KEYS = {
  user: 'remembered_accounts_user',
  admin: 'remembered_accounts_admin',
}

function load(scope) {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS[scope]) || '{}')
  } catch {
    return {}
  }
}

function persist(scope, map) {
  localStorage.setItem(STORAGE_KEYS[scope], JSON.stringify(map))
}

// btoa/atob 只支持单字节字符，先过 TextEncoder 以兼容中文等多字节密码
const encode = (s) => btoa(String.fromCharCode(...new TextEncoder().encode(s)))
const decode = (s) => new TextDecoder().decode(Uint8Array.from(atob(s), (c) => c.charCodeAt(0)))

/** 查询某账号保存过的密码；没有或解码失败返回空串 */
export function getSavedPassword(scope, account) {
  const entry = load(scope)[account]
  if (!entry) return ''
  try {
    return decode(entry)
  } catch {
    return ''
  }
}

/** 保存/更新某账号的密码（登录成功且勾选"记住"时调用） */
export function saveAccount(scope, account, password) {
  if (!account || !password) return
  const map = load(scope)
  map[account] = encode(password)
  persist(scope, map)
}

/** 删除某账号的记忆（登录成功但未勾选"记住"时调用，视为用户主动取消） */
export function removeAccount(scope, account) {
  const map = load(scope)
  if (account in map) {
    delete map[account]
    persist(scope, map)
  }
}
