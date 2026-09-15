# Recipe ingestion

Status: **STAGED**.

This is the acquisition half of recipe ingestion. It accepts a bounded public
HTTP(S) URL or supplied HTML, extracts the first `Schema.org/Recipe` JSON-LD
object, and returns one normalized preview contract. The normalized object
preserves each original ingredient line, a conservative quantity/unit parse,
instructions, source URL, and review warnings.

The module intentionally does not write Grocy, create products, or use model
text to fill missing fields. The next integration layer must resolve each
ingredient against Grocy's canonical products, present a preview, and require
explicit confirmation before creating the recipe and its `recipes_pos` rows.
Unresolved or ambiguous products remain review items.

The first extractor is Schema.org JSON-LD because it is the common upstream
contract and is documented by Schema.org. Site-specific scraping and browser
fallback remain deferred until representative dogfood demonstrates that the
structured-data path is insufficient.

Contract test:

```text
bash scripts/test-recipe-ingest-contract.sh
```

The URL fetch rejects non-HTTP(S), loopback, private, link-local, and reserved
targets and caps the response at 2 MiB. It is an extraction boundary, not a
general-purpose fetch proxy.
