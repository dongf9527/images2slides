# images2slides 私有化部署配置指南

> 目标读者：要把 images2slides 跑在自己（或公司内网）机器上的部署者。
> 先读《p0-issues-explained.md》再部署可以少踩安全坑；本文的加固清单与其一一对应。

## 1. 部署形态先想清楚：它是"云依赖工具"，不是纯离线工具

images2slides 的输出端是 **Google Slides 在线 API**，输入端是 **VLM 云服务**。所以"私有化"存在两个层级，部署前先明确你要哪一层：

| 层级 | 数据面 | 可行性 |
|------|--------|--------|
| **L1：本机/内网运行** | 图片与 layout.json 都在本机，仅调用 VLM API 与 Google API | 开箱即用（本文默认目标） |
| **L2：完全离线** | 全链路不出内网 | 需改造：VLM 换本地多模态模型 + 输出端从 Slides API 换成本地 pptx 生成器（见第 7 节） |

重要认知：**只要输出端还是 Google Slides，就不存在真正意义的"完全私有化"**——版式数据必然经过 Google API。敏感内容场景请直接规划 L2。

## 2. 基础环境

- **Python ≥ 3.11**（`pyproject.toml` 声明 `requires-python = ">=3.11"`，支持 3.11/3.12/3.13）
- **uv**（推荐）或 pip：`uv sync` 一键装齐核心依赖 + dev 组
- 操作系统：Linux / macOS / Windows 均可；服务器建议 Linux
- 无数据库、无常驻进程——每次运行是一次 CLI 命令，部署面非常小

核心依赖（`pyproject.toml` L18-30）：`google-api-python-client`、`google-auth*`、`google-cloud-storage`、`google-genai`、`pillow`、`click`、`python-dotenv`。注意两点依赖卫生问题：`polars` 仅为 `evaluation.py` 服务（只跑 CLI 可忽略），`pydantic` 声明了但源码未实际使用。

## 3. 凭证矩阵（部署的核心工作量）

### 3.1 VLM 侧（四选一，按 `--provider` 或 `VLM_PROVIDER`）

| Provider | 环境变量 | 说明 |
|----------|----------|------|
| google（默认） | `GOOGLE_API_KEY` | Gemini 系列 |
| openai | `OPENAI_API_KEY` | GPT-4V 系列 |
| anthropic | `ANTHROPIC_API_KEY` | Claude 系列 |
| openrouter | `OPENROUTER_API_KEY` | 聚合网关 |

可选依赖：openai / anthropic SDK 在 `[project.optional-dependencies].vlm` 组，需 `uv sync --extra vlm` 或 pip 安装；google/openrouter 用主依赖里的 SDK。模型名用 `VLM_MODEL` 或 `--model` 覆盖，不填走各 provider 默认值（`images2slides/vlm/extract.py:30-66`）。

### 3.2 Google Slides 侧（二选一）

| 方式 | 参数 / 环境变量 | 适用场景 |
|------|----------------|----------|
| OAuth 交互式 | `--client-secret` / `CLIENT_SECRET_PATH` | 开发机、有浏览器的环境 |
| 服务账号 | `--service-account` / `SERVICE_ACCOUNT_PATH` | **服务器首选**（无头环境无法弹浏览器，OAuth 的 `run_local_server` 会卡死） |

服务账号部署步骤：GCP 控制台建服务账号 → 启用 Slides API 与 Drive API → 下载 JSON key → 目标演示文稿与"目标文件夹"对该服务账号邮箱授权（服务账号创建的文稿归属于它自己，建议统一在一个共享 Drive 或由它复制到指定位置）。SCOPES 仅 `presentations`（`images2slides/auth.py:11`），权限面小，这是加分项。

### 3.3 GCS 侧（有图片区域时必需）

- `--gcs-bucket` / `GCS_BUCKET`：承接裁剪图上传（`cli/__main__.py:536-541`）
- 凭证复用 Google 侧的应用默认凭证（ADC）：服务账号方式下即同一个 key 文件，无需单独配置
- **上传策略（P0-2 已修复）**：默认返回 1 小时有效的 V4 签名 URL，bucket 可保持私有；签名需服务账号（或 IAM 签名权限），OAuth 用户凭证会签名失败并明确报错。确需旧行为时设置 `IMAGES2SLIDES_ALLOW_PUBLIC_UPLOAD=1` 显式回退为公读对象

