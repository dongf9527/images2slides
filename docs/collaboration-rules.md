# GitHub 协作规则

> **适用范围**：`dongf9527/images2slides` 仓库的全部协作改动，人工开发与 AI 辅助协作均需遵守。
> **文档自身**：本文件即遵循规则 1 / 3 / 4 —— 存放于 `docs/`，以 Markdown 维护，通过 `git commit` + `git push` 更新（commit 类型使用 `docs:`）。

## 规则总览

| # | 规则 | 核心要求 |
|---|------|----------|
| 1 | 唯一同步方式 | 所有代码/文档改动通过 `git commit` + `git push` 推送到 GitHub，不在对话中凭空产生代码 |
| 2 | 仓库位置 | 严格使用沙箱中的根目录 `/home/z/my-project/repo-images2slides`，不在其他目录创建 `.git` |
| 3 | 提交规范 | 小步提交，commit message 使用 conventional commits 风格（如 `feat:`、`fix:`、`docs:`） |
| 4 | 会话记录 | 分析/评估/测试记录写入 `docs/` 目录，以 Markdown 形式提交推送 |
| 5 | 禁止 force push | 绝不使用 `git push --force`；同理禁止对已推送 commit 执行 `--amend` 后再推送（等效 force，同样触犯本条）；未推送 commit 的 amend 属修正笔误常规手段，不受限 |
| 6 | Rebase 前置 | rebase 前先评估替代方案（revert/merge），必要时提前告知确认 |
| 7 | bug 修复不重命名变量 | 修复 bug 时保持原变量名，仅在 refactor 时重命名 |

## 详细说明

### 规则 1：唯一同步方式

**要求**：所有代码与文档改动，必须经过「写入仓库文件 → `git commit` → `git push`」这一条路径进入 GitHub。对话中口头描述的方案、临时粘贴的代码片段不构成正式交付；只有落盘到仓库并推送成功后，对应工作才算完成。

**理由**：对话内容没有版本化、不可追溯、无法回滚。以 git 作为唯一同步通道，可以保证仓库历史与实际工作一一对应——出问题时能按 commit 二分定位、精确回滚，也便于任何协作者（包括 AI）从远端仓库恢复完整上下文。

**执行要点**：

- 任何"已完成"的结论，必须能对应到一个已推送的 commit；
- 需要在对话中展示代码时，代码本身应以仓库内文件为准，对话中只做引用或摘录；
- 不绕过仓库交付：不把"生成一份代码发给你"当作产出形式，产出即提交。

### 规则 2：仓库位置

**要求**：一切 git 操作只在沙箱根目录 `/home/z/my-project/repo-images2slides` 内进行。这是 `dongf9527/images2slides` 在本环境中唯一的工作副本，不得在任何其他目录执行 `git init` 或创建 `.git`。

**理由**：多份副本会让改动分散、状态互相覆盖；push 错分支或 push 错仓库的事故，绝大多数源于"在错误目录里执行了 git 命令"。固定唯一仓库位置可以从根上消除这类风险。

**执行要点**：

- 所有 git 命令建议使用 `git -C /home/z/my-project/repo-images2slides <子命令>`，或执行前确认当前目录正确；
- 新增文件一律放进该目录的对应子路径（文档放 `docs/`，脚本放 `scripts/` 等约定位置）；
- 需要隔离实验时，使用分支（如 `scratch/<主题>`）而不是新建目录副本。

### 规则 3：提交规范

**要求**：小步提交——一个 commit 只做一件事；commit message 使用 conventional commits 风格，格式为 `<类型>: <简短描述>`。

**理由**：小步提交让每次改动可单独审查、可单独回滚；统一的 message 格式让 `git log` 保持可读，也为后续自动生成 changelog 留下可能。

**常用类型**：

| 类型 | 用途 | 示例 |
|------|------|------|
| `feat:` | 新功能 | `feat: support signed URLs for GCS uploads` |
| `fix:` | 缺陷修复 | `fix: prevent overlap between adjacent text boxes` |
| `docs:` | 文档变更 | `docs: add collaboration rules` |
| `refactor:` | 重构（不改行为） | `refactor: deduplicate VLM client request logic` |
| `test:` | 测试补充或修改 | `test: add CLI end-to-end smoke tests` |
| `chore:` | 构建、依赖、杂项 | `chore: remove unused pydantic dependency` |

**执行要点**：

