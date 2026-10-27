<script setup lang="ts">
import { computed } from "vue";

import type { RegenerationDecision } from "../../types/domain";

const props = defineProps<{
  decisions: RegenerationDecision[];
  potentialThreshold: number;
}>();

const points = computed(() =>
  props.decisions.slice(0, 600).map((item) => ({
    ...item,
    x: 42 + item.regeneration_potential * 4.9,
    y: 326 - item.inefficiency_score * 2.75,
  })),
);

const colors: Record<string, string> = {
  重点再生: "#ef8354",
  渐进更新: "#efb758",
  活力培育: "#4fb7a7",
  稳定提升: "#5288d8",
  生态修复: "#6d8f61",
};
</script>

<template>
  <div class="matrix-wrap">
    <svg class="matrix" viewBox="0 0 560 360" role="img" aria-label="低效程度与再生潜力二维矩阵">
      <rect x="42" y="24" width="490" height="302" rx="12" class="matrix-bg" />
      <line
        :x1="42 + potentialThreshold * 4.9"
        :x2="42 + potentialThreshold * 4.9"
        y1="24"
        y2="326"
        class="threshold-line"
      />
      <circle
        v-for="point in points"
        :key="point.block_id"
        :cx="point.x"
        :cy="point.y"
        r="4"
        :fill="colors[point.regeneration_scenario] || '#718096'"
        fill-opacity="0.72"
      >
        <title>
          {{ point.block_name || point.block_id }}：{{ point.inefficiency_level }}，{{
            point.regeneration_scenario
          }}
        </title>
      </circle>
      <text x="287" y="352" text-anchor="middle">再生潜力 →</text>
      <text x="15" y="175" text-anchor="middle" transform="rotate(-90 15 175)">低效程度 →</text>
    </svg>
    <p>低效等级按六维得分及维度条件判定；纵轴分数仅用于展示。</p>
    <div class="legend">
      <span v-for="(color, label) in colors" :key="label"
        ><i :style="{ background: color }"></i>{{ label }}</span
      >
    </div>
  </div>
</template>
