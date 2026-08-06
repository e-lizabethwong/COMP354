# Testing Guide — Hack Canada Sponsor Research Pipeline

> For anyone who wants to run and test the pipeline locally.

---

## Prerequisites

Before starting, make sure you have the following installed:

- **Python 3.11 or higher** — check with `python --version` in the terminal
- **Git** — to clone the repo

---

## Step 1 — Clone the repo (terminal)

```bash
git clone https://github.com/e-lizabethwong/COMP354.git
cd COMP354
```

---

## Step 2 — Create a virtual environment (terminal)

This keeps all dependencies isolated from your system Python.

> **Note for Windows users:** Use `python` instead of `python3`.
> Windows does not have a `python3` by default.

```bash
# Mac/Linux:
python3 -m venv venv

# Windows:
python -m venv venv
```

Then activate it:

```bash
# On Windows (Git Bash):
source venv/Scripts/activate

# On Windows (PowerShell):
venv\Scripts\Activate.ps1

# On Windows (Command Prompt):
venv\Scripts\activate.bat

# On Mac/Linux:
source venv/bin/activate
```

You should see `(venv)` appear at the start of your terminal prompt.

> **Alternative — Docker:** If you have Docker Desktop installed, you can skip
> Steps 2-3 and use Docker instead. See `DOCKER.md` for instructions.

---

## Step 3 — Install dependencies (terminal)

```bash
# Mac/Linux:
pip install -r requirements.txt
python3 -m playwright install chromium

# Windows:
pip install -r requirements.txt
python -m playwright install chromium
```

> **Note:** `playwright install chromium` downloads a browser (~300MB) used for web scraping.
> This only needs to be done once.

---

## Step 4 — Create your environment variables `.env` file (terminal)

Copy the example file and fill in your details:

```bash
# Mac/Linux:
cp env.example .env

# Windows (PowerShell):
Copy-Item env.example .env

# Windows (Command Prompt):
copy env.example .env
```

Open `.env` in any text editor and fill in the following:

### If using OpenAI/ChatGPT API (credits required):

```
LLM_PROVIDER=openai
OPENAI_API_KEY=your-openai-key-here
LLM_MODEL=gpt-4o-mini
```

### If using Anthropic/Claude API (credits required):

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-anthropic-key-here
LLM_MODEL=claude-sonnet-4-6
```

### If using Google/Gemini API (credits required):

```
LLM_PROVIDER=google
GOOGLE_API_KEY=your-google-key-here
LLM_MODEL=gemini-2.0-flash
```

### If using Playwright only (no API key required):

Leave the `LLM_PROVIDER`, `API_KEY`, and `LLM_MODEL` sections as they are.

Steps 6 and 7 will work without an API key.

### Email generator details (optional but recommended):

```
SENDER_NAME=Your Full Name
SENDER_TITLE=Your Title
EVENT_NAME=Your Hackathon Event
EVENT_DATE=Your Hackathon Event Date
EVENT_VENUE=Your Hackathon Event Venue
```

### Optional settings

For faster local testing, reduce these in your .env:

```
MAX_CRAWL_PAGES=5
MAX_EMAILS_PER_SITE=3
```

> **Important:** Never commit your `.env` file to git. It is already in `.gitignore`.
>
> **Windows users:** If `cp` doesn't work, use `Copy-Item` in PowerShell or
> `copy` in Command Prompt as shown above.

---

## Step 5 — Verify the setup (terminal)

Run these quick checks before testing the full pipeline:

> **Windows users:** Replace `python3` with `python` in all commands below.

```bash
# Check all imports work
python3 -c "from sponsor_pipeline.config import Settings; from sponsor_pipeline.models import Company, RawLead; from sponsor_pipeline.orchestrator import PipelineOrchestrator; print('All imports OK')"

