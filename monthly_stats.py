from dotenv import load_dotenv
import os
import requests
from datetime import datetime
from collections import defaultdict

load_dotenv()

notion_token = os.environ["NOTION_TOKEN"]
work_items_db_id = os.environ["NOTION_WORK_ITEMS_DB_ID"]
monthly_stats_db_id = os.environ["NOTION_MONTHLY_STATS_DB_ID"]
headers = {
    "Authorization": f"Bearer {notion_token}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# ----------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------

def query_all(db_id, filter=None):
    pages = []
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        if filter:
            body["filter"] = filter
        res = requests.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=headers,
            json=body
        ).json()
        pages.extend(res.get("results", []))
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return pages

def get_select_value(page, prop):
    values = page["properties"].get(prop, {}).get("multi_select", [])
    return values[0]["name"] if values else None

def get_date_value(page, prop):
    date = page["properties"].get(prop, {}).get("date")
    return date["start"] if date else None

def delete_page(page_id):
    requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=headers,
        json={"archived": True}
    )

# ----------------------------------------------------------------
# Step 1: Collect Work Items for the target month
# ----------------------------------------------------------------

def collect_stats(target_month):
    """Count Work Items by Category and Status for the given month (YYYY-MM)"""
    print(f"Collecting Work Items for {target_month}...")
    pages = query_all(work_items_db_id)

    # {(category, status): count}
    counts = defaultdict(int)

    for page in pages:
        item_type = get_select_value(page, "Type")
        if item_type == "Epic":
            continue  # Count Tasks only

        planned_end = get_date_value(page, "Planned End")
        if not planned_end or not planned_end.startswith(target_month):
            continue

        category = get_select_value(page, "Category") or "Uncategorized"
        status = get_select_value(page, "Status") or "Unknown"
        counts[(category, status)] += 1

    print(f"Found {sum(counts.values())} items across {len(counts)} category/status combinations.")
    return counts

# ----------------------------------------------------------------
# Step 2: Clear Current Month flag from all records
# ----------------------------------------------------------------

def clear_current_month_flag():
    print("Clearing Current Month flag from all records...")
    pages = query_all(monthly_stats_db_id, filter={
        "property": "Current Month",
        "checkbox": {"equals": True}
    })
    for page in pages:
        requests.patch(
            f"https://api.notion.com/v1/pages/{page['id']}",
            headers=headers,
            json={"properties": {"Current Month": {"checkbox": False}}}
        )
    print(f"Cleared {len(pages)} records.")

# ----------------------------------------------------------------
# Step 3: Clear existing stats for the target month
# ----------------------------------------------------------------

def clear_existing_stats(target_month):
    print(f"Clearing existing stats for {target_month}...")
    pages = query_all(monthly_stats_db_id, filter={
        "property": "Month",
        "rich_text": {"equals": target_month}
    })
    for page in pages:
        delete_page(page["id"])
    print(f"Deleted {len(pages)} existing records.")

# ----------------------------------------------------------------
# Step 3: Write new stats
# ----------------------------------------------------------------

def write_stats(target_month, counts):
    print("Writing new stats...")
    written = 0
    for (category, status), count in sorted(counts.items()):
        title = f"{target_month} / {category} / {status}"
        properties = {
            "Title": {"title": [{"text": {"content": title}}]},
            "Month": {"rich_text": [{"text": {"content": target_month}}]},
            "Category": {"multi_select": [{"name": category}]},
            "Status": {"multi_select": [{"name": status}]},
            "Count": {"number": count},
            "Current Month": {"checkbox": True},
        }
        res = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json={"parent": {"database_id": monthly_stats_db_id}, "properties": properties}
        )
        if res.status_code == 200:
            print(f"  ✅ {title}: {count}")
            written += 1
        else:
            print(f"  ❌ {title}: {res.json()}")
    print(f"Done. Written: {written}")

# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------

if __name__ == "__main__":
    import sys
    # Accept optional month argument: python monthly_stats.py 2026-03
    if len(sys.argv) > 1:
        target_month = sys.argv[1]
    else:
        target_month = datetime.now().strftime("%Y-%m")

    print(f"Target month: {target_month}")
    counts = collect_stats(target_month)
    if counts:
        clear_current_month_flag()
        clear_existing_stats(target_month)
        write_stats(target_month, counts)
    else:
        print("No Work Items found for this month. Nothing to write.")
