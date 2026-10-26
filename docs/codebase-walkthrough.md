# images2slides 代码结构与实现走读

> 本文面向"充分理解本仓库结构与具体实现"的目标，按分层架构组织，所有引用均标注文件与行号（基于 main@9d5abfb + 后续 docs 提交）。
> 配套文档：《images2slides-评估报告.md》（整体评估）、《p0-issues-explained.md》（关键问题详解）、《private-deployment-guide.md》（部署配置）。

## 1. 代码规模分布

| 位置 | 行数 | 职责 |
|------|------|------|
| `images2slides/`（核心包） | 2,415 | 管线全部核心逻辑 |
| ├─ `vlm/extract.py` | 558 | 4 家 VLM 客户端 |
| ├─ `build_slide.py` | 453 | 编排 + 请求构造 |
| ├─ `postprocess.py` | 416 | 版式清洗 7 步 + 质量检查 |
| ├─ `slides_api.py` | 221 | Slides API 请求纯构造 |
| ├─ `uploader.py` | 191 | 裁剪 + GCS 上传 |
| ├─ `models.py` | 187 | frozen dataclass 数据模型 |
| ├─ `validator.py` | 113 | JSON Schema 校验 |
| ├─ `geometry.py` | 61 | px→pt 坐标变换 |
| ├─ `auth.py` | 47 | Google 两种鉴权 |
| └─ `vlm/prompt.py` | 73 | 抽取提示词 |
| `cli/__main__.py` | 722 | click CLI，端到端管线 |
| `evaluation.py` | 1,428 | 评测基准（IoU/CER/WER） |
| `tests/`（8 个文件） | — | 131 个测试，0.4s 跑完 |

核心包不到 2,500 行就完成了"图片 → 可编辑在线幻灯片"的完整管线，理解成本集中在中游三个模块（postprocess、build_slide、vlm/extract）。

## 2. 分层架构：纯函数层与副作用层

这是本仓库最重要的结构特征，直接决定了可测试性与复用方式。

**纯函数层**（无 IO、无网络、输入输出确定，可随意组合与单测）：

- `models.py` —— 5 个 frozen dataclass：`BBoxPx`、`TextStyle`、`Region`、`ImageDimensions`、`Layout`。不可变保证数据在管线中不被意外篡改（L10/L44/L72/L126/L149）。
- `geometry.py` —— `compute_fit()`（L19）计算图片到幻灯片画布的等比缩放与居中偏移，返回 `Fit(scale, offset_x_pt, offset_y_pt, placed_w_pt, placed_h_pt)`；`bbox_px_to_pt()`（L47）把像素坐标换算成磅坐标。
- `validator.py` —— `validate_layout(data: dict) -> Layout`（L64）：把 VLM 返回的裸 dict 严格解析成 `Layout`，字段缺失/类型错误抛 `LayoutValidationError`。这是外部 JSON 与内部模型的唯一入口。
- `slides_api.py` —— `req_create_slide / req_create_image / req_create_textbox / req_insert_text / req_transparent_shape / req_text_style / req_delete_slide` 纯请求构造函数族，只产 dict，不碰网络。
- `postprocess.py` 前半部分 —— `trim_whitespace → normalize_spaces → drop_empty_regions → clamp_to_bounds → sort_by_reading_order → enforce_minimum_size` 六个纯变换 + `postprocess_layout()` 编排（L171）。

**副作用层**（封装一切 IO，全部可被 Protocol 替换）：

- `vlm/extract.py` —— `VLMClient` Protocol（L68）+ 4 个实现：`GoogleVLMClient`（L76）、`OpenAIVLMClient`（L187）、`AnthropicVLMClient`（L284）、`OpenRouterVLMClient`（L383），工厂 `get_vlm_client()`（L485）。
- `uploader.py` —— `Uploader` Protocol（L22）+ `GCSUploader` 实现（L38）。
- `auth.py` —— OAuth（`get_slides_service_oauth`，L14）与服务账号（`get_slides_service_sa`，L37）两条鉴权路径。
- `cli/__main__.py` —— 唯一的组装点，把上述两侧接成管线。

