from dotenv import load_dotenv
import os
import requests
from jira import JIRA

load_dotenv()

jira = JIRA(
    server=os.environ["JIRA_SERVER"],
    basic_auth=(os.environ["JIRA_EMAIL"], os.environ["JIRA_API_TOKEN"])
)

notion_token = os.environ["NOTION_TOKEN"]
ticket_db_id = os.environ["NOTION_TICKET_DB_ID"]
wbs_db_id = os.environ["NOTION_WBS_DB_ID"]
headers = {
    "Authorization": f"Bearer {notion_token}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

SYNC_DAYS = 30  # Number of days to include completed tickets in sync

# ----------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------

def get_existing_pages(db_id, property_name="Ticket Number"):
    """Return existing records in the DB as {ticket_number: page_id}"""
    existing = {}
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = requests.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=headers,
            json=body
        ).json()
        for page in res.get("results", []):
            val = page["properties"].get(property_name, {}).get("rich_text", [])
            if val:
                existing[val[0]["plain_text"]] = page["id"]
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return existing

def get_wbs_page_id(ticket_number):
    """Return the page ID in WBS DB that matches the given Ticket Number"""
    res = requests.post(
        f"https://api.notion.com/v1/databases/{wbs_db_id}/query",
        headers=headers,
        json={
            "filter": {
                "property": "Ticket Number",
                "rich_text": {"equals": ticket_number}
            }
        }
    ).json()
    results = res.get("results", [])
    return results[0]["id"] if results else None

def status_to_notion(jira_status):
    mapping = {
        "To Do": "To Do",
        "In Progress": "In Progress",
        "Done": "Done",
        "Blocked": "Blocked",
    }
    return mapping.get(jira_status, jira_status)

def update_notion_page(page_id, properties):
    """Update properties of an existing Notion page"""
    requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=headers,
        json={"properties": properties}
    )

# ----------------------------------------------------------------
# Step 1: Import / update Epics into WBS DB
# ----------------------------------------------------------------

def import_epics(issues):
    print("\n--- Step 1: Syncing Epics to WBS ---")
    existing = get_existing_pages(wbs_db_id)
    imported = updated = skipped = 0

    for epic in issues:
        if epic.fields.issuetype.hierarchyLevel < 1:
            continue

        key = epic.key
        fields = epic.fields
        start_date = getattr(fields, 'customfield_10015', None)
        due = fields.duedate

        properties = {
            "Title": {"title": [{"text": {"content": fields.summary or key}}]},
            "Ticket Number": {"rich_text": [{"text": {"content": key}}]},
        }
        if start_date:
            properties["Planned Start"] = {"date": {"start": start_date}}
        if due:
            properties["Planned End"] = {"date": {"start": due}}

        if key in existing:
            update_notion_page(existing[key], properties)
            print(f"🔄 WBS Updated: {key} - {fields.summary}")
            updated += 1
        else:
            res = requests.post(
                "https://api.notion.com/v1/pages",
                headers=headers,
                json={"parent": {"database_id": wbs_db_id}, "properties": properties}
            )
            if res.status_code == 200:
                print(f"✅ WBS Imported: {key} - {fields.summary}")
                imported += 1
            else:
                print(f"❌ WBS Failed: {key} - {res.json()}")

    print(f"WBS Done. Imported: {imported}, Updated: {updated}, Skipped: {skipped}")

# ----------------------------------------------------------------
# Step 2: Import / update Tasks and Stories into Ticket DB
# ----------------------------------------------------------------

def import_tickets(issues):
    print("\n--- Step 2: Syncing Tickets ---")
    existing = get_existing_pages(ticket_db_id)
    imported = updated = 0

    for issue in issues:
        if issue.fields.issuetype.hierarchyLevel >= 1:
            continue

        key = issue.key
        fields = issue.fields
        status = status_to_notion(fields.status.name)
        due = fields.duedate
        estimate = getattr(fields, 'customfield_10016', None)
        start_date = getattr(fields, 'customfield_10015', None)
        parent = getattr(fields, 'parent', None)
        epic_key = parent.key if parent else None

        properties = {
            "Title": {"title": [{"text": {"content": fields.summary or key}}]},
            "Ticket Number": {"rich_text": [{"text": {"content": key}}]},
            "Description": {"rich_text": [{"text": {"content": str(fields.description or "")[:2000]}}]},
            "Status": {"multi_select": [{"name": status}]},
        }
        if due:
            properties["Due"] = {"date": {"start": due}}
        if start_date:
            properties["Planned Start"] = {"date": {"start": start_date}}
        if estimate:
            properties["Estimate (h)"] = {"number": float(estimate)}

        wbs_page_id = None
        if epic_key:
            wbs_page_id = get_wbs_page_id(epic_key)
            if wbs_page_id:
                properties["Master Schedule (WBS)"] = {"relation": [{"id": wbs_page_id}]}

        if key in existing:
            update_notion_page(existing[key], properties)
            print(f"🔄 Ticket Updated: {key} - {fields.summary}")
            updated += 1
        else:
            res = requests.post(
                "https://api.notion.com/v1/pages",
                headers=headers,
                json={"parent": {"database_id": ticket_db_id}, "properties": properties}
            )
            if res.status_code == 200:
                ticket_page_id = res.json()["id"]
                print(f"✅ Ticket Imported: {key} - {fields.summary}")
                imported += 1

                # Also update the Tickets relation on the WBS side
                if epic_key and wbs_page_id:
                    wbs_res = requests.get(
                        f"https://api.notion.com/v1/pages/{wbs_page_id}",
                        headers=headers
                    ).json()
                    existing_tickets = wbs_res.get("properties", {}).get("Tickets", {}).get("relation", [])
                    existing_tickets.append({"id": ticket_page_id})
                    requests.patch(
                        f"https://api.notion.com/v1/pages/{wbs_page_id}",
                        headers=headers,
                        json={"properties": {"Tickets": {"relation": existing_tickets}}}
                    )
            else:
                print(f"❌ Ticket Failed: {key} - {res.json()}")

    print(f"Ticket Done. Imported: {imported}, Updated: {updated}")

# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------

if __name__ == "__main__":
    print("Fetching Jira issues...")
    jql = (
        f'project={os.environ["JIRA_PROJECT_KEY"]} AND '
        f'(statusCategory != Done OR updated >= -{SYNC_DAYS}d) '
        f'ORDER BY created ASC'
    )
    issues = jira.search_issues(jql, maxResults=500)
    print(f"Found {len(issues)} issues.")

    import_epics(issues)   # Step 1: WBS must come first
    import_tickets(issues) # Step 2: Tickets link back to WBS
