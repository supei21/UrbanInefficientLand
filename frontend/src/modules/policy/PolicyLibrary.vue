<script setup lang="ts">
import {
  BookOpen,
  FileSearch,
  FileText,
  FileUp,
  LoaderCircle,
  Search,
  Send,
  Sparkles,
  X,
} from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";

import {
  askPolicyQuestion,
  getPolicyDocument,
  listPolicyDocuments,
  searchPolicyDocuments,
  uploadPolicyDocuments,
} from "../../api/workspace";
import type {
  ModelOption,
  PolicyAnswer,
  PolicyDocumentDetail,
  PolicyDocumentSummary,
  PolicySearchResult,
} from "../../types/domain";

const props = defineProps<{
  models: readonly ModelOption[];
  defaultModelId?: string;
}>();

const documents = ref<PolicyDocumentSummary[]>([]);
const selected = ref<PolicyDocumentDetail | null>(null);
const searchQuery = ref("");
const searchResults = ref<PolicySearchResult[]>([]);
const question = ref("");
const answer = ref<PolicyAnswer | null>(null);
const selectedModel = ref("");
const fileInput = ref<HTMLInputElement | null>(null);
const loading = ref(true);
const documentBusy = ref(false);
const searchBusy = ref(false);
const asking = ref(false);
const uploading = ref(false);
const error = ref("");

const categoryCount = computed(
  () => new Set(documents.value.map((item) => item.category || "综合政策")).size,
);
const totalTextLength = computed(() =>
  documents.value.reduce((total, item) => total + item.text_length, 0),
);
const modelId = computed(() => selectedModel.value || props.defaultModelId || "local-rules");

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

async function loadDocuments() {
  loading.value = true;
  error.value = "";
  try {
    documents.value = await listPolicyDocuments();
    if (documents.value[0]) await selectDocument(documents.value[0].id);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "政策库加载失败";
  } finally {
    loading.value = false;
  }
}

async function selectDocument(documentId: string) {
  documentBusy.value = true;
  error.value = "";
  try {
    selected.value = await getPolicyDocument(documentId);
    searchResults.value = [];
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "政策文档读取失败";
  } finally {
    documentBusy.value = false;
  }
}

async function search() {
  const query = searchQuery.value.trim();
  if (!query || searchBusy.value) return;
  searchBusy.value = true;
  error.value = "";
  try {
    searchResults.value = await searchPolicyDocuments(query);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "政策检索失败";
  } finally {
    searchBusy.value = false;
  }
}

async function ask() {
  const query = question.value.trim();
  if (!query || asking.value) return;
  asking.value = true;
  answer.value = null;
  error.value = "";
  try {
    answer.value = await askPolicyQuestion(query, modelId.value);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "政策问答失败";
  } finally {
    asking.value = false;
  }
}

async function upload(event: Event) {
  const target = event.target as HTMLInputElement;
  const files = Array.from(target.files ?? []);
  if (!files.length) return;
  uploading.value = true;
  error.value = "";
  const previousIds = new Set(documents.value.map((item) => item.id));
  try {
    documents.value = await uploadPolicyDocuments(files);
    const newest = documents.value.find((item) => !previousIds.has(item.id));
    if (newest) await selectDocument(newest.id);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "政策文件入库失败";
  } finally {
    uploading.value = false;
    target.value = "";
  }
}

onMounted(loadDocuments);
</script>

