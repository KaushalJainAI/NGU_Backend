# AI Search Engine Integration

The NGU Spices backend leverages Large Language Models (LLMs) to heavily optimize user search queries by automatically generating extensive lists of regional, phonetic, and translated synonyms for every product and combo.

This document describes how the AI search engine (`SpiceSearchEngine`) functions natively within Django.

## Architecture

The AI engine lives primarily in `products/recommendations.py`.

1. **Provider:** [Perplexity AI](https://www.perplexity.ai/) (`sonar` model) using their OpenAI-compatible Chat API.
2. **Framework:** [Langchain](https://python.langchain.com/) for building Prompts and parsing JSON Outputs.
3. **Storage:** Standard SQL via `ProductSearchKB` and `ProductComboSearchKB` models storing array-like data in PostgreSQL/SQLite `JSONField`s.
4. **Matching algorithm:** `FuzzyWuzzy` token-set rations for rapid spelling-mistake correction.

## The Search Logic

When a user searches for `"haldi"` on the e-commerce frontend:
1. The backend performs a high-speed fuzzy match (`fuzzywuzzy.process.extract`).
2. It compares the user query against the `JSONField` arrays of synonyms pre-generated directly by the LLM.
3. Because the LLM was previously prompted to generate regional Indian variations, "turmeric powder" will instantly match to "haldi", "pasupu", or "manjal".

## Non-Blocking Background Generation

Because generating 25+ permutations via an external LLM API takes several seconds, generating these keys *synchronously* during a Django `post_save` signal would hang the application.

To solve this, the generation relies on **native Python background threads** (`products/utils.py -> run_in_background`), circumventing the need for Celery.

### Generation Flow
1. Admin edits a `Product` in the Django Admin Panel and clicks Save.
2. The `post_save` signal (`products/signals.py`) fires instantly.
3. The signal delegates the `a_ensure_search_kb` method to a background daemon thread.
4. The HTTP response immediately returns (0ms delay for the Admin).
5. In the background thread, `asyncio` is used to trigger Langchain's `ainvoke()` over the network.
6. The synonym permutations are received, stored in `ProductSearchKB`, and the background thread explicitly calls `django.db.close_old_connections()` to prevent Postgres connection-pool exhaustion.

## Updating the Model

If you change your Perplexity Account, update the `PERPLEXITY_API_KEY` (or `LLM_API_KEY`) within your `.env` string. The search engine dynamically reads this on initialization.