## 4. 配置项总表

CLI 参数优先，其次环境变量，其次 `.env`（python-dotenv 自动加载，参考 `.env.example`）：

| 配置 | CLI | 环境变量 | 默认 |
|------|-----|----------|------|
| VLM 提供商 | `--provider` | `VLM_PROVIDER` | google |
| 模型 | `--model` | `VLM_MODEL` | 各家默认 |
| GCS bucket | `--gcs-bucket` | `GCS_BUCKET` | 无（跳过图片区域） |
| OAuth 密钥 | `--client-secret` | `CLIENT_SECRET_PATH` | 无 |
| 服务账号 | `--service-account` | `SERVICE_ACCOUNT_PATH` | 无 |
| 标题 | `--title` | — | Untitled Presentation |
| 页面比例 | `--page-size` | — | 16:9 |
| 中间产物 | `--save-layouts` | — | 不保存 |

退出码契约（`cli/__main__.py:35-39`）：`0` 成功 / `1` 校验错 / `2` API 错 / `3` 缺凭证 / `4` VLM 错——上层调度按这个写重试与告警逻辑。

## 5. 服务器部署最小步骤（Docker）

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
ENTRYPOINT ["uv", "run", "images2slides"]
```

```bash
# 运行示例（服务账号方式）
docker run --rm \
  -e SERVICE_ACCOUNT_PATH=/secrets/sa.json \
  -e GOOGLE_API_KEY=xxx \
  -v /srv/secrets:/secrets:ro \
  -v /srv/infographics:/data:ro \
  images2slides convert \
  --image /data/report.png \
  --title "月报" \
  --save-layouts /data/layouts
```

Docker 要点：密钥用只读挂载（`:ro`），绝不进镜像层；OAuth token 默认落在用户配置目录（P0-3 已修复），容器内可用 `--token-path` 或 `IMAGES2SLIDES_TOKEN_PATH` 指到挂载卷，避免随容器层丢失。

## 6. 安全加固清单（部署必查）

- [ ] P0-2（已修复）：默认签名 URL、bucket 保持私有；仅在有意识设置 `IMAGES2SLIDES_ALLOW_PUBLIC_UPLOAD=1` 时才产生公开对象
- [ ] P0-3（已修复）：token 默认落用户配置目录且权限 0600，可用 `IMAGES2SLIDES_TOKEN_PATH`/`--token-path` 重定向；服务器仍建议一律用服务账号（不产生 token.json）
- [ ] 服务账号 JSON key 权限 600，放入密钥管理系统或只读挂载
- [ ] VLM API key 通过环境变量/密钥服务注入，不写进 `.env` 入库
- [ ] GCS bucket 私有化审计：检查是否有历史 `make_public` 遗留的公开对象
- [ ] 出口网络：需放行 `*.googleapis.com`（Slides + GCS + Gemini）与所选 VLM 域名
- [ ] 日志级别注意：uploader 的 info 日志会输出公网 URL（`uploader.py:173`），接入日志平台前评估是否算数据出域

## 7. L2 完全离线路线（改造指引）

若要求全链路不出内网，需要两处替换，得益于分层架构都是"换实现"而非"重写"：

1. **VLM 侧**：实现一个本地 `VLMClient` Protocol（`vlm/extract.py:68`）——接 vLLM/Ollama 部署的开源多模态模型（如 Qwen-VL 系列），复用 `vlm/prompt.py` 的提示词与 `_parse_json_response` 的容错逻辑。风险点：开源小模型的 bbox 精度与 JSON 稳定性会显著低于 Gemini/GPT-4V，务必用 `evaluation.py` 跑一次基线对比再上线。
2. **输出侧**：放弃 Slides API，用 `python-pptx` 写一个本地后端——`build_requests_for_infographic()` 生成的请求 dict 已经是"元素清单"（类型/位置/尺寸/文本/样式齐全），翻译成 python-pptx 调用是直接的一层映射。改造后 `layout.json` 契约、全部纯函数层、测试资产原样保留。

顺带说明：第 2 条路线与《ppt-master-complement-analysis.md》的集成方向一致——如果集成 ppt-master 生态，输出端可以直接走它的 SVG→原生 pptx 管线，不必自己维护 python-pptx 后端。