# Check settings load correctly
python3 -c "
from sponsor_pipeline.config import Settings
s = Settings.from_env(require_llm=False)
print(f'Provider: {s.llm_provider}')
print(f'Model: {s.llm_model}')
print(f'Sender: {s.sender_name}')
print('Settings OK')
"

# Check CLI application is working
python3 main.py --help
```

All three should run without errors. The last command should show all available
pipeline commands: `run`, `discover`, `score`, `research`, `contacts`, `export`, `scrape`.

---

## Step 6 — Test the scraper (no API key needed)

In terminal, test that Playwright can crawl a website and extract emails:

> **Windows users:** Replace `python3` with `python` in all commands below.

```bash
python3 main.py scrape --url https://conuhacks.io --output test_emails.txt
cat test_emails.txt
```

The pipeline now includes structured logging. You should see output like this while it runs:

```bash
2026-07-10 12:48:38,255 | INFO | sponsor_pipeline.cli | Command selected: scrape
2026-07-10 12:48:38,643 | INFO | sponsor_pipeline.cli | Starting scrape for 1 URL(s)
2026-07-10 12:48:38,643 | INFO | sponsor_pipeline.cli | Scraping 1/1: https://conuhacks.io
2026-07-10 12:48:38,643 | INFO | sponsor_pipeline.services.scraper | Starting crawl: https://conuhacks.io
2026-07-10 12:48:45,072 | INFO | sponsor_pipeline.services.scraper | Crawled: https://conuhacks.io
2026-07-10 12:48:45,083 | INFO | sponsor_pipeline.services.scraper | Found email: sponsor.hackconcordia@ecaconcordia.ca
2026-07-10 12:48:50,198 | INFO | sponsor_pipeline.services.scraper | Finished crawl: https://conuhacks.io (5 pages, 3 emails)
2026-07-10 12:48:50,301 | INFO | sponsor_pipeline.cli | Wrote scrape output to test_emails.txt
```

Expected content of `test_emails.txt`:

```bash
Website: https://conuhacks.io
sponsor.hackconcordia@ecaconcordia.ca
team.hackconcordia@ecaconcordia.ca
```

> **Note:** To test with a different website, replace the URL (https://conuhacks.io) with any other site.

You can also scrape multiple URLs from the seed file:

```bash
python3 main.py scrape data/hackathon_urls.txt --output test_emails.txt
```

> **Warning:** The full batch scrape with 21 URLs takes 10-20 minutes depending
> on your network. For a quick test, use the single `--url` option above.
> To speed it up, set `MAX_CRAWL_PAGES=5` in your `.env` file.

---

## Step 7 — Test the email generators (no API key needed)

> **Windows users:** Replace `python3` with `python` in all commands below.

In terminal, test the initial outreach email generator:

```bash
python3 generate_initial_outreach.py
```

When prompted:

- **Company name:** `Any company name` (press Enter)
- **Recipient name:** optional (press Enter)
- **Local recipient:** `y` or `n` (press Enter)

You should see a fully formatted sponsorship email with your name and event details
loaded from your `.env` file.
No logging output is expected here.

Test the follow-up email generator:

```bash
python3 generate_followup_email.py
```

Same prompts as above.

> **Note:** If the sender name shows "Your Name Here" instead of your name,
> make sure `SENDER_NAME` is filled in your `.env` file.

---

## Step 8 — Run the full pipeline (API key required)

> **Note:** This makes real API calls and uses credits. Run it once to verify it works.
>
> **Windows users:** Replace `python3` with `python` in all commands below.
>
> The pipeline supports all three LLM providers: Set `LLM_PROVIDER` in your
> `.env` to `anthropic`, `openai`, or `google` and provide the matching API key.

### Option A — Run each stage separately (recommended for testing)

```bash
# Stage 1: Discover companies from hackathon websites
python3 main.py discover
```

Expected log output:

```
2026-07-10 | INFO | sponsor_pipeline.cli | Command selected: discover
2026-07-10 | INFO | sponsor_pipeline.orchestrator | Setting up pipeline services
2026-07-10 | INFO | sponsor_pipeline.orchestrator | Pipeline services ready
2026-07-10 | INFO | sponsor_pipeline.orchestrator | Starting discovery
```

```bash
# Stage 2: Score discovered companies (uses LLM credits)
python3 main.py score
```

Expected log output:

```
2026-07-10 | INFO | sponsor_pipeline.cli | Command selected: score
2026-07-10 | INFO | sponsor_pipeline.services.scoring | Requesting sponsor score for [company] using X evidence item(s)
2026-07-10 | INFO | sponsor_pipeline.llm.client | Initializing LLM client: provider=anthropic, model=claude-sonnet-4-6
2026-07-10 | INFO | sponsor_pipeline.llm.client | Sending LLM completion request
2026-07-10 | INFO | sponsor_pipeline.llm.client | Received LLM completion response
```

```bash
# Stage 3: Research high-scoring companies (uses LLM credits)
python3 main.py research

