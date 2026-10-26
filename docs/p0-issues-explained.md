# 四条 P0 问题详解

> 本文对评估报告中 4 条 P0（最高优先级）问题逐条展开：问题是什么、代码证据在哪、实际后果是什么、怎么修。
> 行号基于 main@9d5abfb。修复时请遵循仓库协作规则：最小 diff、`fix:` 前缀、不夹带重命名。

## P0-1：region id 唯一性校验缺失

### 问题是什么

`layout.json` 中每个 region 都有 `id` 字段，它是全链路的主键：裁剪图命名、URL 映射、Slides API 对象 ID 都由它派生。但校验器**只检查 id 存在，从不检查唯一**。而 region.id 由 VLM 生成——大模型在长列表中输出重复 id 是常见现象，当前防线挡不住。

### 代码证据

- `images2slides/validator.py:35-61`：`_validate_region()` 检查了 `id` 存在（L39-40）、`type` 合法（L43-44）、`bbox_px` 存在（L45-46），唯独没有唯一性检查。
- `images2slides/validator.py:93`：`validate_layout()` 直接 `tuple(_validate_region(r, i) for ...)` 逐个解析，无去重。
- `images2slides/postprocess.py`：6 步清洗全部透传 `r.id`（L27/L58/L109/L155），不做补偿。

### 实际后果（两条故障路径）

**路径 A——整个 batchUpdate 直接 400**：`build_slide.py:115` 与 `:172` 用 `f"TXT_{region.id}"` / `f"IMG_{region.id}"` 当 Slides API 的 `objectId`。同一张幻灯片里出现重复 objectId 时，Google API 拒绝整个 batchUpdate（`objectId` 必须在全演示文稿内唯一）——由于 `build_presentation()` 把所有 slide 的请求合并成一次 batchUpdate（`build_slide.py:404`），**一个重复 id 报废整份演示文稿**，且用户已付出 VLM 调用成本。

**路径 B——更隐蔽的静默错图**：`uploader.py:172` 用 `cropped_urls[region.id] = url` 按 id 写 dict，重复 id 时后者覆盖前者；`build_slide.py:174` 再按 id 取 URL。结果两个不同区域里，一个贴上另一个区域的图——不报错、不可察觉，直到有人发现幻灯片上图片内容对不上文字。

### 建议修复

在 `validate_layout()` 解析完 regions 后加一行聚合检查（约 3 行 diff）：

```python
ids = [r.id for r in regions]
if len(ids) != len(set(ids)):
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    raise LayoutValidationError(f"Duplicate region ids: {dupes}")
```

配套在 `tests/` 加两个用例：重复 id 抛错；错误消息包含重复的 id 值。

---

## P0-2：GCS `make_public()` 公开上传裁剪图

### 问题是什么

图片区域生成幻灯片前要先裁剪并上传到 GCS。当前实现把每个裁剪图设为**公读**，返回**永久公开**的 URL。信息图往往包含业务数据、内部流程、客户案例——这些切片从此对全网可见，且没有过期时间。公开是不必要的安全让步：Slides API 创建图片元素时只需要 URL 在**当时**可被 Google 服务端抓取一次，并不要求永久公开。

### 代码证据

- `images2slides/uploader.py:80-86`：

```python
try:
    bucket = self._client.blob(object_name)
    ...
    blob.make_public()
except Exception:
    # Uniform bucket-level access enabled - assume bucket is already public
    logger.debug("Could not set object ACL (uniform access?), using public URL anyway")

return blob.public_url
```

注意异常分支：即使 `make_public()` 失败（bucket 启用统一访问控制），代码也只是记一条 debug 日志，然后**照样返回公网 URL**（L86）——把"对象级设为公读失败"默认成"bucket 级已经是公读"，这个假设一旦不成立，Slides API 拉图就会 403。

### 实际后果

1. 裁剪图永久公开可枚举访问（`storage.googleapis.com/<bucket>/<object>`），搜索引擎可收录，无审计痕迹；
2. bucket 必须允许公读，违反最小权限原则；
3. 企业场景直接不可用——这是把工具推向生产的第一道门槛。

### 建议修复

改用 **V4 签名 URL** 替代 `make_public()` + `public_url`：

```python
from datetime import timedelta

url = blob.generate_signed_url(
    version="v4",
    expiration=timedelta(hours=1),
    method="GET",
)
```

要点：bucket 保持私有；签名 URL 有效期覆盖"上传 → batchUpdate 抓取"这一窗口即可（Slides API 在创建图片元素时抓取一次，之后图片内容已在 Slides 服务内）；`generate_signed_url` 需要可签名的凭证——服务账号开箱即用，OAuth 用户凭证路径需配置 `google-auth` 的签名支持（或直接推荐服务账号方式）。同时删除"异常分支照样返回 public_url"的逻辑，改为显式报错。

---

## P0-3：OAuth token 明文落当前工作目录

### 问题是什么

