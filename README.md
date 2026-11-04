# TopBrokers - 全球外汇与差价合约经纪商数据库 (Docs as Code)

本项目是【开户通】（`we.laowei8.com`）与经纪商评测库的 GitOps 版本控制仓库。
每个外汇/CFD 经纪商维护一份独立的 Markdown 文件，通过标准化的 YAML Frontmatter 记录 16 大比价参数、SEO 标签与 REHub 口碑评分，并保留详实的实盘评测长文。

---

## 目录结构

```text
topbrokers/
├── brokers/                      # 经纪商评测 Markdown 库（扁平存放，如 exness-review.md）
├── images/                       # 视觉资产库（Broker Logo、实盘点差截图、监管牌照图）
├── scripts/                      # 自动化工具集
│   ├── sync_to_wordpress.py      # 将 Markdown 文件单向推送到 WordPress/WooCommerce
│   └── export_from_wordpress.py  # 从 WordPress 批量拉取已有经纪商并转为 Markdown
├── template.md                   # 标准化 Broker 评测规范与范例模板
└── README.md
```

---

## 核心规范要求

1. **返佣外链规范**：
   * 所有 `external_url` 统一使用短链形式：`https://s.ssgg.net/xxxx`（如 `https://s.ssgg.net/exness`、`https://s.ssgg.net/pepperstone`）。
2. **站内内链网络构建（SEO 刚性要求）**：
   * 每篇评测正文必须嵌入 **3~5 个高相关站内内链**，链接到本站的比价大表（`/compare`）、ECN榜单（`/best-ecn-brokers.html`）、小资金榜单（`/brokers-in-small-account.html`）或监管防骗指南（`/fca-details.html`、`/last-fake-forex-brokers.html`），打通全站权重流转。
3. **文内双节点开户号召（CTA Buttons）**：
   * 正文内必须设置 **2 处黄金 CTA 节点**（采用 Gutenberg Button Block）：
     * 节点 1：在“点差与成本算账”章节之后（欲望最强时）；
     * 节点 2：在全文末尾 FAQ 之前（总结陈词完毕后）。
4. **REHub 16 大属性必填**：
   * 注册地、监管机构、成立时间、经营模式、最低入金、入金方式、出金优惠、**主要点差（必须写具体数值，如黄金 1.2 欧美 0.8）**、点差类型、交易品种、交易软件、最大杠杆、最小头寸、爆仓比例、可锁仓？、剥头皮？。
3. **内容去 AI 味**：
   * 采用全职交易员实盘视角，客观不盲目吹捧，必须明确列出 1~2 条真实缺点（Cons）以建立公信力。

---

## 常用操作命令

### 1. 演练模式预览（不实际写入线上）
```bash
python3 scripts/sync_to_wordpress.py brokers/pepperstone.md --dry-run
```

### 2. 单篇更新并一键发布至开户通
```bash
python3 scripts/sync_to_wordpress.py brokers/pepperstone.md
```

### 3. 从线上拉取某个已有产品并生成 Markdown
```bash
python3 scripts/export_from_wordpress.py 28711
```
