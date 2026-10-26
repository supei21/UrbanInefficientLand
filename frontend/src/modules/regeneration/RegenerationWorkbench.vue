<script setup lang="ts">
import type { GeoJsonProperties } from "geojson";
import {
  BarChart3,
  ChevronDown,
  ChevronUp,
  Download,
  Layers3,
  LocateFixed,
  Map,
  Play,
  SlidersHorizontal,
} from "lucide-vue-next";
import { computed, ref } from "vue";

import { analyzeRegeneration } from "../../api/workspace";
import type { RegenerationDecision, RegenerationResult } from "../../types/domain";
import PriorityMatrix from "./PriorityMatrix.vue";
import RegenerationMap from "./RegenerationMap.vue";

const SCENARIOS = ["全部", "重点再生", "渐进更新", "活力培育", "稳定提升", "生态修复"];
const SCENARIO_COLORS: Record<string, string> = {
  重点再生: "#e85d3f",
  渐进更新: "#f2a541",
  活力培育: "#2e86ab",
  稳定提升: "#4f9d69",
  生态修复: "#657153",
};

const inefficiency = ref(60);
const potential = ref(50);
const result = ref<RegenerationResult | null>(null);
const selected = ref<RegenerationDecision | null>(null);
const scenario = ref("全部");
const busy = ref(false);
const error = ref("");
const view = ref<"map" | "matrix">("map");
const tableOpen = ref(true);

const topDecisions = computed(() => result.value?.decisions.slice(0, 50) ?? []);
const scenarioRows = computed(() => Object.entries(result.value?.summary.scenario_counts ?? {}));
const visibleCount = computed(() => {
  if (!result.value) return 0;
  if (scenario.value === "全部") return result.value.summary.total;
  return result.value.summary.scenario_counts[scenario.value] ?? 0;
});

async function runAnalysis() {
  busy.value = true;
  error.value = "";
  selected.value = null;
  try {
    result.value = await analyzeRegeneration(inefficiency.value, potential.value);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "分析失败";
  } finally {
    busy.value = false;
  }
}

function selectFeature(properties: GeoJsonProperties | null) {
  const blockId = String(properties?.block_id ?? "");
  selected.value = result.value?.decisions.find((item) => item.block_id === blockId) ?? null;
}

function colorOf(name: string): string {
  return SCENARIO_COLORS[name] ?? "#718096";
}
</script>

