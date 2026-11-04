#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 we.laowei8.com (开户通) 批量拉取已有 Broker 产品并导出为标准 Markdown 文件
"""

import sys
import os
import json
import urllib.request
import yaml
import html2text

URL = os.environ.get("WPMCP_URL", "https://we.laowei8.com/wp-json/easy-mcp-ai/v1/mcp")
TOKEN = os.environ.get("WPMCP_TOKEN", "wpmcp_2d0029f0d996549108aba68d86429215c4f04744a9e6a6eb539188298d0ef22f")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def call_mcp_tool(name, arguments={}):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments
        }
    }
    req = urllib.request.Request(URL, data=json.dumps(payload).encode("utf-8"), headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def clean_html_to_md(html_str):
    if not html_str or not html_str.strip():
        return ""
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_images = False
    h.ignore_links = False
    h.unicode_snob = True
    return h.handle(html_str).strip()

def export_single_product(prod_id, output_dir="brokers"):
    res = call_mcp_tool("wp_rest_read", {"route": f"/wc/v3/products/{prod_id}"})
    raw = res.get("result", {}).get("content", [{}])[0].get("text", "")
    try:
        p = json.loads(raw).get("data", {})
    except Exception as e:
        print(f"❌ 读取产品 ID {prod_id} 失败: {e}")
        return False

    name = p.get("name", f"broker-{prod_id}")
    slug = p.get("slug") or f"broker-{prod_id}"
    status = p.get("status", "draft")
    ext_url = p.get("external_url", "")
    if not ext_url:
        ext_url = f"https://s.ssgg.net/{slug.replace('-review', '')}"
    elif "ifttt.fun" in ext_url:
        ext_url = ext_url.replace("https://s.ifttt.fun/", "https://s.ssgg.net/")

    button_text = p.get("button_text") or "官网开户"

    # 1. 属性提取
    attrs = {}
    for a in p.get("attributes", []):
        a_name = a.get("name")
        opts = a.get("options", [])
        if len(opts) == 1:
            attrs[a_name] = opts[0]
        else:
            attrs[a_name] = opts

    # 2. Meta 提取
    meta_list = p.get("meta_data", [])
    meta_dict = {m.get("key"): m.get("value") for m in meta_list}

    # REHub Review
    pros_raw = meta_dict.get("_review_post_pros_text", "")
    cons_raw = meta_dict.get("_review_post_cons_text", "")
    pros = [line.strip() for line in str(pros_raw).split("\n") if line.strip()] if pros_raw else []
    cons = [line.strip() for line in str(cons_raw).split("\n") if line.strip()] if cons_raw else []

    review_data = {
        "overall_score": float(meta_dict.get("rehub_review_overall_score") or meta_dict.get("_review_post_score_manual") or 8.5),
        "heading": meta_dict.get("_review_heading") or "",
        "pros": pros,
        "cons": cons,
        "criteria": meta_dict.get("_review_post_criteria") or []
    }

    # SEO Data
    seo_data = {
        "focus_keyword": meta_dict.get("rank_math_focus_keyword") or slug.replace("-review", ""),
        "title": meta_dict.get("rank_math_title") or f"{name}评测与开户指南",
        "description": meta_dict.get("rank_math_description") or ""
    }

    frontmatter = {
        "id": prod_id,
        "name": name,
        "slug": slug,
        "status": status,
        "type": "external",
        "external_url": ext_url,
        "button_text": button_text,
        "seo": seo_data,
        "attributes": attrs,
        "review": review_data
    }

    body_html = p.get("description", "")
    body_md = clean_html_to_md(body_html)
    if not body_md:
        body_md = f"## 核心速览与老交易员评价\n\n该平台目前基础参数已录入，详细实盘评测报告正在整理中。\n"

    # 生成 Markdown 内容
    yaml_header = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False, default_flow_style=False)
    final_content = f"---\n{yaml_header}---\n\n{body_md}\n"

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{slug}.md")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_content)

    print(f"✅ 成功导出: [{name}] (ID: {prod_id}, {status}) -> {filename}")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pid = int(sys.argv[1])
        export_single_product(pid)
    else:
        print("请提供产品 ID，例如: python3 export_from_wordpress.py 10311")
