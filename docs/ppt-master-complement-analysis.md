# images2slides 对 ppt-master 的补充价值分析

> 分析对象：[hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)（约 68.7k stars，MIT，Python）与本项目 images2slides。
> 结论先行：两者是**互补关系而非竞争关系**——ppt-master 解决"从文档/主题生成原生 pptx"，images2slides 解决"从已有信息图图片还原可编辑版式"。images2slides 有 4 项能力可直接补进 ppt-master 生态，ppt-master 也有对应能力反哺本项目。

## 1. 两项目定位对比

| 维度 | images2slides | ppt-master |
|------|---------------|------------|
| 输入 | **已有的信息图/幻灯片图片** | 文档、主题、参考资料（PDF/DOCX/网页） |
| 输出 | Google Slides（在线、可编辑） | 原生 .pptx 文件（本地、可编辑） |
| 中间表示 | `layout.json`（px 坐标 + 区域列表） | SVG（作为页面设计语言）→ 原生 PPTX 对象 |
| 核心技术 | VLM 视觉抽取 + 坐标变换 + Slides API batchUpdate | Agent 工作流（skill）+ SVG→PPTX 转换器 + 模板体系 |
| 原生深度 | 文本框 + 图片两种元素 | 幻灯片母版、原生形状/连接符、数据图表、表格、动画、旁白 |
| 运行形态 | 独立 CLI（uv 运行） | 任意 Agent 工具内的 skill 工作流 + Python 脚本集 |
| 元素来源 | 从图片"逆向"恢复 | 从语义"正向"生成 |

关键洞察：**ppt-master 的所有路由都从"语义"出发（读文档、听主题），没有任何一条路由以"一张现成的版式图片"为输入**。而现实工作流里大量存量资产是图片形式：旧 PPT 截图、竞品海报、设计稿、白板照片。这正是 images2slides 的独有入口。

## 2. images2slides 可补充给 ppt-master 的四项能力

### 2.1 "图片 → 可编辑版式"缺失路由（价值最高）

ppt-master 能力矩阵中最明显的空白：给它一张信息图，它没有标准路径将其还原为可编辑 deck。images2slides 恰好把这件事做成了完整管线——VLM 提示词（`vlm/prompt.py`）、四家模型适配、bbox 容错裁剪（+10px padding）、6 步版式清洗，全部现成。

**接入形态建议**：做成 ppt-master 的一个新 workflow 路由（如 `image-to-deck`），上游复用 images2slides 的抽取段，下游直接对接 ppt-master 的 SVG 生成段——VLM 抽出的 region 列表转成 SVG 页面描述，再由 ppt-master 现成转换器输出原生 pptx。images2slides 侧无需大改：`--save-layouts` 产出的 layout.json 就是现成的交接格式。

### 2.2 layout.json：比 SVG 更轻的版式交接契约

images2slides 的 `layout.json` 是一个极简、可校验（`validator.py`）、可清洗（`postprocess.py` 6 步）、带置信度的中间格式。ppt-master 的 SVG 中间语言表达力强但重，且其技术设计文档明确将 SVG 定位为"项目内部语言"。

补充价值：当任务只是"保真还原一张图的版式"时，layout.json 比 SVG 更合适——不需要 SVG 的表达力，却自带 VLM 置信度（`confidence` 字段）和清洗流水线。两者可以共存：layout.json 管"逆向还原"，SVG 管"正向设计"。

### 2.3 评测闭环：IoU / CER / WER 基准

images2slides 自带 1,428 行的 `evaluation.py`：以人工标注为基准，量化区域定位（IoU）与文本还原（CER/WER）质量。ppt-master 的质量体系以 Agent 侧 quality gate + 人工审阅为主，**没有针对"视觉保真度"的量化基准**。

补充价值：image-to-deck 路由上线后，"还原得像不像"必须可量化才能迭代模型与提示词——这套基准可直接迁移。反过来 ppt-master 的 batch_validate 等质量门禁设计也值得 images2slides 借鉴（见第 3 节）。

### 2.4 Protocol 化扩展点的轻量范式

images2slides 用两个 Protocol（`VLMClient`、`Uploader`）+ 工厂函数实现扩展点，零依赖、可单测注入。ppt-master 的 executor-* 体系（executor-chart / executor-table / executor-image 等）功能更强但绑定其 Agent 工作流。做 image-to-deck 集成时，VLM 抽取段建议保持 images2slides 的轻量 Protocol 风格，避免把简单视觉抽取拖进重型执行器框架。

## 3. ppt-master 反哺 images2slides 的能力（对照参考）

| ppt-master 能力 | images2slides 现状 | 补充意义 |
|-----------------|-------------------|----------|
| 原生 chart / table | 仅文本框 + 图片两种元素 | VLM 识别出"这是图表"时，可生成原生可编辑图表而非贴图 |
| 幻灯片母版/版式（p:sldMaster 继承） | 纯 BLANK 版式 | 输出可套品牌模板，企业可用性大增 |
| 动画 / 转场 / 旁白 | 无 | 不影响主流程，属锦上添花 |
| 图片获取（AI 生图、网页图、水印处理） | 仅从原图裁剪 | 信息图中缺失/低清区域可 AI 补全后再贴 |
| quality gate / batch_validate | evaluation.py 偏离线批测 | 可借鉴其"门禁"形态做生成前拦截 |

其中**原生 chart/table**与**母版继承**两项含金量最高——它们把输出从"图片的影子"提升为"真正的原生幻灯片"，也是 ppt-master README 反复强调的差异化主张。

## 4. 建议集成路线图

**第一阶段（1-2 天量级）：验证契约对接**
用 `--save-layouts` 产出 2-3 张典型信息图的 layout.json，手工写一个 50 行左右的转换脚本，把 regions 映射为 python-pptx 调用（或 ppt-master 的 SVG 输入格式），验证"图片 → 原生 pptx"端到端可行。此阶段 images2slides 侧**零改动**。

**第二阶段：落地 image-to-deck 路由**
把验证脚本正式化：images2slides 侧暴露一个"抽取后不建 Slides、只交付 layout.json"的出口（现 CLI 已支持，加个 `--extract-only` 更明确）；ppt-master 侧在 workflows/routing.md 增加该路由的入口说明与示例。

**第三阶段：评测与模型选型闭环**
用 evaluation.py 对不同 VLM（Gemini/GPT/Claude + ppt-master 推荐的 Kimi K3 等）在 image-to-deck 场景跑 IoU/CER/WER 基准，用数据定抽取模型——images2slides 的四客户端架构使换模型只是一行配置。

## 5. 边界与风险

- **保真度天花板在 VLM**：图片还原的上限由视觉抽取精度决定，小字密集型信息图 CER 会明显上升，评测基准是刚需不是可选项。
- **输出目标不同**：images2slides 输出 Google Slides（在线协作强），ppt-master 输出本地 pptx（私有化强）。两条输出端可以并存——这也与《private-deployment-guide.md》的 L2 完全离线路线天然衔接。
- **许可兼容**：两者均 MIT，代码级互相取用无障碍。
- **维护节奏差异**：ppt-master 是 68k stars 的活跃大项目，images2slides 是 Alpha 小项目——集成方向应该是"images2slides 作为输入侧插件进入 ppt-master 生态"，而不是反向让大项目适配小项目。
