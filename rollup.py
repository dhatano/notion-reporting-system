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

def get_latest_page(db_id, date_property="Start"):
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

# ----------------------------------------------------------------
# Step 1: Collect WBS IDs from Daily → Ticket Worked → Master Schedule (WBS)
# ----------------------------------------------------------------

def collect_wbs_ids():
    print("Collecting WBS IDs from Daily → Tickets → WBS...")
    daily_pages = query_all(daily_db_id)
    wbs_ids = set()

    for daily in daily_pages:
        ticket_ids = get_relation_ids(daily, "Tickets Worked")
        for ticket_id in ticket_ids:
            ticket_page = requests.get(
                f"https://api.notion.com/v1/pages/{ticket_id}",
                headers=headers
            ).json()
            for wbs_id in get_relation_ids(ticket_page, "Schedule"):
                wbs_ids.add(wbs_id)

    print(f"Found {len(wbs_ids)} unique WBS items.")
    return list(wbs_ids)

# ----------------------------------------------------------------
# Step 2: Update latest Weekly
# ----------------------------------------------------------------

def update_weekly(wbs_ids):
    print("\nUpdating latest Weekly...")
    page = get_latest_page(weekly_db_id, "Start (Date)")
    if not page:
        print("No Weekly record found. Skipping.")
        return
    title = page["properties"].get("Title", {}).get("title", [])
    label = title[0]["plain_text"] if title else page["id"]
    update_relation(page["id"], "WBS Items", wbs_ids)
    print(f"✅ Weekly updated: {label}")

# ----------------------------------------------------------------
# Step 3: Update latest Monthly
# ----------------------------------------------------------------

def update_monthly(wbs_ids):
    print("\nUpdating latest Monthly...")
    page = get_latest_page(monthly_db_id, "Start (Date)")
    if not page:
        print("No Monthly record found. Skipping.")
        return
    title = page["properties"].get("Title", {}).get("title", [])
    label = title[0]["plain_text"] if title else page["id"]
    update_relation(page["id"], "WBS Items", wbs_ids)
    print(f"✅ Monthly updated: {label}")

# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------

if __name__ == "__main__":
    wbs_ids = collect_wbs_ids()
    if wbs_ids:
        update_weekly(wbs_ids)
        update_monthly(wbs_ids)
    else:
        print("No WBS items found. Nothing to update.")
