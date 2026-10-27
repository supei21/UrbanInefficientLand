<script setup lang="ts">
import {
  ArrowUp,
  Bot,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  Paperclip,
  Plus,
  Sparkles,
  UserRound,
} from "lucide-vue-next";
import { computed, nextTick, ref, watch } from "vue";

import { streamChat } from "../../api/workspace";
import type { ChatPacket, ChatProcessEvent, WorkspaceSummary } from "../../types/domain";
import ModelSettingsDialog from "./ModelSettingsDialog.vue";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  events?: ChatProcessEvent[];
  pending?: boolean;
  error?: boolean;
  modelName?: string;
}

const props = defineProps<{ summary: WorkspaceSummary | null }>();
const emit = defineEmits<{
  prompt: [text: string];
  workspaceChanged: [summary: WorkspaceSummary];
}>();
const draft = ref("");
const busy = ref(false);
const selectedModel = ref("");
const modelDialogOpen = ref(false);
const modelNotice = ref("");
const conversation = ref<HTMLDivElement | null>(null);
const messages = ref<ChatMessage[]>([]);

const quickPrompts = [
  { title: "识别低效空间", detail: "找出最优先的更新片区" },
  { title: "策划再生场景", detail: "生成差异化更新策略" },
  { title: "形成行动建议", detail: "结合政策安排实施路径" },
];
const modelId = computed(
  () => selectedModel.value || props.summary?.default_model_id || "local-rules",
);
const activeModel = computed(() =>
  props.summary?.models.find((model) => model.id === modelId.value),
);
const hasMessages = computed(() => messages.value.length > 0);

function updateMessage(id: string, update: (message: ChatMessage) => ChatMessage) {
  messages.value = messages.value.map((message) => (message.id === id ? update(message) : message));
}

function normalizeEvent(events: ChatProcessEvent[], event: ChatProcessEvent): ChatProcessEvent[] {
  return [
    ...events.map((item) =>
      item.status === "running" ? { ...item, status: "completed" as const } : item,
    ),
    event,
  ];
}

async function send(prompt = draft.value) {
  const query = prompt.trim();
  if (!query || busy.value || !props.summary?.block_count) return;
  draft.value = "";
  busy.value = true;
  emit("prompt", query);
  const assistantId = crypto.randomUUID();
  messages.value.push(
    { id: crypto.randomUUID(), role: "user", content: query },
    { id: assistantId, role: "assistant", content: "", events: [], pending: true },
  );
  try {
    await streamChat(query, modelId.value, (packet: ChatPacket) => {
      if (packet.type === "process") {
        updateMessage(assistantId, (message) => ({
          ...message,
          events: normalizeEvent(message.events ?? [], packet.event),
        }));
      } else if (packet.type === "landscape_progress") {
        updateMessage(assistantId, (message) => ({
          ...message,
          events: normalizeEvent(message.events ?? [], {
            phase: "landscape",
            title: "景观格局计算",
            detail: packet.progress.message,
            status: packet.progress.percent === 100 ? "completed" : "running",
          }),
        }));
      } else if (packet.type === "answer_delta") {
        updateMessage(assistantId, (message) => ({
          ...message,
          content: message.content + packet.content,
        }));
      } else if (packet.type === "result") {
        updateMessage(assistantId, (message) => ({
          ...message,
          content: message.content || packet.result.response || "分析完成。",
          modelName: packet.result.model_name,
          pending: false,
          events: (message.events ?? []).map((event) =>
            event.status === "running" ? { ...event, status: "completed" as const } : event,
          ),
        }));
      } else if (packet.type === "error") {
        throw new Error(packet.message);
      }
    });
  } catch (reason) {
    const detail = reason instanceof Error ? reason.message : "智能分析失败";
    updateMessage(assistantId, (message) => ({
      ...message,
      content: message.content || detail,
      pending: false,
      error: true,
      events: (message.events ?? []).map((event) =>
        event.status === "running" ? { ...event, status: "error" as const } : event,
      ),
    }));
  } finally {
    busy.value = false;
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    void send();
  }
}

function handleModelCreated(workspace: WorkspaceSummary, modelId: string) {
  emit("workspaceChanged", workspace);
  selectedModel.value = modelId;
  modelDialogOpen.value = false;
  modelNotice.value = "模型已添加并选中";
}

function handleModelRemoved(workspace: WorkspaceSummary, modelId: string) {
  emit("workspaceChanged", workspace);
  if (selectedModel.value === modelId) selectedModel.value = "";
  modelNotice.value = "自定义模型已删除";
}

watch(
  messages,
  async () => {
    await nextTick();
    conversation.value?.scrollTo({ top: conversation.value.scrollHeight, behavior: "smooth" });
  },
  { deep: true },
);
</script>

