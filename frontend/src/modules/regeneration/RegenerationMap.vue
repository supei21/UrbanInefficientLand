<script setup lang="ts">
import type { Feature, FeatureCollection, GeoJsonProperties, Geometry } from "geojson";
import maplibregl, { GeoJSONSource, LngLatBounds, Popup } from "maplibre-gl";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps<{
  data?: FeatureCollection;
  scenario: string;
}>();
const emit = defineEmits<{
  select: [properties: GeoJsonProperties | null];
}>();

const container = ref<HTMLDivElement | null>(null);
let map: maplibregl.Map | null = null;
let popup: Popup | null = null;
let fitted = false;

const COLORS = [
  "match",
  ["coalesce", ["get", "regeneration_scenario"], ["get", "ai_decision"], ["get", "decision"]],
  "优先更新",
  "#e85d3f",
  "提质改善",
  "#f2a541",
  "生态修复或储备",
  "#657153",
  "持续观察",
  "#4f9d69",
  "#718096",
] as maplibregl.ExpressionSpecification;

function scenarioOf(feature: Feature): string {
  return String(
    feature.properties?.regeneration_scenario ??
      feature.properties?.ai_decision ??
      feature.properties?.decision ??
      "",
  );
}

function visibleData(): FeatureCollection {
  const source = props.data ?? { type: "FeatureCollection", features: [] };
  if (props.scenario === "全部") return source;
  return {
    ...source,
    features: source.features.filter((feature) => scenarioOf(feature) === props.scenario),
  };
}

function extendBounds(bounds: LngLatBounds, coordinates: unknown): void {
  if (!Array.isArray(coordinates)) return;
  if (
    coordinates.length >= 2 &&
    typeof coordinates[0] === "number" &&
    typeof coordinates[1] === "number"
  ) {
    bounds.extend([coordinates[0], coordinates[1]]);
    return;
  }
  coordinates.forEach((value) => extendBounds(bounds, value));
}

function extendGeometry(bounds: LngLatBounds, geometry: Geometry | null): void {
  if (!geometry) return;
  if (geometry.type === "GeometryCollection") {
    geometry.geometries.forEach((item) => extendGeometry(bounds, item));
    return;
  }
  extendBounds(bounds, geometry.coordinates);
}

function visibleMarkers(): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: visibleData().features.flatMap((feature) => {
      if (!feature.geometry || feature.geometry.type === "Point") return [];
      const bounds = new LngLatBounds();
      extendGeometry(bounds, feature.geometry);
      if (bounds.isEmpty()) return [];
      const center = bounds.getCenter();
      return [{
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [center.lng, center.lat] },
        properties: feature.properties,
      }];
    }),
  };
}

function fitData(data: FeatureCollection): void {
  if (!map || !data.features.length) return;
  const bounds = new LngLatBounds();
  data.features.forEach((feature) => extendGeometry(bounds, feature.geometry));
  if (!bounds.isEmpty())
    map.fitBounds(bounds, { padding: 52, maxZoom: 12, duration: fitted ? 450 : 0 });
  fitted = true;
}

function updateSource(): void {
  if (!map?.getSource("regeneration")) return;
  const data = visibleData();
  (map.getSource("regeneration") as GeoJSONSource | undefined)?.setData(data);
  (map.getSource("regeneration-markers") as GeoJSONSource | undefined)?.setData(visibleMarkers());
  if (!fitted && props.data?.features.length) fitData(props.data);
}

function popupContent(properties: GeoJsonProperties): HTMLElement {
  const root = document.createElement("div");
  root.className = "regeneration-popup";
  const title = document.createElement("strong");
  title.textContent = String(properties?.block_name || properties?.block_id || "空间单元");
  const scenario = document.createElement("b");
  scenario.textContent = String(
    properties?.regeneration_scenario ||
      properties?.ai_decision ||
      properties?.decision ||
      "待分析",
  );
  root.append(title, scenario);
  [
    ["低效程度", properties?.inefficiency_score],
    ["低效等级", properties?.inefficiency_level],
    ["主导问题", properties?.dominant_problem],
    ["发展潜力", properties?.regeneration_potential],
    ["潜力等级", properties?.potential_level],
    ["优势方向", properties?.dev_type],
    ["分类依据", properties?.scenario_reason],
    ["优先级", properties?.priority_score],
    ["实施时序", properties?.implementation_timing],
  ].forEach(([label, value]) => {
    if (value === undefined || value === null || value === "") return;
    const row = document.createElement("div");
    const name = document.createElement("span");
    const content = document.createElement("p");
    name.textContent = String(label);
    content.textContent = String(value);
    row.append(name, content);
    root.append(row);
  });
  return root;
}

function bindLayerInteraction(layerId: string): void {
  if (!map) return;
  map.on("mouseenter", layerId, () => {
    if (map) map.getCanvas().style.cursor = "pointer";
  });
  map.on("mouseleave", layerId, () => {
    if (map) map.getCanvas().style.cursor = "";
    popup?.remove();
  });
  map.on("mousemove", layerId, (event) => {
    const properties = event.features?.[0]?.properties ?? null;
    if (!properties || !map) return;
    popup?.setLngLat(event.lngLat).setDOMContent(popupContent(properties)).addTo(map);
  });
  map.on("click", layerId, (event) => {
    emit("select", event.features?.[0]?.properties ?? null);
  });
}

onMounted(() => {
  if (!container.value) return;
  map = new maplibregl.Map({
    container: container.value,
    center: [114.3, 30.58],
    zoom: 8.4,
    attributionControl: false,
    style: {
      version: 8,
      sources: {
        osm: {
          type: "raster",
          tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          tileSize: 256,
          attribution: "© OpenStreetMap contributors",
        },
      },
      layers: [
        { id: "base", type: "background", paint: { "background-color": "#e9eeeb" } },
        { id: "osm", type: "raster", source: "osm", paint: { "raster-opacity": 0.78 } },
      ],
    },
  });
  popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12 });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
  map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
  map.on("load", () => {
    if (!map) return;
    map.addSource("regeneration", { type: "geojson", data: visibleData() });
    map.addSource("regeneration-markers", { type: "geojson", data: visibleMarkers() });
    map.addLayer({
      id: "regeneration-fill",
      type: "fill",
      source: "regeneration",
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "fill-color": COLORS, "fill-opacity": 0.62 },
    });
    map.addLayer({
      id: "regeneration-line",
      type: "line",
      source: "regeneration",
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "line-color": "#ffffff", "line-width": 0.7, "line-opacity": 0.8 },
    });
    map.addLayer({
      id: "regeneration-points",
      type: "circle",
      source: "regeneration",
      filter: ["==", ["geometry-type"], "Point"],
      paint: {
        "circle-color": COLORS,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 3, 11, 6, 14, 10],
        "circle-opacity": 0.78,
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 0.7,
      },
    });
    map.addLayer({
      id: "regeneration-markers",
      type: "circle",
      source: "regeneration-markers",
      maxzoom: 11,
      paint: {
        "circle-color": COLORS,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 3, 10, 5],
        "circle-opacity": 0.9,
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 0.8,
      },
    });
    bindLayerInteraction("regeneration-fill");
    bindLayerInteraction("regeneration-points");
    bindLayerInteraction("regeneration-markers");
    updateSource();
  });
});

watch(() => [props.data, props.scenario], updateSource, { deep: true });

onBeforeUnmount(() => {
  popup?.remove();
  map?.remove();
  map = null;
});
</script>

<template>
  <div ref="container" class="regeneration-map" aria-label="低效空间再生场景地图"></div>
</template>
