from fastmcp import FastMCP
import requests
import uuid

# === CONFIG ===
# 使用 Zotero 本地 API（无需认证）
ZOTERO_LOCAL_API = "http://localhost:23119/api"
ZOTERO_CONNECTOR = "http://localhost:23119/connector"
# ==============

mcp = FastMCP("Zotero Writer")


def get_csl_from_doi(doi: str) -> dict:
    """通过 DOI 内容协商获取 CSL-JSON 格式的文献元数据"""
    url = f"https://doi.org/{doi}"
    headers = {"Accept": "application/vnd.citationstyles.csl+json"}
    r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
    r.raise_for_status()
    return r.json()


def csl_to_zotero(csl_data: dict) -> dict:
    """将 CSL-JSON 转换为 Zotero 条目格式"""
    # 映射 CSL type 到 Zotero itemType
    type_map = {
        "article-journal": "journalArticle",
        "book": "book",
        "chapter": "bookSection",
        "paper-conference": "conferencePaper",
        "thesis": "thesis",
        "report": "report",
        "webpage": "webpage",
        "article": "journalArticle",
    }

    csl_type = csl_data.get("type", "article-journal")
    item_type = type_map.get(csl_type, "journalArticle")

    # 构建 Zotero 条目
    item = {
        "itemType": item_type,
        "title": csl_data.get("title", ""),
        "DOI": csl_data.get("DOI", ""),
        "url": csl_data.get("URL", ""),
        "abstractNote": csl_data.get("abstract", ""),
        "creators": [],
    }

    # 处理作者
    for author in csl_data.get("author", []):
        creator = {
            "creatorType": "author",
            "firstName": author.get("given", ""),
            "lastName": author.get("family", ""),
        }
        item["creators"].append(creator)

    # 期刊文章特有字段
    if item_type == "journalArticle":
        item["publicationTitle"] = csl_data.get("container-title", "")
        item["volume"] = str(csl_data.get("volume", ""))
        item["issue"] = str(csl_data.get("issue", ""))
        item["pages"] = csl_data.get("page", "")
        item["ISSN"] = csl_data.get("ISSN", [""])[0] if isinstance(csl_data.get("ISSN"), list) else csl_data.get("ISSN", "")

    # 处理日期
    issued = csl_data.get("issued", {})
    date_parts = issued.get("date-parts", [[]])
    if date_parts and date_parts[0]:
        parts = date_parts[0]
        if len(parts) >= 1:
            item["date"] = str(parts[0])  # 年
        if len(parts) >= 2:
            item["date"] += f"-{parts[1]:02d}"  # 月
        if len(parts) >= 3:
            item["date"] += f"-{parts[2]:02d}"  # 日

    return item


@mcp.tool()
def add_paper_by_doi(doi: str) -> str:
    """
    通过 DOI 将学术文献导入 Zotero（使用本地 API）。

    参数:
        doi: 文献的 DOI 字符串 (例如 "10.1038/s41586-020-2012-7")

    返回:
        导入结果或错误信息。
    """
    print(f"Processing DOI: {doi}")

    # 1. 检查 Zotero 本地 API 是否可用
    try:
        r = requests.get(f"{ZOTERO_LOCAL_API}/users/0/items", timeout=5)
        if r.status_code == 403:
            return "❌ Zotero 本地 API 未启用。请在 Zotero 设置 -> 高级 -> 勾选「允许其他应用程序与 Zotero 通讯」"
    except requests.exceptions.ConnectionError:
        return "❌ 无法连接到 Zotero。请确保 Zotero 正在运行。"

    # 2. 使用 DOI 内容协商获取 CSL-JSON
    try:
        csl_data = get_csl_from_doi(doi)
    except requests.exceptions.HTTPError as e:
        return f"❌ DOI 解析失败 (无效DOI或网络问题): {str(e)}"
    except Exception as e:
        return f"❌ DOI 解析失败: {str(e)}"

    # 3. 转换为 Zotero 格式
    try:
        zotero_item = csl_to_zotero(csl_data)
    except Exception as e:
        return f"❌ 格式转换失败: {str(e)}"

    # 4. 通过 Connector saveItems 端点写入 Zotero
    try:
        url = f"{ZOTERO_CONNECTOR}/saveItems"
        headers = {
            "Content-Type": "application/json",
            "X-Zotero-Connector-API-Version": "3",
        }

        # Connector saveItems 需要的格式
        payload = {
            "items": [zotero_item],
            "uri": f"https://doi.org/{doi}",
            "sessionID": str(uuid.uuid4())
        }

        r = requests.post(url, json=payload, headers=headers, timeout=10)

        if r.status_code in [200, 201]:
            title = zotero_item.get("title", "Unknown Title")
            return f"✅ 成功导入:\n标题: {title}\nDOI: {doi}"
        else:
            return f"⚠️ 导入失败. 状态码: {r.status_code}, 响应: {r.text}"

    except Exception as e:
        return f"❌ Zotero API 写入错误: {str(e)}"


@mcp.tool()
def check_zotero_connection() -> str:
    """
    检查 Zotero 本地 API 连接状态。

    返回:
        连接状态信息。
    """
    try:
        r = requests.get(f"{ZOTERO_LOCAL_API}/users/0/items?limit=1", timeout=5)
        if r.status_code == 200:
            return "✅ Zotero 本地 API 连接正常"
        elif r.status_code == 403:
            return "❌ Zotero 本地 API 未启用。请在 Zotero 设置 -> 高级 -> 勾选「允许其他应用程序与 Zotero 通讯」"
        else:
            return f"⚠️ 未知状态: {r.status_code}"
    except requests.exceptions.ConnectionError:
        return "❌ 无法连接到 Zotero。请确保 Zotero 正在运行。"
    except Exception as e:
        return f"❌ 连接错误: {str(e)}"


if __name__ == "__main__":
    mcp.run()