## 3. 端到端数据流

```
信息图 PNG
   │
   ▼
vlm/extract.py  extract_layout_from_image()          (L499)
   │  └─ 内部先调 VLM 拿原始 JSON，再立刻走 validator.validate_layout()  (L527)
   ▼
Layout (frozen dataclass)
   │
   ▼
postprocess.py  postprocess_layout()                 (L171)
   │  6 步清洗：去空白 → 归一空格 → 丢空区域 → 夹回画布 → 阅读序排序 → 最小尺寸
   ▼
cli  保存 layout.json（--save-layouts 可选，这就是对外集成契约）
   │
   ▼
uploader.py  crop_and_upload_regions()               (L136)
   │  每个 image 区域裁剪（+10px 右下 padding 补偿 VLM 边框收紧，L111-112）
   │  SHA256 前 16 位做内容哈希 → 对象名 {prefix}{region.id}_{hash}.png   (L170)
   ▼
dict[region.id → 公网 URL]
   │
   ▼
geometry.py  compute_fit()                           (每张图一次)
   │
   ▼
build_slide.py  build_requests_for_infographic()     (L66)
   │  文本区域：字体非线性放大（L121-126）+ 右向扩宽防重叠（L134-150）
   │  图片区域：IMG_{region.id} + 裁剪图 URL
   │  全部 requestId 确定性生成：SLIDE_{i:03d} / BG_ / TXT_ / IMG_ 前缀
   ▼
slides_api.py 请求 dict 列表 → apply_requests() 一次 batchUpdate  (L185)
   ▼
Google Slides 演示文稿（在线、可编辑）
```

两个关键衔接点值得记住：**layout.json 是管线的中间契约**（前后端可各自替换），**region.id 贯穿全链**（裁剪命名、URL 映射、Slides objectId 都由它派生——这也是 P0-1 id 唯一性问题的根源，详见 p0-issues-explained.md）。

## 4. 模块逐个详解

### 4.1 vlm/extract.py —— 四客户端同构

`VLMConfig`（L30）持有 provider/model，`get_api_key()`（L51）按 provider 映射环境变量：`GOOGLE_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENROUTER_API_KEY`。四个客户端类的 `extract_layout()` 结构完全同构：读图 → 编码 → 调 API → `_parse_json_response()` 剥壳取 JSON。差异只在 SDK 调用细节——这正是评估报告指出"约 75% 重复代码、可收敛为一个基类 + 差异点"的依据。`_parse_json_response` 各家都做了容错（剥 markdown 代码围栏等），LLM 输出格式抖动是真实痛点。

### 4.2 postprocess.py —— 两个"validate_layout"

本模块有 416 行，一半是清洗管线，一半是质量检查工具，**注意同名冲突**：

- `postprocess.validate_layout(layout, confidence_threshold=0.7, iou_threshold=0.3)`（L295）：返回 `ValidationWarning` 列表，做的是"质量体检"（低置信度、区域重叠 IoU>0.3 等），**不是** validator.py 的强校验。两函数同名不同义，导入时极易混淆。
- `compute_bbox_iou()`（L212）是独立的 IoU 实现，evaluation.py 的基准指标也用它。
- `get_layout_statistics()`（L385）输出区域数/密度等统计，供评测报告用。

### 4.3 build_slide.py —— 编排与字体补偿

除编排外有两个值得细看的实现：

- **字体非线性放大**（L121-126）：`scaled = base * scale + max(0, (14 - base*scale) * 0.294)`，小字号获得 boost、14pt 以上不变，补偿缩放后小字在投影场景不可读的问题。
- **右向扩宽防重叠**（L134-150）：文本框先按字体放大的比例算期望宽度，再逐个检查右侧垂直重叠的区域，把右边界压到邻居左边界 -2pt，下限仍不小于原宽度。这是"VLM 给的文本框偏窄"的经验性修复。

批量路径 `build_presentation()`（L336）把所有 slide 的请求合成**一次** `batchUpdate`（L404），并用 `insertionIndex = i`（L398）保证顺序——原子性好，但也是"一个 region id 重复就全盘 400"的原因。

