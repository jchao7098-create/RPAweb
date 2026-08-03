import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

// 全局西文/数字字体（仅 latin 子集：页面是中文界面，西文只用于品牌词与数字）
import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-500.css'
import '@fontsource/inter/latin-600.css'
import '@fontsource/inter/latin-700.css'
import '@fontsource/inter/latin-800.css'

// 全站共享设计令牌（导航/按钮/状态章/表单），登录页与部门情况页复用这里的类
import './assets/theme.css'

// Element Plus 不再全量引入：组件与样式由 vite.config.js 里的
// unplugin（AutoImport + Components + ElementPlusResolver）按需注入。
// ECharts 此前全局注册但全站无一处使用，依赖已整体移除；
// 将来要加图表时先 npm install echarts vue-echarts，再在用到的组件里局部引入。

const app = createApp(App)

app.use(router)

app.mount('#app')
