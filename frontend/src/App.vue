<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>

    <!-- 登录页面的内容 -->
    <div id='building'>
    <!-- 顶层路由过渡：key 取顶层路由记录，子路由切换时不触发外层动画；
         同组件不同 props 的路由（如 /department-skills 与 /department-plugins）靠 key 重新挂载以播放过渡 -->
    <RouterView v-slot="{ Component }">
      <Transition name="page" mode="out-in">
        <component :is="Component" :key="$route.matched[0]?.path" />
      </Transition>
    </RouterView>

  </div>
</template>

<style scoped>


</style>
