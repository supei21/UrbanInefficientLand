<script setup lang="ts">
import {
  Bot,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  Plus,
  Send,
  Sparkles,
  UserRound,
} from "lucide-vue-next";
import { computed, nextTick, ref, watch } from "vue";

import { streamChat } from "../../api/workspace";
import type { ChatPacket, ChatProcessEvent, WorkspaceSummary } from "../../types/domain";

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
const draft = ref("");
const busy = ref(false);
const selectedModel = ref("");
const conversation = ref<HTMLDivElement | null>(null);
const messages = ref<ChatMessage[]>([
  {
    id: "welcome",
    role: "assistant",
    content:
      "您好，我是城市低效空间再生智能助手。我可以读取当前空间单元数据，完成低效识别、再生潜力评估、场景策划和政策依据检索，并把分析过程实时展示给您。",
  },
]);

const quickPrompts = [
  "分析当前数据中的低效空间，并说明最优先的更新片区",
  "解释重点再生单元的主要驱动因素和风险",
  "结合政策要求给出近期行动建议",
];
const modelId = computed(
  () => selectedModel.value || props.summary?.default_model_id || "local-rules",
);
const activeModel = computed(() =>
  props.summary?.models.find((model) => model.id === modelId.value),
);

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
  <section class="stream-chat-panel">
    <header class="stream-chat-header">
      <div>
        <span class="eyebrow">PLANNING COPILOT</span>
        <h2>城市低效空间再生智能助手</h2>
        <p>
          {{ props.summary?.block_count ?? 0 }} 个空间单元已加载 ·
          {{ activeModel?.label || "正在读取模型" }}
        </p>
      </div>
      <div class="stream-status">
        <i :class="{ busy }"></i>{{ busy ? "智能体执行中" : "等待任务" }}
      </div>
    </header>

    <div ref="conversation" class="stream-chat-scroll">
      <div class="stream-conversation">
        <article
          v-for="message in messages"
          :key="message.id"
          :class="['stream-message', message.role, { error: message.error }]"
        >
          <div class="stream-avatar">
            <UserRound v-if="message.role === 'user'" :size="16" />
            <Bot v-else :size="16" />
          </div>
          <div class="stream-message-body">
            <div class="stream-message-meta">
              <strong>{{ message.role === "user" ? "你" : "再生规划智能体" }}</strong>
              <span v-if="message.modelName">{{ message.modelName }}</span>
            </div>

            <div v-if="message.events?.length" class="stream-process-trace">
              <details open>
                <summary>
                  <Sparkles :size="13" />
                  <span>{{ message.pending ? "正在执行分析流程" : "分析过程" }}</span>
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
      <div class="stream-quick-prompts">
        <button
          v-for="prompt in quickPrompts"
          :key="prompt"
          :disabled="busy || !props.summary?.block_count"
          @click="send(prompt)"
        >
          {{ prompt }}
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
            props.summary?.block_count
              ? '询问低效空间、再生场景、政策依据或实施建议…'
              : '请先加载空间数据'
          "
          @keydown="onKeydown"
        ></textarea>
        <div class="stream-composer-toolbar">
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
          <button class="stream-add-button" type="button" disabled title="模型由配置文件统一管理">
            <Plus :size="14" />
          </button>
          <span class="stream-input-hint">Enter 发送 · Shift+Enter 换行</span>
          <button class="stream-send-button" type="submit" :disabled="busy || !draft.trim()">
            <Send :size="16" />
          </button>
        </div>
      </form>
      <p>竞赛演示结果用于城市更新研究与方案比选，不替代法定规划审查。</p>
    </footer>
  </section>
</template>
