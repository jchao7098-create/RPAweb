import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'



// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需引入：模板里的 el-* 组件与 ElMessage/ElMessageBox 等命令式 API
    // 由编译期自动注入（含对应样式），不再全量打包整个组件库；
    // 组件代码里不要再手写 `import { ElMessage } from 'element-plus'`，交给 AutoImport。
    AutoImport({
      resolvers: [ElementPlusResolver()],
      dts: false,
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: false,
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    // 只绑定本机，避免开发中的页面被局域网内其他人访问；
    // 需要对外演示时再临时改回 '0.0.0.0'
    host: 'localhost'
  },
  test: {
    // Element Plus 的命令式 API 会按需引入 CSS；测试时必须交给 Vite 转换，
    // 否则外部化后的 Node ESM 加载器无法读取 .css 文件。
    server: {
      deps: {
        inline: [/element-plus/],
      },
    },
  },
})
