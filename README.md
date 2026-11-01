# Pramaan

> New rules, explained in your language, every line proved.

Built during Forge '26 by team CTRL + AI (NIT Warangal).

## Tests

```
cd backend
pytest -q           # offline tests only (live tests are excluded)
pytest -m live      # live checks against the real RBI/SEBI/PIB sites and Groq; run on their own, one run at a time
```

Groq's free tier allows 8,000 tokens per minute per model, so do not run `pytest -m live` while the app or another script is analysing documents.
