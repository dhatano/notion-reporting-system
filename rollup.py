from dotenv import load_dotenv
import os
import requests

load_dotenv()

notion_token = os.environ["NOTION_TOKEN"]
daily_db_id = os.environ["NOTION_DAILY_DB_ID"]
weekly_db_id = os.environ["NOTION_WEEKLY_DB_ID"]
monthly_db_id = os.environ["NOTION_MONTHLY_DB_ID"]
headers = {
    "Authorization": f"Bearer {notion_token}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# ----------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------

def query_all(db_id, filter=None, sorts=None):
    """Fetch all pages from a database (handles pagination)"""
    pages = []
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        if filter:
            body["filter"] = filter
        if sorts:
            body["sorts"] = sorts
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

def get_relation_ids(page, property_name):
    """Return a list of page IDs from a relation property"""
    return [r["id"] for r in page["properties"].get(property_name, {}).get("relation", [])]

def get_page(page_id):
    return requests.get(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=headers
    ).json()

def get_latest_page(db_id, date_property="Start (Date)"):
    """Return the page with the most recent date in date_property, or None"""
    pages = query_all(db_id, sorts=[{"property": date_property, "direction": "descending"}])
    for page in pages:
        date_val = page["properties"].get(date_property, {}).get("date")
        if date_val:
            return page
    return None

def update_relation(page_id, property_name, related_ids):
    """Overwrite a relation property with the given list of page IDs"""
    requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=headers,
        json={"properties": {property_name: {"relation": [{"id": i} for i in related_ids]}}}
    )

def get_label(page):
    title = page["properties"].get("Title", {}).get("title", [])
    return title[0]["plain_text"] if title else page["id"]

# ----------------------------------------------------------------
# Step 1: Collect Task IDs from Daily → Tickets Worked (Work Items)
# ----------------------------------------------------------------

def collect_task_ids():
    print("Collecting Task IDs from Daily → Tickets Worked...")
    daily_pages = query_all(daily_db_id)
    task_ids = set()

    for daily in daily_pages:
        for task_id in get_relation_ids(daily, "Tickets Worked"):
            task_ids.add(task_id)

    print(f"Found {len(task_ids)} unique tasks.")
    return list(task_ids)

# ----------------------------------------------------------------
# Step 2: Collect Epic IDs from Task → Parent Item
# ----------------------------------------------------------------

def collect_epic_ids(task_ids):
    print("Collecting Epic IDs from Tasks → Parent Item...")
    epic_ids = set()

    for task_id in task_ids:
        task_page = get_page(task_id)
        for epic_id in get_relation_ids(task_page, "Parent Item"):
            epic_ids.add(epic_id)

    print(f"Found {len(epic_ids)} unique epics.")
    return list(epic_ids)

# ----------------------------------------------------------------
# Step 3: Update latest Weekly (Task level)
# ----------------------------------------------------------------

def update_weekly(task_ids):
    print("\nUpdating latest Weekly...")
    page = get_latest_page(weekly_db_id)
    if not page:
        print("No Weekly record found. Skipping.")
        return
    update_relation(page["id"], "WBS Items", task_ids)
    print(f"✅ Weekly updated: {get_label(page)}")

# ----------------------------------------------------------------
# Step 4: Update latest Monthly (Epic level)
# ----------------------------------------------------------------

def update_monthly(epic_ids):
    print("\nUpdating latest Monthly...")
    page = get_latest_page(monthly_db_id)
    if not page:
        print("No Monthly record found. Skipping.")
        return
    update_relation(page["id"], "WBS Items", epic_ids)
    print(f"✅ Monthly updated: {get_label(page)}")

# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------

if __name__ == "__main__":
    task_ids = collect_task_ids()
    if not task_ids:
        print("No tasks found in Daily logs. Nothing to update.")
    else:
        update_weekly(task_ids)
        epic_ids = collect_epic_ids(task_ids)
        if epic_ids:
            update_monthly(epic_ids)
        else:
            print("No parent Epics found. Monthly skipped.")
