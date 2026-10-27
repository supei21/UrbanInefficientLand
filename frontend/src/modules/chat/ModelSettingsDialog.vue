<script setup lang="ts">
import { Check, Eye, EyeOff, KeyRound, Plus, Trash2, X } from "lucide-vue-next";
import { computed, ref } from "vue";

import { createUserModel, deleteUserModel } from "../../api/workspace";
import type { ModelOption, WorkspaceSummary } from "../../types/domain";

const props = defineProps<{ models: readonly ModelOption[] }>();
const emit = defineEmits<{
  close: [];
  created: [workspace: WorkspaceSummary, modelId: string];
  removed: [workspace: WorkspaceSummary, modelId: string];
}>();

const label = ref("");
const model = ref("");
const baseUrl = ref("");
const apiKey = ref("");
const showKey = ref(false);
const busy = ref(false);
const deletingId = ref("");
const error = ref("");

const customModels = computed(() => props.models.filter((item) => item.id.startsWith("custom-")));
const canSubmit = computed(
  () =>
    Boolean(label.value.trim()) &&
    Boolean(model.value.trim()) &&
    Boolean(baseUrl.value.trim()) &&
    Boolean(apiKey.value.trim()) &&
    !busy.value,
);

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

async function submit() {
  if (!canSubmit.value) return;
  busy.value = true;
  error.value = "";
  try {
    const endpoint = new URL(normalizeBaseUrl(baseUrl.value));
    if (!["http:", "https:"].includes(endpoint.protocol)) {
      throw new Error("API 地址必须以 http:// 或 https:// 开头");
    }
    const result = await createUserModel({
      label: label.value.trim(),
      model: model.value.trim(),
      base_url: endpoint.toString().replace(/\/$/, ""),
      api_key: apiKey.value.trim(),
    });
    apiKey.value = "";
    emit("created", result.workspace, result.model.id);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "模型添加失败";
  } finally {
    busy.value = false;
  }
}

async function remove(modelId: string) {
  deletingId.value = modelId;
  error.value = "";
  try {
    emit("removed", await deleteUserModel(modelId), modelId);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "模型删除失败";
  } finally {
    deletingId.value = "";
  }
}
</script>

<template>
  <div class="model-dialog-backdrop" @click.self="emit('close')">
    <section
      class="model-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="model-dialog-title"
    >
      <header class="model-dialog-header">
        <div class="model-dialog-title">
          <span><KeyRound :size="18" /></span>
          <div>
            <h2 id="model-dialog-title">添加大模型</h2>
            <p>接入支持 OpenAI Chat Completions 协议的模型服务</p>
          </div>
        </div>
        <button type="button" aria-label="关闭模型配置" @click="emit('close')">
          <X :size="18" />
        </button>
      </header>

      <div class="model-dialog-scroll">
        <form class="model-form" @submit.prevent="submit">
          <div class="model-form-grid">
            <label>
              <span>显示名称</span>
              <input
                v-model="label"
                maxlength="40"
                autocomplete="off"
                placeholder="例如：我的 DeepSeek"
              />
            </label>
            <label>
              <span>模型 ID</span>
              <input
                v-model="model"
                maxlength="80"
                autocomplete="off"
                placeholder="例如：deepseek-chat"
              />
            </label>
          </div>
          <label>
            <span>API 地址</span>
            <input
              v-model="baseUrl"
              maxlength="200"
              inputmode="url"
              autocomplete="url"
              placeholder="https://api.example.com/v1"
            />
            <small>请填写服务商提供的 OpenAI 兼容接口根地址。</small>
          </label>
          <label>
            <span>API Key</span>
            <div class="model-key-input">
              <input
                v-model="apiKey"
                :type="showKey ? 'text' : 'password'"
                maxlength="300"
                autocomplete="new-password"
                placeholder="输入 API Key"
              />
              <button
                type="button"
                :aria-label="showKey ? '隐藏 API Key' : '显示 API Key'"
                @click="showKey = !showKey"
              >
                <EyeOff v-if="showKey" :size="16" />
                <Eye v-else :size="16" />
              </button>
            </div>
          </label>

          <div class="model-security-note">
            <Check :size="15" />
            <p>
              Key 只提交到本机 Flask 服务，完整内容不会回传页面或进入
              Git。调用模型时，请求会发送到你填写的 API 地址。
            </p>
          </div>
          <p v-if="error" class="model-form-error">{{ error }}</p>
          <button class="model-submit-button" type="submit" :disabled="!canSubmit">
            <Plus :size="16" />{{ busy ? "正在添加…" : "添加并使用此模型" }}
          </button>
        </form>

        <section v-if="customModels.length" class="custom-model-list">
          <div class="custom-model-list-title">
            <strong>已添加模型</strong><span>{{ customModels.length }}</span>
          </div>
          <article v-for="item in customModels" :key="item.id">
            <span class="custom-model-icon"><KeyRound :size="15" /></span>
            <div>
              <strong>{{ item.label }}</strong>
              <span>{{ item.description }}</span>
            </div>
            <button
              type="button"
              :disabled="Boolean(deletingId)"
              :aria-label="`删除 ${item.label}`"
              @click="remove(item.id)"
            >
              <Trash2 :size="15" />
            </button>
          </article>
        </section>
      </div>
    </section>
  </div>
</template>