<template>
  <section :class="['stream-chat-panel', { empty: !hasMessages }]">
    <header class="stream-chat-header">
      <div class="chat-header-title">
        <span class="chat-agent-mark"><Sparkles :size="15" /></span>
        <div>
          <strong>城市再生智能体</strong>
          <span>{{ activeModel?.label || "正在读取模型" }}</span>
        </div>
      </div>
      <div class="stream-status"><i :class="{ busy }"></i>{{ busy ? "分析中" : "在线" }}</div>
    </header>

    <div ref="conversation" class="stream-chat-scroll">
      <div v-if="!hasMessages" class="chat-welcome">
        <div class="welcome-symbol"><Sparkles :size="24" /></div>
        <p>天枢 · 城市更新智能体</p>
        <h1>今天想从哪里开始？</h1>
        <span>识别城市低效空间，评估再生潜力，并生成可解释的场景策划方案。</span>
      </div>

      <div v-else class="stream-conversation">
        <article
          v-for="message in messages"
          :key="message.id"
          :class="['stream-message', message.role, { error: message.error }]"
        >
          <div class="stream-avatar">
            <UserRound v-if="message.role === 'user'" :size="15" />
            <Sparkles v-else :size="15" />
          </div>
          <div class="stream-message-body">
            <div class="stream-message-meta">
              <strong>{{ message.role === "user" ? "你" : "天枢" }}</strong>
              <span v-if="message.modelName">{{ message.modelName }}</span>
            </div>

            <div v-if="message.events?.length" class="stream-process-trace">
              <details open>
                <summary>
                  <Sparkles :size="13" />
                  <span>{{ message.pending ? "正在执行分析流程" : "已完成分析流程" }}</span>
                  <ChevronDown :size="13" />
                </summary>
                <div class="stream-process-list">
                  <div v-for="(event, index) in message.events" :key="`${event.title}-${index}`">
                    <span :class="['process-state', event.status || 'running']">
                      <CircleAlert
                        v-if="event.status === 'warning' || event.status === 'error'"
                        :size="11"
                      />
                      <Check v-else-if="event.status === 'completed'" :size="11" />
                      <Clock3 v-else :size="11" />
                    </span>
                    <div>
                      <b>{{ event.title }}</b>
                      <p v-if="event.detail || event.observation">
                        {{ event.detail || event.observation }}
                      </p>
                    </div>
                  </div>
                </div>
              </details>
            </div>

            <div v-if="message.content" class="stream-message-content">
              {{ message.content }}<i v-if="message.pending" class="stream-cursor"></i>
            </div>
            <div v-else-if="message.pending" class="stream-pending">
              <span></span><span></span><span></span>正在连接分析流程
            </div>
          </div>
        </article>
      </div>
    </div>

    <footer class="stream-composer-area">
      <div v-if="modelNotice" class="model-notice" role="status">
        {{ modelNotice }}
        <button type="button" aria-label="关闭提示" @click="modelNotice = ''">×</button>
      </div>
      <div v-if="!hasMessages" class="stream-quick-prompts">
        <button
          v-for="prompt in quickPrompts"
          :key="prompt.title"
          :disabled="busy || !props.summary?.block_count"
          @click="send(`${prompt.title}：${prompt.detail}`)"
        >
          <strong>{{ prompt.title }}</strong
          ><span>{{ prompt.detail }}</span>
        </button>
      </div>
      <form class="stream-composer" @submit.prevent="send()">
        <textarea
          v-model="draft"
          aria-label="输入分析问题"
          rows="2"
          maxlength="2000"
          :disabled="busy || !props.summary?.block_count"
          :placeholder="
            props.summary?.block_count ? '描述你想分析的片区、目标与约束条件…' : '正在加载空间数据…'
          "
          @keydown="onKeydown"
        ></textarea>
        <div class="stream-composer-toolbar">
          <button class="stream-add-button" type="button" disabled title="附件功能即将开放">
            <Paperclip :size="17" />
          </button>
          <label class="stream-model-selector">
            <Bot :size="14" />
            <select v-model="selectedModel" :disabled="busy" aria-label="选择模型">
              <option value="">默认模型</option>
              <option
                v-for="model in props.summary?.models"
                :key="model.id"
                :value="model.id"
                :disabled="!model.ready"
              >
                {{ model.label }}{{ model.ready ? "" : "（未配置）" }}
              </option>
            </select>
          </label>
          <button
            class="stream-model-add-button"
            type="button"
            title="使用 API Key 添加大模型"
            aria-label="添加大模型"
            :disabled="busy"
            @click="modelDialogOpen = true"
          >
            <Plus :size="16" />
          </button>
          <span class="stream-input-hint">Enter 发送</span>
          <button class="stream-send-button" type="submit" :disabled="busy || !draft.trim()">
            <ArrowUp :size="17" stroke-width="2.5" />
          </button>
        </div>
      </form>
      <p>内容由智能模型生成，重要规划结论请结合专业审查。</p>
    </footer>

    <ModelSettingsDialog
      v-if="modelDialogOpen"
      :models="props.summary?.models ?? []"
      @close="modelDialogOpen = false"
      @created="handleModelCreated"
      @removed="handleModelRemoved"
    />
  </section>
</template>