- 标题行使用祈使句、建议不超过 50 字；需要展开时空一行写正文，说明"为什么改"；
- `feat` 与 `fix` 对应的 issue/编号可附在正文或脚注中。

### 规则 4：会话记录

**要求**：分析、评估、测试等过程性工作的最终记录，写入 `docs/` 目录并以 Markdown 形式提交推送，避免结论只存在于对话中。

**理由**：对话会过期、会被截断，`docs/` 里的 Markdown 不会。把结论沉淀进仓库后，后续协作者（包括新的 AI 会话）无需重做同样的分析即可继承完整上下文。

**执行要点**：

- 评估/调研报告 → `docs/`（现有先例：`docs/images2slides-评估报告.md`）；
- 测试记录、实验结论、问题排查记录同样入库，一事一档；
- 文件名建议使用英文 kebab-case（如 `collaboration-rules.md`）或明确的中文名，正文以中文书写；
- 记录应包含：背景、做了什么、结论、下一步建议。

### 规则 5：禁止 force push

**要求**：绝不执行 `git push --force`。同理，**禁止对已推送的 commit 执行 `--amend` 后再推送**——这等效于改写远端历史，同样触犯本条。未推送的本地 commit 使用 `--amend` 修正笔误属于常规手段，不受本条限制。

**理由**：force push 会抹掉远端历史，其他协作者的本地分支将与远端错位，严重时直接丢失他人提交。本仓库的提交历史同时承担"工作档案"职责（如评估报告中的 git 考古结论），必须保持只追加、不改写。

**执行要点**：

- push 被拒（non-fast-forward）时，先 `git fetch` 并分析差异，用 merge 或叠加新 commit 解决，绝不通过 force "绕过"冲突；
- 已推送 commit 需要修改时，用新的 `fix:` / `revert:` commit 叠加修正；
- 未推送 commit 的提交信息写错（如类型用错），可直接 `--amend` 后再首次推送。

### 规则 6：Rebase 前置评估

**要求**：执行 rebase 之前，先评估替代方案——`git revert`（以新提交撤销历史）或 `git merge`（不改写历史的合并）。确有理由需要 rebase 时，提前说明理由并获得确认，尤其是涉及已推送的共享分支时。

**理由**：rebase 会改写提交历史，对已推送分支执行会制造与规则 5 相同的后果。revert 与 merge 不改写历史，在绝大多数场景下已经足够；把 rebase 作为"需要确认的特殊手段"而非默认动作，可以避免误操作。

**执行要点**：

- 默认优先级：能 revert 不 rebase，能 merge 不 rebase；
- rebase 仅限整理"尚未推送的本地提交"，或确认无他人基于该分支工作时；
- 执行前先留备份引用：`git branch backup/<分支名>`，以便随时恢复；
- 对远端分支的 rebase 类操作（含 PR 内 squash 后重推）一律先确认。

### 规则 7：bug 修复不重命名变量

**要求**：修复 bug 时保持原变量名、函数签名与既有代码风格，diff 只包含让 bug 消失所必需的最小改动；重命名、结构调整留给单独的 `refactor:` 提交。

**理由**：把重命名混入 bug 修复，会让 diff 噪声远大于实质变更——review 时难以确认"修复本身是否正确"，重命名过程也可能顺手引入新问题。纯粹的 `fix:` commit 应当能被单独理解、单独回滚，且不波及其他行为。

**执行要点**：

- `fix:` commit 的每一行 diff 都应能回答"这一行如何让 bug 消失"；
- 确需重命名时拆成两个 commit：先 `refactor:`（仅改名，不改行为），再 `fix:`（最小修复）；
- 顺手"优化一下"不属于 bug 修复范围，另开任务或另提 commit。

## 提交前自查清单

每次 push 之前逐项确认：

- [ ] 改动全部在 `/home/z/my-project/repo-images2slides` 内完成，未在其他目录创建 `.git`（规则 2）
- [ ] 一个 commit 只做一件事，message 符合 conventional commits（规则 3）
- [ ] 过程性分析/评估/测试记录已沉淀为 `docs/` 下的 Markdown（规则 4）
- [ ] 未使用 `--force`，未 amend 任何已推送的 commit（规则 5）
- [ ] 如涉及 rebase：已评估 revert/merge 替代方案，必要时已获得确认（规则 6）
- [ ] bug 修复未夹带变量重命名或结构调整（规则 7）