<template>
  <div class="regeneration-workbench">
    <section class="map-workspace">
      <header class="map-toolbar">
        <div class="map-title">
          <Map :size="17" />
          <div><strong>武汉市低效空间再生场景图</strong><span>低效程度 × 再生潜力</span></div>
        </div>
        <div class="map-view-toggle" role="tablist" aria-label="分析视图">
          <button :class="{ active: view === 'map' }" @click="view = 'map'">
            <Map :size="14" />地图
          </button>
          <button :class="{ active: view === 'matrix' }" @click="view = 'matrix'">
            <BarChart3 :size="14" />矩阵
          </button>
        </div>
        <label class="scenario-filter">
          <Layers3 :size="14" />
          <select v-model="scenario" aria-label="再生场景筛选">
            <option v-for="item in SCENARIOS" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <span class="feature-count">{{ visibleCount }} 个空间单元</span>
      </header>

      <div class="map-stage">
        <RegenerationMap
          v-show="view === 'map'"
          :data="result?.spatial"
          :scenario="scenario"
          @select="selectFeature"
        />
        <div v-show="view === 'matrix'" class="matrix-stage">
          <PriorityMatrix
            v-if="result"
            :decisions="result.decisions"
            :inefficiency-threshold="inefficiency"
            :potential-threshold="potential"
          />
          <div v-else class="map-empty-message">运行分析后查看低效程度与再生潜力矩阵</div>
        </div>
        <div v-if="!result && view === 'map'" class="map-empty-overlay">
          <LocateFixed :size="28" />
          <strong>空间数据已就绪</strong>
          <span>点击右侧“运行再生分析”，在地图上生成五类再生场景</span>
        </div>
        <div v-if="busy" class="map-loading">
          <i></i><strong>正在计算 6721 个空间单元</strong><span>生成低效识别与再生场景图层</span>
        </div>
        <div v-if="view === 'map'" class="map-legend-panel">
          <span v-for="name in SCENARIOS.slice(1)" :key="name">
            <i :style="{ background: colorOf(name) }"></i>{{ name }}
          </span>
        </div>
      </div>

      <footer class="map-statusbar">
        <span><i class="status-ready"></i>{{ result ? "分析图层已加载" : "等待分析" }}</span>
        <span>坐标系：CGCS2000 → WGS84</span>
        <span>底图：OpenStreetMap</span>
        <button @click="tableOpen = !tableOpen">
          {{ tableOpen ? "收起属性表" : "展开属性表" }}
          <ChevronDown v-if="tableOpen" :size="13" /><ChevronUp v-else :size="13" />
        </button>
      </footer>

      <section :class="['attribute-drawer', { open: tableOpen }]">
        <div class="attribute-header">
          <div><strong>优先再生单元</strong><span>按综合优先级排序，显示前 50 条</span></div>
          <span v-if="result">{{ result.summary.total }} 条分析结果</span>
        </div>
        <div class="attribute-table-scroll">
          <table>
            <thead>
              <tr>
                <th>排名</th>
                <th>单元编号</th>
                <th>行政区</th>
                <th>再生场景</th>
                <th>低效程度</th>
                <th>再生潜力</th>
                <th>优先级</th>
                <th>实施时序</th>
              </tr>
            </thead>
            <tbody v-if="topDecisions.length">
              <tr
                v-for="(item, index) in topDecisions"
                :key="item.block_id"
                :class="{ selected: selected?.block_id === item.block_id }"
                @click="selected = item"
              >
                <td class="rank">{{ index + 1 }}</td>
                <td>
                  <b>{{ item.block_id }}</b>
                </td>
                <td>{{ item.district || "—" }}</td>
                <td>
                  <span
                    class="scenario-dot"
                    :style="{ background: colorOf(item.regeneration_scenario) }"
                  ></span
                  >{{ item.regeneration_scenario }}
                </td>
                <td>{{ item.inefficiency_score.toFixed(1) }}</td>
                <td>{{ item.regeneration_potential.toFixed(1) }}</td>
                <td>{{ item.priority_score.toFixed(1) }}</td>
                <td>{{ item.implementation_timing }}</td>
              </tr>
            </tbody>
            <tbody v-else>
              <tr>
                <td colspan="8" class="table-empty">运行分析后显示优先再生单元</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>

    <aside class="analysis-sidebar">
      <header class="analysis-header">
        <div>
          <span class="eyebrow">ANALYSIS</span>
          <h2>再生分析</h2>
        </div>
        <SlidersHorizontal :size="18" />
      </header>
      <div class="analysis-scroll">
        <section class="analysis-card parameter-card">
          <h3>识别参数</h3>
          <label>
            <span
              >低效识别阈值 <b>{{ inefficiency }}</b></span
            >
            <input v-model.number="inefficiency" type="range" min="0" max="100" />
          </label>
          <label>
            <span
              >再生潜力阈值 <b>{{ potential }}</b></span
            >
            <input v-model.number="potential" type="range" min="0" max="100" />
          </label>
          <button class="run-analysis-button" :disabled="busy" @click="runAnalysis">
            <Play :size="15" fill="currentColor" />{{ busy ? "正在分析…" : "运行再生分析" }}
          </button>
          <p v-if="error" class="error-text">{{ error }}</p>
        </section>

        <section class="analysis-card">
          <h3>分析概览</h3>
          <div class="summary-grid">
            <div>
              <span>分析单元</span><strong>{{ result?.summary.total ?? "—" }}</strong>
            </div>
            <div>
              <span>低效候选</span><strong>{{ result?.summary.candidate_count ?? "—" }}</strong>
            </div>
            <div>
              <span>近期重点</span><strong>{{ result?.summary.priority_count ?? "—" }}</strong>
            </div>
            <div>
              <span>人工复核</span><strong>{{ result?.summary.manual_review_count ?? "—" }}</strong>
            </div>
          </div>
          <div v-if="result" class="average-bars">
            <div>
              <span>平均低效程度</span><b>{{ result.summary.average_inefficiency }}</b
              ><i><em :style="{ width: `${result.summary.average_inefficiency}%` }"></em></i>
            </div>
            <div>
              <span>平均再生潜力</span><b>{{ result.summary.average_potential }}</b
              ><i><em :style="{ width: `${result.summary.average_potential}%` }"></em></i>
            </div>
          </div>
        </section>

        <section class="analysis-card">
          <h3>场景分类</h3>
          <div v-if="scenarioRows.length" class="scenario-summary-list">
            <button v-for="[name, count] in scenarioRows" :key="name" @click="scenario = name">
              <i :style="{ background: colorOf(name) }"></i><span>{{ name }}</span
              ><strong>{{ count }}</strong>
            </button>
          </div>
          <p v-else class="analysis-empty">运行分析后显示五类再生场景统计。</p>
        </section>

        <section class="analysis-card selection-card">
          <h3>单元详情</h3>
          <template v-if="selected">
            <div class="selection-title">
              <div>
                <b>{{ selected.block_name || selected.block_id }}</b
                ><span>{{ selected.block_id }} · {{ selected.district }}</span>
              </div>
              <em :style="{ color: colorOf(selected.regeneration_scenario) }">{{
                selected.regeneration_scenario
              }}</em>
            </div>
            <dl>
              <div>
                <dt>场景定位</dt>
                <dd>{{ selected.scenario_positioning }}</dd>
              </div>
              <div>
                <dt>优先等级</dt>
                <dd>{{ selected.priority_level }}</dd>
              </div>
              <div>
                <dt>实施时序</dt>
                <dd>{{ selected.implementation_timing }}</dd>
              </div>
              <div>
                <dt>行动建议</dt>
                <dd>{{ selected.scenario_actions.join("、") }}</dd>
              </div>
              <div>
                <dt>关键证据</dt>
                <dd>{{ selected.key_evidence.join("；") }}</dd>
              </div>
            </dl>
          </template>
          <p v-else class="analysis-empty">在地图或属性表中点击空间单元查看识别依据与场景建议。</p>
        </section>

        <section v-if="result?.artifact" class="analysis-card export-card">
          <h3>成果导出</h3>
          <a :href="`/api/artifacts/${result.artifact.id}/download`"
            ><Download :size="14" />下载完整分析 JSON</a
          >
        </section>
      </div>
    </aside>
  </div>
</template>
