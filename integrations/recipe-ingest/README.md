# Recipe ingestion

Status: **STAGED**.

This is the acquisition half of recipe ingestion. It accepts a bounded public
HTTP(S) URL or supplied HTML, extracts the first `Schema.org/Recipe` JSON-LD
object, and returns one normalized preview contract. The normalized object
preserves each original ingredient line, a conservative quantity/unit parse,
instructions, source URL, and review warnings.

The module intentionally does not write Grocy during extraction or product
resolution, create products, or use model text to fill missing fields. Its
`GrocyRecipeImporter` builds a reviewable plan, requires explicit confirmation,
creates the recipe and its `recipes_pos` rows through Grocy's generic object
API, and reads both back before reporting success. Unresolved or ambiguous
products remain review items. A transport failure after a write is reported as
`OUTCOME UNKNOWN` and must be reconciled before retry.

The first extractor is Schema.org JSON-LD because it is the common upstream
contract and is documented by Schema.org. Site-specific scraping and browser
fallback remain deferred until representative dogfood demonstrates that the
structured-data path is insufficient.

Contract test:

```text
bash scripts/test-recipe-ingest-contract.sh
```

The staged MCP server is registered in the Hermes template as a private stdio
server. The generated profile substitutes `HADES_HERMES_WORKING_DIRECTORY` and
the protected `HADES_GROCY_API_KEY_FILE`; `HADES_GROCY_URL` is optional and
defaults to the private loopback Grocy URL. Keep it narrowed to recipe turns.
Its two tools are deliberately separate: `recipe_url_preview` and
`recipe_url_apply`.

The URL fetch rejects non-HTTP(S), loopback, private, link-local, and reserved
targets and caps the response at 2 MiB. It is an extraction boundary, not a
general-purpose fetch proxy.
