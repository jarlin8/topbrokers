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
    通过确定性状态机将 Markdown 文本严格解析为 WordPress 原生 Gutenberg Blocks 结构。
    逐行处理，彻底规避因正则切分导致的表格撕裂、按钮标签错乱与段落遗漏问题，确保后台 100% 验证通过。
    """
    # 替换特殊货币符号避免被解析器忽略
    md_text = md_text.replace("$", "美元 ")
    lines = md_text.splitlines()
    blocks = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 1. 空行跳过
        if not stripped:
            i += 1
            continue

        # 2. 原生 Gutenberg 按钮组块（完整提取，防止内部 wp:button 被截断）
        if stripped.startswith("<!-- wp:buttons"):
            btn_lines = [line]
            i += 1
            while i < n and "<!-- /wp:buttons -->" not in lines[i]:
                btn_lines.append(lines[i])
                i += 1
            if i < n:
                btn_lines.append(lines[i])
                i += 1
            full_btn = "\n".join(btn_lines)
            m = re.search(r'href="([^"]+)"[^>]*>(.*?)</a>', full_btn)
            if m:
                href = m.group(1)
                text = m.group(2).strip()
                normalized = (
                    '<!-- wp:buttons {"layout":{"type":"flex","justifyContent":"center"}} -->\n'
                    '<div class="wp-block-buttons">\n'
                    '<!-- wp:button {"backgroundColor":"primary","textColor":"white","style":{"border":{"radius":"4px"}},"fontSize":"medium"} -->\n'
                    f'<div class="wp-block-button has-custom-font-size has-medium-font-size"><a class="wp-block-button__link has-white-color has-primary-background-color has-text-color has-background has-medium-font-size has-custom-font-size wp-element-button" href="{href}" style="border-radius:4px" target="_blank" rel="nofollow noopener">{text}</a></div>\n'
                    '<!-- /wp:button -->\n'
                    '</div>\n'
                    '<!-- /wp:buttons -->'
                )
                blocks.append(normalized)
            else:
                blocks.append(full_btn)
            continue

        # 3. 原生 Rank Math FAQ 块（完整提取并标准化为官方最新保存格式）
        if stripped.startswith("<!-- wp:rank-math/faq-block"):
            faq_lines = [line]
            i += 1
            while i < n and "<!-- /wp:rank-math/faq-block -->" not in lines[i]:
                faq_lines.append(lines[i])
                i += 1
            if i < n:
                faq_lines.append(lines[i])
                i += 1
            full_faq = "\n".join(faq_lines)
            m = re.match(r'<!-- wp:rank-math/faq-block\s+(\{.*?\})\s*-->', full_faq, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    questions = data.get("questions", [])
                    items_html = []
                    for q in questions:
                        items_html.append(f'<div class="rank-math-faq-item"><h3 class="rank-math-question">{q["title"]}</h3><div class="rank-math-answer">{q["content"]}</div></div>')
                    blocks.append(f'<!-- wp:rank-math/faq-block {json.dumps(data, ensure_ascii=False)} -->\n<div class="wp-block-rank-math-faq-block rank-math-block">' + ''.join(items_html) + '</div>\n<!-- /wp:rank-math/faq-block -->')
                    continue
                except Exception:
                    pass
            blocks.append(full_faq)
            continue

        # 4. 其他任何 <!-- wp: 块
        if stripped.startswith("<!-- wp:"):
            raw_lines = [line]
            parts = stripped.split()
            end_tag = parts[1].replace("wp:", "/wp:") if len(parts) > 1 else "-->"
            i += 1
            while i < n and f"<!-- {end_tag} -->" not in lines[i]:
                raw_lines.append(lines[i])
                i += 1
            if i < n:
                raw_lines.append(lines[i])
                i += 1
            blocks.append("\n".join(raw_lines))
            continue

        # 5. 分割线
        if stripped in ("---", "***", "___"):
            blocks.append('<!-- wp:separator -->\n<hr class="wp-block-separator has-alpha-channel-opacity"/>\n<!-- /wp:separator -->')
            i += 1
            continue

        # 6. 标题 (#, ##, ###...)
        hm = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if hm:
            level = len(hm.group(1))
            htext = hm.group(2).strip()
            blocks.append(f'<!-- wp:heading {{"level":{level}}} -->\n<h{level} class="wp-block-heading">{htext}</h{level}>\n<!-- /wp:heading -->')
            i += 1
            continue

        # 7. 图片 (![alt](src))
        im = re.match(r'^!\[(.*?)\]\((.*?)\)$', stripped)
        if im:
            alt = im.group(1).strip()
            src = im.group(2).strip()
            blocks.append(f'<!-- wp:image {{"sizeSlug":"large","linkDestination":"none"}} -->\n<figure class="wp-block-image size-large"><img src="{src}" alt="{alt}"/><figcaption class="wp-element-caption">{alt}</figcaption></figure>\n<!-- /wp:image -->')
            i += 1
            continue

        # 8. 表格 (完整收集从首行 | 到末行 | 的全部行，作为单个表格统一处理)
        if stripped.startswith("|"):
            tbl_lines = [stripped]
            i += 1
            while i < n and lines[i].strip().startswith("|"):
                tbl_lines.append(lines[i].strip())
                i += 1
            table_md = "\n".join(tbl_lines)
            thtml = markdown.markdown(table_md, extensions=['tables'])
            thtml = re.sub(r'\s*style="[^"]*"', '', thtml)
            thtml = thtml.replace('<table>', '<table class="has-fixed-layout">')
            thtml = re.sub(r'>\s+<', '><', thtml).strip()
            blocks.append(f'<!-- wp:table -->\n<figure class="wp-block-table">{thtml}</figure>\n<!-- /wp:table -->')
            continue

        # 9. 引用 (以 > 开头)
        if stripped.startswith(">"):
            q_lines = [re.sub(r'^>\s?', '', stripped)]
            i += 1
            while i < n and lines[i].strip().startswith(">"):
                q_lines.append(re.sub(r'^>\s?', '', lines[i].strip()))
                i += 1
            q_html = markdown.markdown("\n".join(q_lines)).strip()
            blocks.append(f'<!-- wp:quote -->\n<blockquote class="wp-block-quote">{q_html}</blockquote>\n<!-- /wp:quote -->')
            continue

        # 10. 无序列表 (以 * 或 - 开头)
        if stripped.startswith("* ") or stripped.startswith("- "):
            list_lines = [line]
            i += 1
            while i < n and (lines[i].strip().startswith("* ") or lines[i].strip().startswith("- ") or (lines[i].startswith("  ") and lines[i].strip())):
                list_lines.append(lines[i])
                i += 1
            l_html = markdown.markdown("\n".join(list_lines)).strip()
            blocks.append(f'<!-- wp:list -->\n{l_html}\n<!-- /wp:list -->')
            continue

        # 11. 有序列表 (以 1. 2. 开头)
        if re.match(r'^\d+\.\s+', stripped):
            list_lines = [line]
            i += 1
            while i < n and (re.match(r'^\d+\.\s+', lines[i].strip()) or (lines[i].startswith("  ") and lines[i].strip())):
                list_lines.append(lines[i])
                i += 1
            l_html = markdown.markdown("\n".join(list_lines)).strip()
            blocks.append(f'<!-- wp:list {{"ordered":true}} -->\n{l_html}\n<!-- /wp:list -->')
            continue

        # 12. 普通段落 (收集连续普通行直到空行或结构标记)
        p_lines = [line]
        i += 1
        while i < n:
            next_s = lines[i].strip()
            if not next_s:
                break
            if next_s.startswith("#") or next_s.startswith("|") or next_s.startswith(">") or next_s.startswith("<!--") or next_s in ("---", "***") or next_s.startswith("* ") or next_s.startswith("- ") or re.match(r'^\d+\.\s+', next_s) or next_s.startswith("!["):
                break
            p_lines.append(lines[i])
            i += 1
        p_md = "\n".join(p_lines)
        p_html = markdown.markdown(p_md).strip()
        if p_html.startswith("<p>") and p_html.endswith("</p>"):
            p_html = p_html[3:-4].strip()
        blocks.append(f'<!-- wp:paragraph -->\n<p>{p_html}</p>\n<!-- /wp:paragraph -->')

    return '\n\n'.join(blocks)

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
