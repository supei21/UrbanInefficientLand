# 天枢杯｜城市低效空间再生智能系统

参赛选题：**低效空间再生：面向城市活力重塑的空间识别与场景策划**。

这是一个独立的天枢杯参赛项目。项目路径以实际克隆目录为准，不依赖其他项目目录。

## 比赛演示闭环

1. 上传或读取街区/地块多源属性数据。
2. 对开发边界内地块，按土地利用、城市活力、功能结构、公共服务、交通可达性、空间品质六个维度计算低效程度，并划分高度、明显、疑似、一般四级。
3. 从区位价值、市场支撑、空间承载、实施可行性四个方面计算再生潜力。
4. 结合六维低效等级、再生潜力与刚性约束划分再生类型，并用散点图展示低效得分与潜力。
5. 输出重点再生、渐进更新、活力培育、稳定提升、生态修复五类场景。
6. 生成单元级行动建议、实施时序、优先级排名和可解释证据。
7. 空间数据存在时导出 JSON、GeoJSON 与 SHP ZIP 成果。

仓库自带 `data/sample/blocks.json`（3 个示例单元）。如果在 `data/input/Wuhan_block_llm.json` 放置完整数据，启动时会优先加载该文件；完整数据未包含在仓库中。六维低效算法见 `tianshu_core/low_efficiency.py`，再生潜力和场景策划见 `tianshu_core/regeneration.py`。低效权重与等级采用 2026-10-25 修正试算口径：当前建设比例读取 `Bulit_Area`，上期读取 `Bulit_pro2`，变化量为二者之差。导入 SHP ZIP 时，`Bulit_pro2` 会映射成 `construction_ratio`；`previous_construction_ratio` 是更早一期，不参与这两个年份的变化量计算。`config/analysis.yaml` 中保留同口径的权重说明，运行计算以 Python 代码为准。

若本机具有原始武汉 ArcGIS FeatureSet 和修正试算的 `low_efficiency_trial_data.json`，可运行 `scripts/prepare_wuhan_local.py <原始JSON> <修正试算JSON>`，只读这两份来源并在被 Git 忽略的 `data/input/Wuhan_block_llm.json` 生成 5254 个边界内地块的本地输入。评分在每次分析时重新计算，不读取旧成果中的预计算分数。

独立导出 SHP 可运行 `python -m scripts.evaluate_low_efficiency_shp <街区数据.zip> <输出目录>`。脚本使用 ZIP 内已有的开发边界重叠率字段，筛选重叠率不少于 50% 的地块；不会自行叠加开发边界面图层，也不调用 Web 系统。输出全部参评、三级候选、高度与明显低效、无需人工复核候选四组 SHP，保留原始属性并增加 `EVIDENCE` 等评价字段。生成的成果位于被 Git 忽略的 `outputs/` 时不会进入仓库。

## 技术架构

- 前端：Vue 3、TypeScript、Vite，按 `api / composables / modules / components` 分层。
- 后端：Python 3.11、Flask 应用工厂、Blueprint、Pydantic 请求校验。
- 领域层：空间分析、XGBoost、智能体、政策 RAG，与 Web 框架解耦。
- 工程质量：Ruff、mypy、pytest、ESLint、Prettier、vue-tsc。

详细模块边界见 `docs/development/ARCHITECTURE.md`，协作与代码评审规范见 `CONTRIBUTING.md`。

## 独立 Conda 环境

项目禁止使用 pip 安装。首次搭建：

```powershell
cd "<项目克隆目录>"
conda env create --name TIANSHU --file environment.yml
conda run --name TIANSHU npm --prefix frontend install
```

已有环境按环境文件更新：

```powershell
conda env update --name TIANSHU --file environment.yml --prune
```

也可以直接运行 `scripts/setup_conda.ps1`。项目不使用 pip 安装；Python 与 Node.js 均由项目内 Conda 环境提供，前端包通过该环境中的 npm 安装。

## 运行

```powershell
conda run --name TIANSHU python scripts\run_demo.py
```

浏览器打开 `http://127.0.0.1:8000`。

前端开发模式：

```powershell
conda run --name TIANSHU flask --app backend.main:app run --debug --port 8000
conda run --name TIANSHU npm --prefix frontend run dev
```

## 验证

```powershell
.\scripts\check.ps1
```

## 输入字段

最低要求：

- `block_id`：空间单元唯一编号。
- `block_name` 或 `district`：展示名称，建议提供。
- 六维评价建议提供 2026/2021 年建设比例、夜间灯光、POI、人口密度、道路密度、街区几何及开发边界重叠比例。

系统兼容原项目字段及常见同义字段，例如 `poi_density` / `poi_density_per_km2`、`road_density` / `road_density_km_per_km2`、`pop_density` / `pop_density_per_km2`。

若提供 `ecological_redline`、`permanent_farmland` 或 `prohibited_disaster_zone`，命中刚性约束的单元将优先进入“生态修复”场景。六维评价中缺失的数值指标使用中位百分位（50）参与计算，并给出数据覆盖率。候选地块如涉及生态或耕地约束、异常面积、开发边界临界重叠，会标记人工复核。

## 主要目录

```text
TIANSHU/
├─ backend/
│  ├─ app.py                  # Flask 应用工厂与全局适配
│  ├─ api/                    # 按业务能力拆分的 Blueprint
│  └─ workspace.py            # 应用用例与成果管理
├─ tianshu_core/
│  └─ regeneration.py         # 比赛核心算法
├─ config/analysis.yaml       # 阈值、权重与系统配置
├─ data/input/                # 默认武汉街区数据
├─ frontend/src/
│  ├─ api/                    # 类型化 API 客户端
│  ├─ composables/            # 跨组件状态
│  └─ modules/                # Vue 业务模块
├─ tests/test_regeneration.py # 核心算法测试
├─ environment.yml            # Conda 环境定义
└─ scripts/run_demo.py        # 统一启动入口
```

## 结果说明

比赛版结果用于城市更新研究、候选片区筛查和场景比选，不替代法定规划、权属核验、现场调查或工程可行性论证。
