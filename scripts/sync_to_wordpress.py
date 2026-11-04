#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WordPress / REHub Broker 自动化同步脚本
将 Markdown 文件解析并推送到 we.laowei8.com (开户通) WooCommerce 产品库。
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

def markdown_to_html(md_text):
    """将 Markdown 转换为兼容 WordPress 的 HTML"""
    return markdown.markdown(
        md_text,
        extensions=[
            "extra",          # 表格、属性列表等
            "nl2br",          # 换行转换为 <br>
            "sane_lists",     # 更好的列表解析
            "codehilite"      # 代码高亮
        ]
    )

def build_product_payload(meta, body_html):
    """根据元数据和 HTML 正文组装 WooCommerce 产品结构"""
    payload = {
        "name": meta.get("name"),
        "type": meta.get("type", "external"),
        "status": meta.get("status", "publish"),
        "external_url": meta.get("external_url", "https://s.ssgg.net/xxxx"),
        "button_text": meta.get("button_text", "官网开户"),
        "description": body_html,
    }

    if meta.get("slug"):
        payload["slug"] = meta["slug"]

    # 1. 组装 16 大属性
    attributes_data = []
    input_attrs = meta.get("attributes", {})
    for attr_name, attr_val in input_attrs.items():
        # 清理名称匹配
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
    
    # REHub 布局保持 woo_compact
    meta_data.append({"key": "_rh_woo_product_layout", "value": "woo_compact"})

    # REHub Review 字段
    review = meta.get("review", {})
    if review:
        overall_score = str(review.get("overall_score", "9.0"))
        meta_data.append({"key": "rehub_review_overall_score", "value": overall_score})
        meta_data.append({"key": "_review_post_score_manual", "value": overall_score})
        
        if review.get("heading"):
            meta_data.append({"key": "_review_heading", "value": str(review["heading"])})

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

    # Rank Math SEO 字段
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

    # 替换 id: null 或 id: 0
    updated = re.sub(r"^id:\s*(null|none|0|\"\"|'')\s*$", f"id: {new_id}", content, flags=re.MULTILINE | re.IGNORECASE)
    if updated != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated)
        print(f"📝 已将新建产品 ID [{new_id}] 回写至本地文件: {file_path}")

def sync_broker_file(file_path, dry_run=False):
    """同步单个 Markdown 文件至 WordPress"""
    print(f"\n==========================================")
    print(f"正在处理文件: {file_path}")
    meta, body_markdown = parse_markdown_file(file_path)
    body_html = markdown_to_html(body_markdown)
    payload = build_product_payload(meta, body_html)

    product_id = meta.get("id")
    name = meta.get("name", "未命名")

    if dry_run:
        print(f"[DRY-RUN] 预览同步: {name} (ID: {product_id})")
        print(f"  - 状态: {payload.get('status')}")
        print(f"  - 外链: {payload.get('external_url')}")
        print(f"  - 属性数量: {len(payload.get('attributes', []))}")
        print(f"  - Meta 项数: {len(payload.get('meta_data', []))}")
        print(f"  - HTML 正文长度: {len(body_html)} 字符")
        return True

    if product_id:
        print(f"🔄 正在更新已有产品: [{name}] (ID: {product_id})...")
        route = f"/wc/v3/products/{product_id}"
        res = call_mcp_tool("wp_rest_write", {
            "route": route,
            "method": "PUT",
            "body": payload
        })
    else:
        print(f"✨ 正在新建产品: [{name}]...")
        route = "/wc/v3/products"
        res = call_mcp_tool("wp_rest_write", {
            "route": route,
            "method": "POST",
            "body": payload
        })

    # 检查返回结果
    res_text = res.get("result", {}).get("content", [{}])[0].get("text", "")
    try:
        data = json.loads(res_text)
        if data.get("status") in [200, 201]:
            resp_data = data.get("data", {})
            returned_id = resp_data.get("id")
            link = resp_data.get("permalink", "")
            print(f"✅ 同步成功！产品 ID: {returned_id}")
            print(f"   前台链接: {link}")
            if not product_id and returned_id:
                update_file_id(file_path, returned_id)
            return True
        else:
            print(f"❌ 同步失败: {res_text[:300]}")
            return False
    except Exception as e:
        print(f"⚠️ 解析响应出错: {e}, 原文: {res_text[:300]}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="WordPress Broker Markdown 同步工具")
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
