# 系统架构

## 设计目标

比赛版采用 Vue 3 + TypeScript 与 Python Flask，围绕“低效空间识别—再生潜力评估—场景策划—成果输出”形成完整闭环。架构以清晰边界为先，遵循 SOLID、KISS、DRY、YAGNI，但不为模式而模式。

## 依赖方向

```text
Vue 页面/组件
    ↓ 仅通过 typed API client
Flask Blueprint（协议适配、参数校验、状态码）
    ↓
应用服务 DemoWorkspace（流程编排、工作区状态、成果管理）
    ↓
tianshu_core（领域模型、空间算法、模型推理、RAG）
    ↓
data / models / runtime（基础设施与持久化文件）
```

领域算法不导入 Flask，前端组件不直接了解文件存储和模型实现。这样可以分别替换 Web 框架、界面或算法，而不引发级联修改。

## 后端模块

- `backend/app.py`：应用工厂、全局异常、CORS 与静态前端托管。
- `backend/api/`：按系统、数据、分析、政策、成果、对话六类能力划分 Blueprint。
- `backend/http.py`：唯一的 HTTP/Pydantic 转换边界与 NDJSON 流式响应实现。
- `backend/workspace.py`：用例编排和比赛演示工作区。
- `tianshu_core/`：可独立测试的领域算法与智能体能力。

## 前端模块

- `src/api/`：统一请求、错误和流式协议处理。
- `src/composables/`：跨组件的工作区状态与用例状态。
- `src/modules/`：按数据、再生分析、智能助手组织业务功能。
- `src/components/`：不承载业务流程的通用展示组件。
- `src/types/`：前后端契约对应的 TypeScript 类型。

## 质量门禁

`scripts/check.ps1` 顺序执行 Python 格式检查、静态检查、测试、Vue 类型检查、ESLint、Prettier 检查和生产构建。任何合并都应通过同一套命令，避免“在我的电脑上可以”的差异。
