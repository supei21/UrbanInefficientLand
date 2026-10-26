<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  Bot,
  ChartNoAxesCombined,
  CircleHelp,
  Database,
  Layers3,
  MapPinned,
  Sparkles,
} from "lucide-vue-next";

import { useWorkspace } from "./composables/useWorkspace";
import StreamingChat from "./modules/chat/StreamingChat.vue";
import DataPanel from "./modules/data/DataPanel.vue";
import RegenerationWorkbench from "./modules/regeneration/RegenerationWorkbench.vue";

const activeModule = ref<"regeneration" | "assistant">("regeneration");
const { summary, error, refresh, replace } = useWorkspace();

onMounted(refresh);
</script>

<template>
  <div class="gis-shell">
    <aside class="gis-left-sidebar">
      <div class="gis-brand">
        <div class="gis-brand-mark"><MapPinned :size="20" /></div>
        <div><strong>天枢·城市再生</strong><span>URBAN REGENERATION</span></div>
      </div>
      <div class="gis-sidebar-scroll">
        <nav class="primary-nav" aria-label="系统功能">
          <button
            aria-label="再生分析"
            :class="{ active: activeModule === 'regeneration' }"
            @click="activeModule = 'regeneration'"
          >
            <ChartNoAxesCombined :size="19" /><span>再生分析</span>
          </button>
          <button
            aria-label="智能助手"
            :class="{ active: activeModule === 'assistant' }"
            @click="activeModule = 'assistant'"
          >
            <Bot :size="19" /><span>智能助手</span>
          </button>
        </nav>
        <DataPanel :summary="summary" @changed="replace" />
        <div class="architecture-note">
          <Layers3 :size="18" />
          <div><b>分析框架</b><span>活力 · 功能 · 品质 · 可达性</span></div>
        </div>
        <a class="help-link" href="/api/health" target="_blank"
          ><CircleHelp :size="15" /> API 服务状态</a
        >
      </div>
      <div class="gis-sidebar-footer">
        <span :class="['service-dot', { online: Boolean(summary) }]"></span>
        <div>
          <b>{{ summary ? "Flask 服务已连接" : "正在连接服务" }}</b
          ><small>Vue 3 · Python 3.11</small>
        </div>
      </div>
    </aside>

    <section class="gis-main-stage">
      <header class="gis-topbar">
        <div class="gis-page-title">
          <span class="eyebrow">TIANSHU CUP · 2026</span>
          <h1>
            {{ activeModule === "regeneration" ? "低效空间识别与场景策划" : "城市再生智能助手" }}
          </h1>
        </div>
        <div class="gis-topbar-meta">
          <span><Database :size="14" />{{ summary?.block_count ?? 0 }} 个空间单元</span>
          <span><Layers3 :size="14" />{{ summary?.field_count ?? 0 }} 个指标字段</span>
          <span><Sparkles :size="14" />五类再生场景</span>
        </div>
      </header>
      <div v-if="error" class="global-error">
        {{ error }} <button @click="refresh">重试</button>
      </div>
      <main class="gis-module-host">
        <RegenerationWorkbench v-if="activeModule === 'regeneration'" />
        <StreamingChat v-else :summary="summary" />
      </main>
    </section>
  </div>
</template>