# Stage 4: Find contacts for researched companies (uses LLM credits)
python3 main.py contacts

# Export results to CSV and Markdown
python3 main.py export --output-dir results/
```

### Option B — Run the full pipeline in one command (terminal)

```bash
python3 main.py run
```

Expected log output:

```
2026-07-10 | INFO | sponsor_pipeline.orchestrator | Starting full pipeline
2026-07-10 | INFO | sponsor_pipeline.orchestrator | Filter result: X passed, Y rejected below threshold 6.0
2026-07-10 | INFO | sponsor_pipeline.orchestrator | Full pipeline finished: discovered=X, scored=X, researched=X, outreach_ready=X
```

---

## Step 9 — Check the results (terminal)

After running the pipeline, check what was produced:

```bash
# Verify the database was created
ls -la data/

# Check exported results (if you ran export)
ls results/
```

> **Note:** Pipeline results are stored in a SQLite database at `data/sponsors.db`.
> This is a binary file, so do not try to open it with a text editor.
>
> To inspect the data, use the built-in `sqlite3` tool (no install needed):
>
> ```bash
> # List all tables
> sqlite3 data/sponsors.db ".tables"
>
> # View scored companies
> sqlite3 data/sponsors.db "SELECT data FROM scores LIMIT 5;"
> ```
>
> The `results/` folder (created by the `export` command) contains:
>
> - `prospects.csv` — outreach-ready companies in CSV format
> - `*.md` files — individual Markdown reports per company

---

## Troubleshooting

**"`python3` not found" (Windows)**
Windows does not have a `python3` command by default. Use `python` instead
of `python3` for all commands in this guide.

**"No module named X"**
Make sure your virtual environment is activated (`venv\Scripts\activate` on
Windows, `source venv/bin/activate` on Mac/Linux) and you ran
`pip install -r requirements.txt`.

**"playwright: command not found"**
Use `python -m playwright install chromium` (Windows) or
`python3 -m playwright install chromium` (Mac/Linux) instead.

**".env file not found" or "API key not set"**
Make sure your `.env` file exists and has the correct API key for your
chosen provider. On Windows use `Copy-Item env.example .env` in PowerShell
or `copy env.example .env` in Command Prompt.

**"LLM_PROVIDER not supported"**
Check that `LLM_PROVIDER` in your `.env` is exactly one of:
`anthropic`, `openai`, or `google`.

**Pipeline produces no results**
Check `data/hackathon_urls.txt` exists and has valid URLs. Run the
scrape test first to confirm Playwright is working.

**Batch scrape is taking too long**
Reduce `MAX_CRAWL_PAGES=5` and `MAX_EMAILS_PER_SITE=3` in your `.env`
for faster testing. The default values are optimized for production use.

**Need a consistent environment across all operating systems?**
Use Docker. See `DOCKER.md` for setup instructions.

---

_Last updated: July 2026 | COMP354 — Introduction to Software Engineering | Concordia University_
