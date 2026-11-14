#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WordPress / REHub Broker 自动化同步脚本 (原生 Gutenberg Block 引擎)
将 Markdown 文件解析并推送到 we.laowei8.com (开户通) WooCommerce 产品库，
所有文本与模块严格转换为 WordPress 官方原生 Block 结构。
"""

import sys
import os
import re
import json
import urllib.request
import urllib.error
import yaml
import markdown

URL = os.environ.get("WPMCP_URL", "https://we.laowei8.com/wp-json/easy-mcp-ai/v1/mcp")
TOKEN = os.environ.get("WPMCP_TOKEN", "wpmcp_2d0029f0d996549108aba68d86429215c4f04744a9e6a6eb539188298d0ef22f")

# 16 大 REHub 全局属性映射表 (Attribute Name -> ID & Slug)
GLOBAL_ATTR_MAP = {
    "主要点差": {"id": 16, "slug": "pa_主要点差"},
    "交易品种": {"id": 13, "slug": "pa_交易品种"},
    "交易软件": {"id": 6,  "slug": "pa_交易软件"},
    "入金方式": {"id": 8,  "slug": "pa_入金方式"},
    "出金优惠": {"id": 12, "slug": "pa_出金优惠"},
    "剥头皮？": {"id": 11, "slug": "pa_剥头皮？"},
    "可锁仓？": {"id": 10, "slug": "pa_可锁仓？"},
    "成立时间": {"id": 4,  "slug": "pa_成立时间"},
    "最低入金": {"id": 1,  "slug": "pa_最低入金"},
    "最大杠杆": {"id": 7,  "slug": "pa_最大杠杆"},
    "最小头寸": {"id": 2,  "slug": "pa_最小头寸"},
    "注册地":   {"id": 14, "slug": "pa_注册地"},
    "点差类型": {"id": 15, "slug": "pa_点差类型"},
    "爆仓比例": {"id": 3,  "slug": "pa_爆仓比例"},
    "监管机构": {"id": 5,  "slug": "pa_监管机构"},
    "经营模式": {"id": 9,  "slug": "pa_经营模式"},
}

def call_mcp_tool(name, arguments={}):
    """通过 Easy MCP AI 接口调用后端工具"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments
        }
    }
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def parse_markdown_file(file_path):
    """解析带有 YAML Frontmatter 的 Markdown 文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(pattern, content, re.DOTALL)
    if not match:
        raise ValueError(f"文件 {file_path} 未找到有效的 YAML Frontmatter 头部！")

    frontmatter_raw = match.group(1)
    body_markdown = match.group(2).strip()

    meta = yaml.safe_load(frontmatter_raw)
    return meta, body_markdown

def markdown_to_gutenberg_blocks(md_text):
    """
    将 Markdown 文本严格解析为 WordPress 原生 Gutenberg Blocks 结构，
    确保段落、标题、列表、表格和 Rank Math FAQ Block 完全按原生 Block 渲染。
    """
    # 替换特殊货币符号避免被解析器忽略
    protected_md = md_text.replace("$", "美元 ")
    
    # 规范化：确保每个以 # 开头的标题后都有空行，防止随后的段落因单换行粘连被漏掉
    protected_md = re.sub(r'^(#{1,6}\s+[^\n]+)\n(?!\n)', r'\1\n\n', protected_md, flags=re.MULTILINE)
    
    # 保护已存在的 Gutenberg Block 注释（如 Rank Math FAQ block）
    wp_pattern = re.compile(r'(<!-- wp:[a-z0-9\-\/]+.*?-->.*?<!-- /wp:[a-z0-9\-\/]+ -->)', re.DOTALL)
    parts = wp_pattern.split(protected_md)
    output_blocks = []

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("<!-- wp:"):
            # 已经是合法的 Gutenberg Block，直接保留
            output_blocks.append(part)
        else:
            # 切分普通 Markdown 块（按双换行切分）
            chunks = [c.strip() for c in re.split(r'\n{2,}', part) if c.strip()]
            for chunk in chunks:
                if chunk.startswith("---") or chunk == "***":
                    output_blocks.append('<!-- wp:separator -->\n<hr class="wp-block-separator has-alpha-channel-opacity"/>\n<!-- /wp:separator -->')
                elif chunk.startswith("#"):
                    m = re.match(r'^(#{1,6})\s+(.*)$', chunk)
                    if m:
                        level = len(m.group(1))
                        htext = m.group(2).strip()
                        output_blocks.append(f'<!-- wp:heading {{"level":{level}}} -->\n<h{level} class="wp-block-heading">{htext}</h{level}>\n<!-- /wp:heading -->')
                elif chunk.startswith("![") and "](" in chunk:
                    # 原生 Gutenberg Image Block
                    m = re.match(r'^!\[(.*?)\]\((.*?)\)$', chunk)
                    if m:
                        alt = m.group(1).strip()
                        src = m.group(2).strip()
                        output_blocks.append(f'<!-- wp:image {{"sizeSlug":"large","linkDestination":"none"}} -->\n<figure class="wp-block-image size-large"><img src="{src}" alt="{alt}"/><figcaption class="wp-element-caption">{alt}</figcaption></figure>\n<!-- /wp:image -->')
                elif chunk.startswith("|") and "|" in chunk:
                    # 表格 Block
                    table_html = markdown.markdown(chunk, extensions=['tables'])
                    # 清理表格多余空白
                    table_html = re.sub(r'>\s+<', '><', table_html)
                    output_blocks.append(f'<!-- wp:table -->\n<figure class="wp-block-table">{table_html}</figure>\n<!-- /wp:table -->')
                elif chunk.startswith("- ") or chunk.startswith("* "):
                    # 无序列表 Block
                    list_html = markdown.markdown(chunk).strip()
                    output_blocks.append(f'<!-- wp:list -->\n{list_html}\n<!-- /wp:list -->')
                elif re.match(r'^\d+\.\s+', chunk):
                    # 有序列表 Block
                    list_html = markdown.markdown(chunk).strip()
                    output_blocks.append(f'<!-- wp:list {{"ordered":true}} -->\n{list_html}\n<!-- /wp:list -->')
                elif chunk.startswith(">"):
                    # 引用 Block
                    q_text = re.sub(r'^>\s?', '', chunk, flags=re.MULTILINE).strip()
                    q_html = markdown.markdown(q_text).strip()
                    output_blocks.append(f'<!-- wp:quote -->\n<blockquote class="wp-block-quote">{q_html}</blockquote>\n<!-- /wp:quote -->')
                else:
                    # 普通段落 Block
                    p_html = markdown.markdown(chunk).strip()
                    if p_html.startswith("<p>") and p_html.endswith("</p>"):
                        p_html = p_html[3:-4].strip()
                    output_blocks.append(f'<!-- wp:paragraph -->\n<p>{p_html}</p>\n<!-- /wp:paragraph -->')

    return '\n\n'.join(output_blocks)

def build_product_payload(meta):
    """组装 WooCommerce 产品属性、外链及 Meta 数据"""
    payload = {
        "name": meta.get("name"),
        "type": meta.get("type", "external"),
        "status": meta.get("status", "publish"),
        "external_url": meta.get("external_url", "https://s.ssgg.net/xxxx"),
        "button_text": meta.get("button_text", "官网开户"),
    }

    if meta.get("slug"):
        payload["slug"] = meta["slug"]

    # 1. 组装 16 大属性
    attributes_data = []
    input_attrs = meta.get("attributes", {})
    for attr_name, attr_val in input_attrs.items():
        clean_name = attr_name.strip()
        matched_info = None
        for k, v in GLOBAL_ATTR_MAP.items():
            if k.replace("？", "").replace("?", "") == clean_name.replace("？", "").replace("?", ""):
                matched_info = v
                break
        
        if not matched_info:
            continue

        if isinstance(attr_val, list):
            options = [str(x).strip() for x in attr_val]
        else:
            options = [str(attr_val).strip()]

        attributes_data.append({
            "id": matched_info["id"],
            "name": clean_name,
            "options": options,
            "visible": True,
            "variation": False
        })

    if attributes_data:
        payload["attributes"] = attributes_data

    # 2. 组装 REHub 评分与 Rank Math SEO Meta
    meta_data = []
    meta_data.append({"key": "_rh_woo_product_layout", "value": "woo_compact"})

    review = meta.get("review", {})
    if review:
        overall_score = str(review.get("overall_score", "9.0"))
        meta_data.append({"key": "rehub_review_overall_score", "value": overall_score})
        meta_data.append({"key": "_review_post_score_manual", "value": overall_score})
        
        if review.get("heading"):
            meta_data.append({"key": "_review_heading", "value": str(review["heading"])})

        summary_text = (
            review.get("summary_text")
            or review.get("summary")
            or review.get("row__review_post_summary_text")
            or meta.get("row__review_post_summary_text")
            or ""
        )
        if summary_text:
            meta_data.append({"key": "_review_post_summary_text", "value": str(summary_text)})
            meta_data.append({"key": "rehub_woodeals_short", "value": str(summary_text)})
            meta_data.append({"key": "row__review_post_summary_text", "value": str(summary_text)})

        pros = review.get("pros", [])
        if isinstance(pros, list):
            meta_data.append({"key": "_review_post_pros_text", "value": "\n".join(pros)})

        cons = review.get("cons", [])
        if isinstance(cons, list):
            meta_data.append({"key": "_review_post_cons_text", "value": "\n".join(cons)})

        criteria = review.get("criteria", [])
        if criteria:
            criteria_list = []
            for idx, c in enumerate(criteria, 1):
                c_name = str(c.get("name", ""))
                c_score = str(c.get("score", overall_score))
                criteria_list.append({"review_post_name": c_name, "review_post_score": c_score})
                meta_data.append({"key": f"_review_score_criteria_{idx}", "value": c_score})
            meta_data.append({"key": "_review_post_criteria", "value": criteria_list})

    seo = meta.get("seo", {})
    if seo:
        if seo.get("title"):
            meta_data.append({"key": "rank_math_title", "value": str(seo["title"])})
        if seo.get("description"):
            meta_data.append({"key": "rank_math_description", "value": str(seo["description"])})
        if seo.get("focus_keyword"):
            meta_data.append({"key": "rank_math_focus_keyword", "value": str(seo["focus_keyword"])})

    if meta_data:
        payload["meta_data"] = meta_data

    return payload

def update_file_id(file_path, new_id):
    """如果原文件没有 ID，创建成功后回写 ID 到 markdown 文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    updated = re.sub(r"^id:\s*(null|none|0|\"\"|'')\s*$", f"id: {new_id}", content, flags=re.MULTILINE | re.IGNORECASE)
    if updated != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated)
        print(f"📝 已将新建产品 ID [{new_id}] 回写至本地文件: {file_path}")