### 4.4 uploader.py —— 裁剪与上传

`crop_region_png()`（L91）裁剪时右、下各加 10px padding 补偿 VLM 边框系统性收紧；`get_file_hash()`（L120）以内容 SHA256 前 16 位参与对象命名，天然去重（同图同区域不重复占空间）。`GCSUploader.upload_png()`（L60）上传后 `blob.make_public()`（L81）——P0-2 安全问题的位置，详见问题详解文档。

### 4.5 auth.py —— 两条鉴权路径

OAuth 交互式（`InstalledAppFlow.run_local_server`，需本地浏览器）与服务账号静默（适合服务器）。`token_path` 默认 `"token.json"` 相对路径（L14）——P0-3 的位置。SCOPES 仅 `presentations`，权限面本身收得很小。

### 4.6 cli/__main__.py —— 四步管线与退出码

`convert` 命令（L554 起）按 4 步推进：①VLM 逐图分析（L611）→ ②裁剪上传（L643，无 bucket 时降级为跳过图片区域并提示，L667-674）→ ③鉴权（L679）→ ④建演示文稿（L689）。退出码契约：`0` 成功 / `1` 校验错 / `2` API 错 / `3` 缺凭证 / `4` VLM 错（L35-39）。注意 Step 2 中单个区域上传失败会让整个进程退出（L664-666）——P0-4 的位置。

### 4.7 evaluation.py —— 自建评测闭环

仓库根的单文件 1,428 行基准系统（`uv run python evaluation.py`）：对样例图跑管线，与人工标注比对，输出 IoU（框重叠度）、CER（字符错误率）、WER（词错误率）。依赖 `polars` 做结果聚合——这就是"polars 重依赖仅为评测服务"结论的出处。这份基准的存在让"改了 prompt/换了模型之后效果变好还是变坏"有数可依，是同类脚本项目里少见的工程习惯。

## 5. 关键设计决策速查

| 决策 | 位置 | 收益 |
|------|------|------|
| frozen dataclass 不可变模型 | models.py 全部 | 管线中数据不被意外篡改 |
| Protocol 化 VLMClient / Uploader | extract.py L68 / uploader.py L22 | 扩展点清晰，测试可注入假实现 |
| layout.json 中间契约 | cli L628 + --save-layouts | 前后端解耦，可缓存、可复现、可对接外部系统 |
| 确定性对象 ID（TXT_/IMG_/BG_ 前缀） | build_slide L93/L115/L172 | 重跑结果可 diff，不产生幽灵元素 |
| 单次 batchUpdate | build_slide L404 | 原子性好，无半成品状态 |
| 内容哈希对象命名 | uploader L120-133/L170 | 同图重跑不重复占存储 |
| 评测闭环 | evaluation.py | 模型/提示词改动可量化对比 |

## 6. 建议阅读顺序（约 30-40 分钟）

1. `models.py`（187 行，5 分钟）—— 先认识数据形状，后面一切都在搬运它
2. `geometry.py`（61 行，3 分钟）—— 理解 px→pt 的一次性变换
3. `validator.py`（113 行，5 分钟）—— 外部 JSON 如何变成内部模型
4. `slides_api.py`（221 行，8 分钟）—— 认识 Slides API 请求的最小集合
5. `build_slide.py` 的 `build_requests_for_infographic()`（L66-182，10 分钟）—— 管线的"大脑"
6. `postprocess.py` 的 `postprocess_layout()`（L171-190）+ `vlm/prompt.py`（73 行）—— 清洗策略与提示词
7. `cli/__main__.py` 的 `convert`（L554-718）—— 最后看组装，把前面所有模块串起来
8. 需要换模型/调效果时再深入 `vlm/extract.py` 与 `evaluation.py`

读完这条路径后，再看 `feat/saas/*` 四个实验分支的 diff，就能清楚看到作者在 SaaS 化方向上尝试了哪些不同取舍（不同 AI 模型生成的实现差异本身就具有参考价值）。
