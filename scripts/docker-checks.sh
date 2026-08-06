set -eu

# python -m unittest discover -s tests
pytest tests
python -m compileall sponsor_pipeline tests main.py generate_initial_outreach.py generate_followup_email.py batch_scrape_from_urls.py scrape_single_website.py
python -m ruff check . --extend-ignore EXE002