OAuth 鉴权成功后，凭证（含 `refresh_token`）以**明文 JSON** 写入**当前工作目录**下的 `token.json`。CWD 是最不可控的位置：在哪个目录启动命令，凭证就落在哪。

### 代码证据

- `images2slides/auth.py:14`：`def get_slides_service_oauth(client_secret_path: str, token_path: str = "token.json")` —— 默认值是相对路径；
- `images2slides/auth.py:31-32`：`open(token_path, "w")` + `f.write(creds.to_json())` —— 明文写入，无权限收紧；
- `cli/__main__.py:683`：`service = get_slides_service_oauth(client_secret)` —— CLI 调用时**没有传 `token_path`**，永远走默认 CWD。

### 实际后果与已有缓解

`.gitignore` 已忽略 `token.json`，意外的 `git commit` 大概率被挡住——这是**唯一**的既有缓解。但明文凭证放在 CWD 仍有真实暴露面：

- 换目录运行 = 到处散落 token 副本（`~/a/token.json`、`~/b/token.json`…），难清理、难审计；
- 打包/备份/共享工作目录时容易连带带走；
- `git add -f`、某些 IDE 的"全部添加"、目录整体拷贝都会绕过 gitignore；
- `refresh_token` 有效期长，泄露后攻击者可长期换取新 access token。

### 建议修复

1. 默认路径改为用户配置目录：Linux/macOS 用 `~/.config/images2slides/token.json`（或引入 `platformdirs` 跨平台取 `user_config_dir`）；
2. 写入时收紧权限：`os.chmod(token_path, 0o600)`（Windows 上对应 ACL 语义由文件系统处理）；
3. 允许环境变量覆盖（如 `IMAGES2SLIDES_TOKEN_PATH`），CLI 加 `--token-path` 选项透传；
4. `token.json` 已在 `.gitignore`，保持即可。

---

## P0-4：单个区域上传失败中止整个转换

### 问题是什么

VLM 抽取（整条管线中最贵、最慢的一步）成功之后，任何一个图片区域裁剪或上传失败，CLI 直接退出，所有已完成的抽取成果作废。而"完全没配 bucket"的情况反而能优雅降级（跳过图片区域、继续生成文本幻灯片）——**降级能力存在，只是没接到"部分失败"这个最常见的故障形态上**。

### 代码证据

- `images2slides/uploader.py:167-176`：`crop_and_upload_regions()` 循环内 `except UploadError` 后 `logger.error(...)` 然后 `raise`——**第一个**失败的区域中断剩余所有区域；
- `cli/__main__.py:664-666`：

```python
except UploadError as e:
    click.echo(f"Image upload error: {e}", err=True)
    sys.exit(EXIT_API_ERROR)
```

—— CLI 捕获后整体退出，前面已完成的全部 layout 丢弃；
- 对比无 bucket 的降级路径 `cli/__main__.py:667-674`：提示"Image regions will be skipped"后继续构建——说明设计者认可"图片缺失仍可交付"的产品语义。

### 实际后果

一张 10 图的信息图，第 9 个区域上传超时 → 前面 8 个的成功上传与全部文本抽取全部作废，重跑还要再花一遍 VLM 费用。失败概率随区域数线性上升，成本浪费同样线性上升。

### 建议修复

两层改造，保持最小侵入：

1. **uploader 层**：`crop_and_upload_regions()` 把"一票否决"改为"收集失败"——单区域 try/except，失败记入返回结构（如返回 `(cropped_urls, failed_region_ids)` 元组，或 logger.warning 后继续），循环不中断；
2. **CLI 层**：失败区域数 > 0 时不再 `sys.exit`，而是在最终汇总里明确列出哪些区域被跳过（沿用无 bucket 路径的用户提示语风格）；可选进阶：为失败区域落一个空占位（文本框标注"[图片上传失败]"），保证版式完整性可人工补；
3. **退出码**：引入"部分成功"语义（如复用 `EXIT_SUCCESS` 但打印明确 warning 汇总，或新增退出码 5），便于上游脚本区分"全成/部分/全败"。

修复时注意保持 `Uploader` Protocol 语义不变——只改调用方编排，不动接口签名（遵循协作规则 7：不夹带重构）。

---

## 修复优先级与顺序建议

| 顺序 | 问题 | 理由 |
|------|------|------|
| 1 | P0-1 id 唯一性 | 3 行 diff，挡住"整份文稿报废"的最高频故障 |
| 2 | P0-4 上传降级 | 复用既有降级语义，直接降低使用成本 |
| 3 | P0-3 token 路径 | 改动小，安全收益明确 |
| 4 | P0-2 签名 URL | 涉及凭证类型约束（签名需要服务账号），宜单独一个 `fix:` 提交并更新部署文档 |

四条都完成后，建议各补 1-2 个测试用例并跑 `uv run pytest` 与 `uv run python evaluation.py` 确认无回归。
