# 天枢杯｜城市低效空间再生智能系统

参赛选题：**低效空间再生：面向城市活力重塑的空间识别与场景策划**。

这是一个独立的天枢杯参赛项目。代码、Conda 环境、数据、前端构建物与运行成果均位于 `E:\VscodeMyPrograma\TIANSHU`，不依赖其他项目目录。

## 比赛演示闭环

1. 上传或读取街区/地块多源属性数据。
2. 从活力、功能、空间品质、可达性四个方面计算低效程度。
3. 从区位价值、市场支撑、空间承载、实施可行性四个方面计算再生潜力。
4. 使用“低效程度 × 再生潜力”二维矩阵划分再生类型。
5. 输出重点再生、渐进更新、活力培育、稳定提升、生态修复五类场景。
6. 生成单元级行动建议、实施时序、优先级排名和可解释证据。
7. 空间数据存在时导出 JSON、GeoJSON 与 SHP ZIP 成果。

默认演示数据为武汉市 6721 个街区单元。系统阈值和权重见 `config/analysis.yaml`，核心算法见 `tianshu_core/regeneration.py`。

## 技术架构

- 前端：Vue 3、TypeScript、Vite，按 `api / composables / modules / components` 分层。
- 后端：Python 3.11、Flask 应用工厂、Blueprint、Pydantic 请求校验。
- 领域层：空间分析、XGBoost、智能体、政策 RAG，与 Web 框架解耦。
- 工程质量：Ruff、mypy、pytest、ESLint、Prettier、vue-tsc。

详细模块边界见 `docs/development/ARCHITECTURE.md`，协作与代码评审规范见 `CONTRIBUTING.md`。

## 独立 Conda 环境

项目禁止使用 pip 安装。首次搭建：

```powershell
cd "E:\VscodeMyPrograma\TIANSHU"
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
- POI、人口、道路、公共服务、交通、产业、建设强度、绿地、空置率、建筑年龄等指标至少提供一组。

系统兼容原项目字段及常见同义字段，例如 `poi_density` / `poi_density_per_km2`、`road_density` / `road_density_km_per_km2`、`pop_density` / `pop_density_per_km2`。

若提供 `ecological_redline`、`permanent_farmland` 或 `prohibited_disaster_zone`，命中刚性约束的单元将优先进入“生态修复”场景。缺失指标不会直接填零，系统按可用指标计算并给出数据覆盖率；覆盖率过低时标记人工复核。

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
