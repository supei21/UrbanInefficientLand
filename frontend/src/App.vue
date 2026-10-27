<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  BookOpen,
  CircleHelp,
  Database,
  Map,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  SquarePen,
} from "lucide-vue-next";

import { useWorkspace } from "./composables/useWorkspace";
import StreamingChat from "./modules/chat/StreamingChat.vue";
import DataPanel from "./modules/data/DataPanel.vue";
import PolicyLibrary from "./modules/policy/PolicyLibrary.vue";
import RegenerationWorkbench from "./modules/regeneration/RegenerationWorkbench.vue";

type ModuleName = "assistant" | "regeneration" | "policy" | "data";

const activeModule = ref<ModuleName>("assistant");
const sidebarCollapsed = ref(false);
const searchOpen = ref(false);
const searchQuery = ref("");
const chatKey = ref(0);
const conversationTitle = ref("新对话");
const { summary, error, refresh, replace } = useWorkspace();

const moduleMeta = computed(() => {
  if (activeModule.value === "regeneration") {
    return { eyebrow: "SPATIAL ANALYSIS", title: "低效空间识别与场景策划" };
  }
  if (activeModule.value === "policy") {
    return { eyebrow: "POLICY KNOWLEDGE BASE", title: "城市更新政策库" };
  }
  return { eyebrow: "DATA WORKSPACE", title: "分析数据管理" };
});

const recentConversations = computed(() => {
  const items = [conversationTitle.value];
  const query = searchQuery.value.trim().toLowerCase();
  return query ? items.filter((item) => item.toLowerCase().includes(query)) : items;
});

function startNewChat() {
  activeModule.value = "assistant";
  conversationTitle.value = "新对话";
  chatKey.value += 1;
}

function updateConversationTitle(prompt: string) {
  if (conversationTitle.value !== "新对话") return;
  conversationTitle.value = prompt.length > 22 ? `${prompt.slice(0, 22)}…` : prompt;
}

onMounted(refresh);
</script>

<template>
  <div :class="['chatgpt-shell', { 'sidebar-collapsed': sidebarCollapsed }]">
    <aside class="chatgpt-sidebar">
      <div class="sidebar-brand-row">
        <button
          class="brand-button"
          type="button"
          title="返回对话"
          @click="activeModule = 'assistant'"
        >
          <span class="brand-symbol">枢</span>
          <span class="brand-name">天枢城市再生</span>
        </button>
        <button
          class="sidebar-collapse-button"
          type="button"
          :title="sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
          @click="sidebarCollapsed = !sidebarCollapsed"
        >
          <PanelLeftOpen v-if="sidebarCollapsed" :size="19" />
          <PanelLeftClose v-else :size="19" />
        </button>
      </div>

      <nav class="sidebar-actions" aria-label="主要功能">
        <button
          :class="{ active: activeModule === 'assistant' }"
          aria-label="对话"
          title="对话"
          @click="activeModule = 'assistant'"
        >
          <MessageSquareText :size="18" /><span>对话</span>
        </button>
        <button aria-label="新建对话" title="新建对话" @click="startNewChat">
          <SquarePen :size="18" /><span>新建对话</span>
        </button>
        <button aria-label="搜索" title="搜索" @click="searchOpen = !searchOpen">
          <Search :size="18" /><span>搜索</span>
        </button>
        <button
          :class="{ active: activeModule === 'regeneration' }"
          aria-label="空间分析"
          title="空间分析"
          @click="activeModule = 'regeneration'"
        >
          <Map :size="18" /><span>空间分析</span>
        </button>
        <button
          :class="{ active: activeModule === 'policy' }"
          aria-label="政策库"
          title="政策库"
          @click="activeModule = 'policy'"
        >
          <BookOpen :size="18" /><span>政策库</span>
        </button>
        <button
          :class="{ active: activeModule === 'data' }"
          aria-label="数据管理"
          title="数据管理"
          @click="activeModule = 'data'"
        >
          <Database :size="18" /><span>数据管理</span>
        </button>
      </nav>

      <div v-if="searchOpen" class="sidebar-search">
        <Search :size="15" />
        <input v-model="searchQuery" autofocus aria-label="搜索会话" placeholder="搜索会话" />
      </div>

      <div class="conversation-list">
        <div class="sidebar-section-label">最近</div>
        <button
          v-for="title in recentConversations"
          :key="title"
          :class="{ active: activeModule === 'assistant' }"
          @click="activeModule = 'assistant'"
        >
          <span>{{ title }}</span>
        </button>
        <p v-if="!recentConversations.length">没有匹配的会话</p>
      </div>

      <div class="sidebar-service-card">
        <span :class="['service-dot', { online: Boolean(summary) }]"></span>
        <div>
          <strong>{{ summary ? "分析服务已连接" : "正在连接服务" }}</strong>
          <small>{{ summary?.block_count ?? 0 }} 个空间单元</small>
        </div>
      </div>
    </aside>

    <main class="chatgpt-main">
      <div v-if="error" class="global-error chatgpt-global-error">
        {{ error }} <button @click="refresh">重试</button>
      </div>

      <StreamingChat
        v-if="activeModule === 'assistant'"
        :key="chatKey"
        :summary="summary"
        @prompt="updateConversationTitle"
        @workspace-changed="replace"
      />

      <template v-else>
        <header class="workspace-topbar">
          <button class="mobile-sidebar-toggle" @click="sidebarCollapsed = !sidebarCollapsed">
            <PanelLeftOpen :size="19" />
          </button>
          <div>
            <span>{{ moduleMeta.eyebrow }}</span>
            <h1>{{ moduleMeta.title }}</h1>
          </div>
          <a href="/api/health" target="_blank"><CircleHelp :size="16" />服务状态</a>
        </header>
        <section class="workspace-content">
          <RegenerationWorkbench v-if="activeModule === 'regeneration'" />
          <PolicyLibrary
            v-else-if="activeModule === 'policy'"
            :models="summary?.models ?? []"
            :default-model-id="summary?.default_model_id"
          />
          <div v-else class="data-workspace-page">
            <div class="data-workspace-intro">
              <span>DATA WORKSPACE</span>
              <h2>准备城市空间分析数据</h2>
              <p>导入 JSON、CSV 或 ZIP 数据集，系统会自动识别指标字段与空间几何。</p>
            </div>
            <DataPanel :summary="summary" @changed="replace" />
          </div>
        </section>
      </template>
    </main>
  </div>
</template>
