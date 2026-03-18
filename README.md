# Notion Reporting System — Scripts

Two Python scripts to automate your **Notion Reporting System** template.

| Script | What it does |
|---|---|
| `sync.py` | Jira → Notion: imports Epics and Tasks into the Work Items database with hierarchy, status, and category |
| `rollup.py` | Notion → Notion: links Work Items to your latest Weekly (Task level) and Monthly (Epic level) reports based on Daily ticket logs |

---

## Prerequisites

- Python 3.8+
- A [Notion](https://notion.so) account with the Reporting System template installed
- A [Jira](https://www.atlassian.com/software/jira) account — Free plan works (`sync.py` only)

---

## Setup

### 1. Clone this repository

```bash
git clone https://github.com/dhatano/notion-reporting-system.git
cd notion-reporting-system
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate       # macOS/Linux
# venv\Scripts\activate        # Windows

pip install python-dotenv requests jira
```

### 3. Configure credentials

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
NOTION_TOKEN=your_notion_integration_token
NOTION_WORK_ITEMS_DB_ID=your_work_items_database_id
NOTION_DAILY_DB_ID=your_daily_database_id
NOTION_WEEKLY_DB_ID=your_weekly_database_id
NOTION_MONTHLY_DB_ID=your_monthly_database_id

JIRA_SERVER=https://yourcompany.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your_jira_api_token
JIRA_PROJECT_KEY=YOUR_PROJECT_KEY
```

See below for how to obtain each value.

---

## Getting Your Credentials

### Notion Integration Token

1. Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **New integration** → give it a name → Submit
3. Copy the **Internal Integration Token**
4. In Notion, open the top-level **Reporting System** page, click **⋯ > Connect to** and select your integration — this grants access to all child databases at once

### Notion Database IDs

Open the database in Notion in your browser. The URL looks like:
```
https://www.notion.so/326124302a49...?v=...
```
The 32-character string before the `?` is the database ID.

### Jira API Token

1. Go to [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**
3. Copy and store it safely — it won't be shown again

---

## Usage

```bash
source venv/bin/activate   # macOS/Linux

# Jira → Notion
python sync.py

# Notion → Notion (Work Items rollup to Weekly/Monthly)
python rollup.py
```

### sync.py

Imports all Jira issues into the **Work Items** database in two passes:

1. **Epics first** — creates or updates Epic records (Type: Epic) with Planned Start/End
2. **Tasks second** — creates or updates Task records (Type: Task) with Status, Category, Description, Estimate, and a link to their parent Epic

**Category mapping** (from Jira issue type):

| Jira issue type | Category |
|---|---|
| Story | Feature |
| Task | Task |
| Bug | Bug |
| Change Request | Change Request |

**Sync scope** — by default syncs:
- All issues that are **not Done**
- Issues **updated within the last 30 days** (even if Done)

To change the window, edit `SYNC_DAYS` in `sync.py`:

```python
SYNC_DAYS = 30  # days
```

### rollup.py

Aggregates Work Items into Weekly and Monthly reports:

1. Collects all Tasks linked in Daily **Tickets Worked**
2. Updates the latest **Weekly** record's WBS Items with those Tasks
3. Traverses each Task's **Parent Item** to find its Epic
4. Updates the latest **Monthly** record's WBS Items with those Epics

If no Weekly or Monthly record exists (or has no Start Date), that step is silently skipped.

---

## Notion DB Setup

The Work Items database requires the following properties:

| Property | Type |
|---|---|
| Title | Title |
| Ticket Number | Text |
| Type | Multi-select (Epic / Task) |
| Category | Multi-select (Feature / Bug / Task / Change Request) |
| Status | Multi-select (To Do / In Progress / Done / Blocked) |
| Planned Start | Date |
| Planned End | Date |
| Estimate (h) | Number |
| Description | Text |
| Parent Item | Relation (self — auto-created by Notion sub-items feature) |

Enable **Sub-items** in the database settings to get the Parent Item / Sub Item relations automatically.

---

## File Structure

```
notion-reporting-system/
├── sync.py          # Jira → Notion sync
├── rollup.py        # Notion → Notion Work Items rollup
├── .env             # Your credentials (never commit this)
├── .env.example     # Credential template
└── README.md
```

---

## Security Note

**Never commit `.env` to Git.** It contains API tokens that grant access to your Notion workspace and Jira account. The `.gitignore` in this repo excludes it by default.

---

## License

MIT
