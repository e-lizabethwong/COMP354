# Hack Canada Sponsor Research Pipeline

An AI-assisted pipeline that automates sponsor discovery, scoring, research, and outreach for student hackathon organizations. Built as a Version 1.0 prototype by a student team at Concordia University.

---

## What it does

1. **Discovery** — crawls hackathon websites and job boards to find potential sponsors
2. **Scoring** — evaluates each company across six dimensions using an LLM
3. **Research** — generates a detailed sponsorship report per high-scoring company
4. **Contacts** — identifies the best person to reach out to at each company
5. **Outreach** — generates personalized initial and follow-up emails

---

## Quick start

### Version

```bash
python main.py --version
# formats as: Hack Canada Sponsor Research Pipeline X.X.X (prototype)
```


### Prerequisites

- Python 3.11+
- Git
- An API key for Anthropic, OpenAI, or Google

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/e-lizabethwong/COMP354.git
cd COMP354

# 2. Create and activate virtual environment
# Mac/Linux:
python3 -m venv venv && source venv/bin/activate
# Windows:
python -m venv venv && venv\Scripts\activate
# Windows (Git Bash):
python -m venv venv && source venv/Scripts/activate

# 3. Install dependencies
pip install -r requirements.txt
python -m playwright install chromium

# 4. Configure environment
cp env.example .env
# Edit .env and add your API key
```

### Run

```bash
# Test the scraper (no API key needed)
python main.py scrape --url https://conuhacks.io --output emails.txt

# Run the full pipeline
python main.py run

# Or run stage by stage
python main.py discover
python main.py score
python main.py research
python main.py contacts
python main.py export --output-dir results/
```

> **Windows users:** Use `python` instead of `python3`

---

## Project structure

```
sponsor_pipeline/
    adapters/        # Company discovery sources (MLH, hackathon sites, job boards)
    llm/             # Provider-agnostic LLM gateway (Anthropic, OpenAI, Google)
    persistence/     # SQLite storage layer
    prompts/         # LLM prompt templates
    export/          # CSV and Markdown report exporter
    services/        # Core pipeline services
        scraper.py           # Playwright-based web crawler
        scoring.py           # Company scoring service
        research.py          # Research report generator
        contacts.py          # Contact discovery service
        discovery.py         # Company discovery orchestration
        filter.py            # Lead filtering by score threshold
        sponsor_evaluator/   # Rich 6-dimension evaluator module
data/
    hackathon_urls.txt   # Seed URLs for discovery
    sponsors.db          # SQLite database (created on first run)
results/                 # Exported reports (created by export command)
```

---

## LLM providers

The pipeline supports three providers — set `LLM_PROVIDER` in your `.env`:

| Provider           | Key                 | Default model       |
| ------------------ | ------------------- | ------------------- |
| Anthropic (Claude) | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| OpenAI (ChatGPT)   | `OPENAI_API_KEY`    | `gpt-4o-mini`       |
| Google (Gemini)    | `GOOGLE_API_KEY`    | `gemini-2.0-flash`  |

---

## Docker

A Docker environment is available for consistent cross-platform testing.
See `DOCKER.md` for instructions.

---

## Testing

For detailed setup and testing instructions see `TESTING_GUIDE.md`.

---

## Course context

Built for **COMP354 — Introduction to Software Engineering** at Concordia University (Summer 2026).
This is Version 1.0 of a larger planned system for HackConcordia's sponsor research operations.

---

## Team

| Name               | Role                                       |
| ------------------ | ------------------------------------------ |
| Elizabeth Wong     | Scraper Management / Repo Owner            |
| Matthieu Geahel    | Project Lead / Architectural Core Pipeline |
| Daniel Henao Duque | Backend Developer & Integration Lead       |
| Alexander Hristov  | DevOps & Infrastructure Lead               |
| Abdallah Khirallah | AI Scraper Implementation Lead             |
| Rojin Nik Nejad    | Quality Assurance Mac                      |
| Muhetaer Abidan    | Diagrams / Macro Level Planning            |
| Galy Kevork        | System Documentation / Project Report      |
| Fady Rizkall       | Quality Assurance Linux                    |
