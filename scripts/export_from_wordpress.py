#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 we.laowei8.com (开户通) 批量拉取已有 Broker 产品并导出为标准 Markdown 文件
具备断点续传、自动重试与速率限制自适应避让能力。
"""

import sys
import os
import re
import json
import time
import urllib.request
import urllib.error
import yaml
import html2text

URL = os.environ.get("WPMCP_URL", "https://we.laowei8.com/wp-json/easy-mcp-ai/v1/mcp")
TOKEN = os.environ.get("WPMCP_TOKEN", "wpmcp_2d0029f0d996549108aba68d86429215c4f04744a9e6a6eb539188298d0ef22f")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def call_mcp_tool_with_retry(name, arguments={}):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments
        }
    }
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(URL, data=json.dumps(payload).encode("utf-8"), headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                
                # 检查是否命中速率限制
                if "error" in data:
                    err = data["error"]
                    if err.get("code") == -32003 or "Rate limit" in err.get("message", ""):
                        retry_after = err.get("data", {}).get("retry_after", 20)
                        print(f"⏳ 触发 Easy MCP AI 频率限制（60次/分），等待 {retry_after + 2} 秒后自动恢复...")
                        time.sleep(retry_after + 2)
                        continue
                    else:
                        return data
                return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"⏳ HTTP 429 Too Many Requests，等待 25 秒...")
                time.sleep(25)
                continue
            elif e.code == 403:
                print(f"❌ HTTP 403 权限异常: {e}")
                return None
            else:
                time.sleep(3)
        except Exception as e:
            time.sleep(2)

    return None

def clean_html_to_md(html_str):
    if not html_str or not html_str.strip():
        return ""
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_images = False
    h.ignore_links = False
    h.unicode_snob = True
    return h.handle(html_str).strip()

def get_existing_exported_ids(output_dir="brokers"):
    existing_ids = set()
    if not os.path.isdir(output_dir):
        return existing_ids
    
    for f in os.listdir(output_dir):
        if not f.endswith(".md"):
            continue
        filepath = os.path.join(output_dir, f)
        try:
            with open(filepath, "r", encoding="utf-8") as fp:
                for line in fp:
                    if line.startswith("id:"):
                        val = line.split(":", 1)[1].strip()
                        if val.isdigit():
                            existing_ids.add(int(val))
                        break
        except Exception:
            pass
    return existing_ids

def export_single_product(prod_id, output_dir="brokers"):
    res = call_mcp_tool_with_retry("wp_rest_read", {"route": f"/wc/v3/products/{prod_id}"})
    if not res:
        return False

    raw = res.get("result", {}).get("content", [{}])[0].get("text", "")
    try:
        p = json.loads(raw).get("data", {})
    except Exception as e:
        return False

    name = p.get("name") or f"broker-{prod_id}"
    slug = p.get("slug") or f"broker-{prod_id}"
    status = p.get("status", "draft")
    ext_url = p.get("external_url", "")
    if not ext_url:
        clean_slug = slug.replace("-review", "")
        ext_url = f"https://s.ssgg.net/{clean_slug}"
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
        elif len(opts) > 1:
            attrs[a_name] = opts

    # 2. Meta 提取
    meta_list = p.get("meta_data", [])
    meta_dict = {m.get("key"): m.get("value") for m in meta_list}

    # REHub Review
    pros_raw = meta_dict.get("_review_post_pros_text", "")
    cons_raw = meta_dict.get("_review_post_cons_text", "")
    pros = [line.strip() for line in str(pros_raw).split("\n") if line.strip()] if pros_raw else []
    cons = [line.strip() for line in str(cons_raw).split("\n") if line.strip()] if cons_raw else []

    try:
        score_val = float(meta_dict.get("rehub_review_overall_score") or meta_dict.get("_review_post_score_manual") or 8.5)
    except Exception:
        score_val = 8.5

    criteria_raw = meta_dict.get("_review_post_criteria") or []
    criteria = []
    if isinstance(criteria_raw, list):
        for c in criteria_raw:
            if isinstance(c, dict) and c.get("review_post_name"):
                criteria.append({
                    "name": c.get("review_post_name"),
                    "score": float(c.get("review_post_score") or score_val)
                })

    review_data = {
        "overall_score": score_val,
        "heading": meta_dict.get("_review_heading") or "",
        "summary_text": meta_dict.get("_review_post_summary_text") or meta_dict.get("rehub_woodeals_short") or "",
        "pros": pros,
        "cons": cons,
        "criteria": criteria
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
    clean_filename = slug.replace("/", "_").replace("\\", "_")
    filename = os.path.join(output_dir, f"{clean_filename}.md")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_content)

    return name, prod_id, status, filename

def export_all_products(output_dir="brokers"):
    existing_ids = get_existing_exported_ids(output_dir)
    print(f"📦 发现本地已存在 {len(existing_ids)} 个已导出的 Broker 文件（自动跳过）")

    # 获取全量产品列表
    id_list = []
    page = 1
    while True:
        res = call_mcp_tool_with_retry("wp_rest_read", {
            "route": "/wp/v2/product",
            "query": {"status": "any", "per_page": 100, "page": page},
            "fields": "id,slug,name"
        })
        if not res:
            break
        raw = res.get("result", {}).get("content", [{}])[0].get("text", "")
        data = json.loads(raw)
        prods = data.get("data", [])
        if not prods:
            break
        for p in prods:
            id_list.append(p.get("id"))
        total_pages = data.get("pagination", {}).get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    total_all = len(id_list)
    pending_ids = [pid for pid in id_list if pid not in existing_ids]
    print(f"📋 全网共有 {total_all} 个 Broker，待导出: {len(pending_ids)} 个")

    if not pending_ids:
        print("🎉 全部 Broker 已全部导出完毕，无需新增！")
        return

    success_count = 0
    fail_count = 0
    start_time = time.time()

    for idx, pid in enumerate(pending_ids, 1):
        res = export_single_product(pid, output_dir)
        if res:
            name, prod_id, status, fname = res
            success_count += 1
        else:
            fail_count += 1
            print(f"⚠️ 产品 ID {pid} 导出未成功")

        if idx % 10 == 0 or idx == len(pending_ids):
            elapsed = time.time() - start_time
            rate = idx / (elapsed if elapsed > 0 else 1)
            print(f"⏳ 进度: [{idx}/{len(pending_ids)}] 已导出: {success_count} (失败: {fail_count}) | 速率: {rate:.1f}篇/秒 | 用时: {elapsed:.1f}s")
        
        # 保持在 40~50 req/min 安全速率，避免触发 60 req/min 拦截
        time.sleep(1.0)

    elapsed_total = time.time() - start_time
    print(f"\n🎉 批量导出执行完成！")
    print(f"   待导出: {len(pending_ids)} | 本次成功: {success_count} | 失败: {fail_count} | 耗时: {elapsed_total:.1f}s")

def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--all":
            export_all_products()
        else:
            try:
                pid = int(arg)
                export_single_product(pid)
            except ValueError:
                print("参数错误，用法: python3 export_from_wordpress.py [--all | <product_id>]")
    else:
        export_all_products()

if __name__ == "__main__":
    main()