def sync_broker_file(file_path, dry_run=False):
    """同步单个 Markdown 文件至 WordPress（使用 Gutenberg 原生 Blocks）"""
    print(f"\n==========================================")
    print(f"正在处理文件: {file_path}")
    meta, body_markdown = parse_markdown_file(file_path)
    
    # 转换为原生 Gutenberg Blocks
    gutenberg_blocks = markdown_to_gutenberg_blocks(body_markdown)
    payload = build_product_payload(meta)

    product_id = meta.get("id")
    name = meta.get("name", "未命名")

    if dry_run:
        print(f"[DRY-RUN] 预览同步: {name} (ID: {product_id})")
        print(f"  - 状态: {payload.get('status')}")
        print(f"  - 外链: {payload.get('external_url')}")
        print(f"  - 属性数量: {len(payload.get('attributes', []))}")
        print(f"  - Meta 项数: {len(payload.get('meta_data', []))}")
        print(f"  - Gutenberg Blocks 字符数: {len(gutenberg_blocks)}")
        first_few = '\n'.join(gutenberg_blocks.split('\n')[:8])
        print(f"  - Blocks 前导片段:\n{first_few}")
        return True

    # 1. 更新产品属性及 WooCommerce / REHub Meta
    if product_id:
        print(f"🔄 1/2 正在更新属性与评分: [{name}] (ID: {product_id})...")
        route_wc = f"/wc/v3/products/{product_id}"
        res_wc = call_mcp_tool("wp_rest_write", {
            "route": route_wc,
            "method": "PUT",
            "body": payload
        })
    else:
        print(f"✨ 1/2 正在创建产品: [{name}]...")
        route_wc = "/wc/v3/products"
        res_wc = call_mcp_tool("wp_rest_write", {
            "route": route_wc,
            "method": "POST",
            "body": payload
        })

    wc_text = res_wc.get("result", {}).get("content", [{}])[0].get("text", "")
    data_wc = json.loads(wc_text)
    if data_wc.get("status") not in [200, 201]:
        print(f"❌ WooCommerce 基础属性更新失败: {wc_text[:300]}")
        return False

    actual_id = data_wc.get("data", {}).get("id") or product_id
    if not product_id and actual_id:
        update_file_id(file_path, actual_id)

    # 2. 通过 WordPress 核心 REST API 推送原生 Gutenberg Blocks 内容
    print(f"🧱 2/2 正在注入原生 Gutenberg Blocks 正文 (ID: {actual_id})...")
    route_wp = f"/wp/v2/product/{actual_id}"
    res_wp = call_mcp_tool("wp_rest_write", {
        "route": route_wp,
        "method": "POST",
        "body": {
            "content": gutenberg_blocks
        }
    })

    wp_text = res_wp.get("result", {}).get("content", [{}])[0].get("text", "")
    try:
        data_wp = json.loads(wp_text)
        if data_wp.get("status") in [200, 201]:
            link = data_wp.get("data", {}).get("link", "")
            print(f"✅ 同步成功！原生 Gutenberg Blocks 已注入！")
            print(f"   前台链接: {link}")
            
            # 清除缓存
            call_mcp_tool("wp_clear_cache", {
                "scope": "posts",
                "post_ids": [int(actual_id)]
            })
            print(f"🧹 已自动刷新前台与 CDN 缓存")
            return True
        else:
            print(f"⚠️ 正文注入反馈: {wp_text[:300]}")
            return False
    except Exception as e:
        print(f"⚠️ 解析核心响应出错: {e}, 原文: {wp_text[:300]}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="WordPress Broker Gutenberg Blocks 同步工具")
    parser.add_argument("path", nargs="?", default="brokers", help="Markdown 文件路径或 brokers 目录路径")
    parser.add_argument("--dry-run", action="store_true", help="演练模式，仅打印组装结构不实际提交")
    args = parser.parse_args()

    target = args.path
    if os.path.isfile(target):
        sync_broker_file(target, dry_run=args.dry_run)
    elif os.path.isdir(target):
        files = [os.path.join(target, f) for f in os.listdir(target) if f.endswith(".md")]
        print(f"📂 在目录 [{target}] 下共发现 {len(files)} 个 Markdown 文件")
        for f in sorted(files):
            sync_broker_file(f, dry_run=args.dry_run)
    else:
        print(f"❌ 路径不存在: {target}")
        sys.exit(1)

if __name__ == "__main__":
    main()
