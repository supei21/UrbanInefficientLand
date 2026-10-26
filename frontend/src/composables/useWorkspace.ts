import { computed, readonly, ref } from "vue";

import { getWorkspace } from "../api/workspace";
import type { WorkspaceSummary } from "../types/domain";

const summary = ref<WorkspaceSummary | null>(null);
const loading = ref(false);
const error = ref("");

export function useWorkspace() {
  async function refresh() {
    loading.value = true;
    error.value = "";
    try {
      summary.value = await getWorkspace();
    } catch (reason) {
      error.value = reason instanceof Error ? reason.message : "工作区加载失败";
    } finally {
      loading.value = false;
    }
  }

  function replace(next: WorkspaceSummary) {
    summary.value = next;
  }

  return {
    summary: readonly(summary),
    loading: readonly(loading),
    error: readonly(error),
    ready: computed(() => Boolean(summary.value)),
    refresh,
    replace,
  };
}