<template>
  <section class="policy-library-page">
    <header class="policy-overview">
      <div class="policy-overview-copy">
        <span>POLICY KNOWLEDGE BASE</span>
        <h2>城市更新政策知识库</h2>
        <p>集中管理政策原文，支持语义检索、条款溯源和基于当前模型的政策问答。</p>
      </div>
      <div class="policy-overview-stats">
        <article>
          <strong>{{ documents.length }}</strong
          ><span>政策文档</span>
        </article>
        <article>
          <strong>{{ categoryCount }}</strong
          ><span>政策分类</span>
        </article>
        <article>
          <strong>{{ totalTextLength.toLocaleString() }}</strong
          ><span>已解析字符</span>
        </article>
      </div>
      <input
        ref="fileInput"
        class="visually-hidden"
        type="file"
        multiple
        accept=".txt,.docx,.pdf"
        @change="upload"
      />
      <button class="policy-upload-button" :disabled="uploading" @click="fileInput?.click()">
        <LoaderCircle v-if="uploading" class="spin" :size="16" />
        <FileUp v-else :size="16" />
        {{ uploading ? "正在入库…" : "导入政策文件" }}
      </button>
    </header>

    <form class="policy-searchbar" @submit.prevent="search">
      <Search :size="18" />
      <input
        v-model="searchQuery"
        aria-label="检索政策库"
        maxlength="200"
        placeholder="检索政策名称、更新要求、土地用途或实施条件…"
      />
      <button type="submit" :disabled="searchBusy || !searchQuery.trim()">
        <LoaderCircle v-if="searchBusy" class="spin" :size="15" />
        <span>{{ searchBusy ? "检索中" : "检索政策" }}</span>
      </button>
    </form>

    <p v-if="error" class="policy-error">{{ error }}</p>

    <div class="policy-library-grid">
      <aside class="policy-document-panel">
        <header>
          <BookOpen :size="16" /><strong>政策目录</strong><span>{{ documents.length }}</span>
        </header>
        <div class="policy-document-list">
          <button
            v-for="item in documents"
            :key="item.id"
            :class="{ active: selected?.id === item.id && !searchResults.length }"
            @click="selectDocument(item.id)"
          >
            <span class="policy-file-icon"><FileText :size="16" /></span>
            <span class="policy-file-copy">
              <strong>{{ item.name }}</strong>
              <small>{{ item.category || "综合政策" }} · {{ formatBytes(item.size) }}</small>
              <em>{{ item.excerpt || "暂无摘要" }}</em>
            </span>
          </button>
          <div v-if="loading" class="policy-panel-empty">
            <LoaderCircle class="spin" :size="20" />正在读取政策库
          </div>
          <div v-else-if="!documents.length" class="policy-panel-empty">
            <FileText :size="22" />尚未添加政策文件
          </div>
        </div>
      </aside>

      <div class="policy-main-column">
        <section v-if="searchResults.length" class="policy-result-panel">
          <header>
            <div>
              <span>SEARCH RESULTS</span>
              <h3>“{{ searchQuery }}”的相关条款</h3>
            </div>
            <button type="button" aria-label="关闭检索结果" @click="searchResults = []">
              <X :size="17" />
            </button>
          </header>
          <div class="policy-search-results">
            <article v-for="(item, index) in searchResults" :key="`${item.source}-${index}`">
              <div class="policy-result-rank">{{ String(index + 1).padStart(2, "0") }}</div>
              <div>
                <strong>{{ item.source || "政策规则库" }}</strong>
                <span>
                  相关度 {{ Math.round(item.score * 100) }}%
                  <template v-if="item.article_ref"> · {{ item.article_ref }}</template>
                </span>
                <p>{{ item.excerpt }}</p>
                <button
                  v-if="item.document_id"
                  type="button"
                  @click="selectDocument(item.document_id)"
                >
                  查看原文
                </button>
              </div>
            </article>
          </div>
        </section>

        <section v-else class="policy-reader-panel">
          <header v-if="selected">
            <div>
              <span>{{ selected.category || "综合政策" }}</span>
              <h3>{{ selected.name }}</h3>
              <p>
                {{ selected.source }} · {{ formatBytes(selected.size) }} ·
                {{ selected.text_length.toLocaleString() }} 字符
              </p>
            </div>
            <FileText :size="22" />
          </header>
          <div v-if="documentBusy" class="policy-reader-empty">
            <LoaderCircle class="spin" :size="22" />正在读取政策原文
          </div>
          <div v-else-if="selected" class="policy-document-content">{{ selected.content }}</div>
          <div v-else class="policy-reader-empty">
            <FileSearch :size="26" />从左侧选择政策文件查看原文
          </div>
        </section>

        <section class="policy-ask-panel">
          <header>
            <div class="policy-ask-icon"><Sparkles :size="17" /></div>
            <div><strong>政策问答</strong><span>基于政策库回答，并返回可追溯依据</span></div>
          </header>
          <form @submit.prevent="ask">
            <textarea
              v-model="question"
              rows="2"
              maxlength="2000"
              placeholder="例如：低效工业用地更新需要重点满足哪些政策条件？"
            ></textarea>
            <div>
              <select v-model="selectedModel" :disabled="asking" aria-label="政策问答模型">
                <option value="">默认模型</option>
                <option
                  v-for="item in props.models"
                  :key="item.id"
                  :value="item.id"
                  :disabled="!item.ready"
                >
                  {{ item.label }}{{ item.ready ? "" : "（未配置）" }}
                </option>
              </select>
              <button type="submit" :disabled="asking || !question.trim()">
                <LoaderCircle v-if="asking" class="spin" :size="15" />
                <Send v-else :size="15" />{{ asking ? "分析中…" : "开始问答" }}
              </button>
            </div>
          </form>
          <div v-if="answer" class="policy-answer">
            <div>
              <Sparkles :size="15" /><strong>政策库回答</strong><span>{{ answer.mode }}</span>
            </div>
            <p>{{ answer.answer }}</p>
          </div>
        </section>
      </div>
    </div>
  </section>
</template>
