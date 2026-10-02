# Architecture Flow Map Skill

项目迭代久了，人会对整体结构失去把握。这个 Skill 让 Agent 读真实的代码和配置，产出一个可以打开、缩放、点击的单文件 HTML 地图：先看全局模块和数据，再展开某个模块，再挑一个关键场景按"上一步 / 下一步"逐步回放，每一步高亮涉及的节点和连线，并用中文说明发生了什么。

它和普通的"画架构图"有两点不同：

- **每条关系都要有出处。** 节点、连线、步骤都标明"已确认 / 推断 / 待确认"，并附 `路径:行号 · 符号`。构建脚本会到仓库里逐条核对：路径不存在、行号越界、符号不在所写的那一行，都会让构建失败，错误的引用到不了读者面前。实际运行过的命令和结果也可以作为证据记录。
- **数据和展示分开。** Agent 只写一个 `map.json`；查看器是固定模板，不随项目重写。代码改了以后重新构建，过时的引用会自动报出来。

## 用法

安装：

```bash
npx skills add a1024053774/architecture-flow-map-skill@architecture-flow-map -g -y --agent claude-code
```

`--agent` 换成你用的工具；不加时 CLI 会尝试装到所有已知工具，其中个别工具失败会报 `Failed to install`，不影响已装好的那些。

然后直接说：

```text
用 architecture-flow-map 帮我梳理这个项目现在怎么运转。
我最关心：用户下单、退款回调。我不理解：为什么订单状态会被两个地方改。
```

关心的场景和不理解的关系都可以不写，Agent 会自己从代码里挑 3–5 个场景。默认输出到目标仓库的 `docs/flow-map/`（`map.json` 和 `index.html`）。

构建命令（Agent 会自己运行）：

```bash
python3 architecture-flow-map/scripts/build_map.py --root <仓库> --data <目录>/map.json --out <目录>/index.html
```

`index.html` 是自包含文件，不依赖网络。少数内嵌浏览器会把 `file://` 页面当静态快照显示，点击没反应时用 `python3 -m http.server --directory <目录>` 起一个本地服务再打开。

## 查看器能做什么

- 画布可滚轮缩放、拖动平移、一键重置；按屏幕宽高自动选择横向或纵向排布。
- 点击节点看职责、关联业务对象、代码位置（可复制）、进出连线；有内部组件的模块可以展开，面包屑返回全局。
- 选择场景后用按钮或 ← → 键逐步回放；每一步列出数据的增删改查、失败处理与分支、依据。
- 实线是同步调用，虚线是异步（事件、队列、回调），点线是数据读写；虚框和 `？` 标出推断与待确认。
- 首页汇总"尚未确认与推断"和"文档与实现的差异"，影响超出"文档写错"的条目（例如未发布的数据可以匿名查到）标红并排在最前；地址栏记住当前场景和步骤，方便把链接发给别人。
- 窗口宽度小于 1400px 时，详情面板改为盖在画布上的抽屉，画布保持宽度；默认缩放不低于让节点文字约 12px 的比例。
- 页面内置 `await flowMapSelfCheck()`：用真实控件走完每个场景的每一步、展开每个模块，对照 `map.json` 检查高亮是否正确，并报告文字大小和连线说明的重叠数。任何浏览器工具执行这一行即可，不必猜页面结构。

## 相比原提示词改了什么

原始提示词来自 [@LinearUncle 在 X 上的分享](https://x.com/LinearUncle/status/2105506429788422409)，方向很好。做成 Skill 时调整了这些地方：

| 原提示词 | 这个 Skill |
| --- | --- |
| 要求"能追溯到代码"，靠 Agent 自觉 | 构建脚本逐条核对路径、行号和符号，不通过就不生成 HTML |
| "区分已确认、推断、未确认" | 三档各有硬性要求：确认要有引用，推断要写依据，未确认要写需要什么证据 |
| 每次让 Agent 自己选实现方式 | 固定查看器模板加数据格式，Agent 只写数据，结果稳定、可重建 |
| 不要把所有文件画成节点 | 给出预算：全局 6–14 个节点，模块内部最多 12 个，超出会警告 |
| 区分同步、异步和数据流 | 三种连线各有方向约定，数据连线的箭头沿数据流动方向 |
| 完成后自查 | 页面内置自检函数，一行调用完成交互检查；自检未通过就不能报 `PASS` |
| 项目迭代后地图会过时 | 重新构建即可发现失效引用，`map.json` 是唯一事实来源 |

## 目录

```text
architecture-flow-map/
  SKILL.md                       # 不可违反的核心、证据规则和流程概要
  references/tracing.md          # 第 1–4 步：摸底、选全局节点、挑场景、沿代码追踪
  references/build-and-check.md  # 第 6–8 步：构建、浏览器自检、汇报；更新已有地图
  references/map-schema.md       # map.json 格式
  assets/viewer.html             # 查看器模板（无外部依赖）
  scripts/build_map.py           # 校验并生成 HTML
examples/project-map/            # 对 project-map-skill 的完整示例
tests/build_map_e2e.sh           # 构建脚本的验收测试
```

## 验证

```bash
bash tests/build_map_e2e.sh
python3 architecture-flow-map/scripts/build_map.py --root ../project-map-skill --data examples/project-map/map.json --out examples/project-map/flow-map.html
```

第一条在临时目录里搭一个小仓库，确认正确的地图能构建，19 种错误地图（路径不存在、符号不在所写的行、推断没写依据、实测没写结果、步骤引用了不存在的连线等）都被拒绝，失败的构建不会覆盖已有的 HTML，地图文字里的 `</script>` 也无法提前结束数据块，过长的连线说明会得到警告。第二条重建示例，需要把 [project-map-skill](https://github.com/a1024053774/project-map-skill) 检出在同级目录，示例对应它的 `c16779a` 提交。
