# Notion Reporting System — Jira Sync

A Python script to import and sync Jira issues into the **Notion Reporting System** template.

- Epics → WBS database
- Tasks/Stories → Ticket database (linked to their parent Epic in WBS)

---

## Prerequisites

- Python 3.8+
- A [Notion](https://notion.so) account with the Reporting System template installed
- A [Jira](https://www.atlassian.com/software/jira) account (Free plan works)

---

## Setup

### 1. Clone this repository

```bash
git clone https://github.com/YOUR_USERNAME/notion-jira-sync.git
cd notion-jira-sync
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
NOTION_TICKET_DB_ID=your_ticket_database_id
NOTION_WBS_DB_ID=your_wbs_database_id

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
4. In Notion, open each database (Ticket DB and WBS DB), click **⋯ > Connect to** and select your integration

### Notion Database IDs

Open the database in Notion in your browser. The URL looks like:
```
https://www.notion.so/your-workspace/326124302a49...?v=...
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
python sync.py
```

### What it does

1. **Step 1 — Sync Epics to WBS**: Fetches all Jira Epics and creates or updates records in your Notion WBS database (Title, Ticket Number, Planned Start, Planned End).
2. **Step 2 — Sync Tickets**: Fetches Tasks and Stories, creates or updates records in your Notion Ticket database (Title, Status, Description, Estimate, Dates), and links each ticket to its parent Epic in WBS.

### Sync scope

By default, the script syncs:
- All issues that are **not Done**
- Issues that were **updated within the last 30 days** (even if Done)

To change the window, edit `SYNC_DAYS` in `sync.py`:

```python
SYNC_DAYS = 30  # days
```

---

## File Structure

```
notion-jira-sync/
├── sync.py          # Main sync script
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
