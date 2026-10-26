<script setup lang="ts">
import { ref } from "vue";
import { FileUp, RotateCcw } from "lucide-vue-next";

import { resetWorkspace, uploadDataset } from "../../api/workspace";
import type { WorkspaceSummary } from "../../types/domain";

const props = defineProps<{ summary: WorkspaceSummary | null }>();
const emit = defineEmits<{ changed: [summary: WorkspaceSummary] }>();
const input = ref<HTMLInputElement | null>(null);
const busy = ref(false);
const error = ref("");

async function chooseFile(event: Event) {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;
  busy.value = true;
  error.value = "";
  try {
    emit("changed", await uploadDataset(file));
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "上传失败";
  } finally {
    busy.value = false;
    target.value = "";
  }
}

async function reset() {
  busy.value = true;
  error.value = "";
  try {
    emit("changed", await resetWorkspace());
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "重置失败";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="side-section">
    <div class="section-label">数据工作区</div>
    <div class="dataset-card">
      <div class="dataset-name">{{ props.summary?.dataset_name || "正在加载数据" }}</div>
      <div class="dataset-metrics">
        <div>
          <strong>{{ props.summary?.block_count ?? "—" }}</strong
          ><span>空间单元</span>
        </div>
        <div>
          <strong>{{ props.summary?.field_count ?? "—" }}</strong
          ><span>指标字段</span>
        </div>
      </div>
      <span v-if="props.summary?.has_spatial_data" class="status-pill">包含空间几何</span>
    </div>
    <input
      ref="input"
      class="visually-hidden"
      type="file"
      accept=".json,.csv,.zip"
      @change="chooseFile"
    />
    <button class="button secondary full" :disabled="busy" @click="input?.click()">
      <FileUp :size="16" /> {{ busy ? "处理中…" : "导入分析数据" }}
    </button>
    <button class="button ghost full" :disabled="busy" @click="reset">
      <RotateCcw :size="15" /> 恢复演示数据
    </button>
    <p v-if="error" class="error-text">{{ error }}</p>
    <p v-for="warning in props.summary?.dataset_warnings" :key="warning" class="warning-text">
      {{ warning }}
    </p>
  </section>
</template>
