# Recipe URL ingestion dogfood

Status: **STAGED / synthetic dogfood green for the structured-data path**.

The disposable contract test exercises the owner-equivalent flow against a
fake canonical Grocy transport:

```text
Scotty: grab this recipe https://recipes.example.test/tacos
HADES: previewed Weeknight Tacos; ground beef and salsa match Grocy; confirm?
Scotty: import it
HADES: requires explicit confirmation; no write performed
Scotty: yes, import it
HADES: recipe created and read back from Grocy
```

The repeatable disposable real-Grocy proof is
`bash scripts/test-recipe-grocy-disposable.sh`. It uses the pinned image in a
fresh temporary `/config`, creates only synthetic products/units, verifies
preview and confirmation behavior, and confirms the recipe plus both
`recipes_pos` rows through Grocy's canonical API. The temporary container is
removed after the run; no live household state or credential is used.

It also verifies:

- JSON-LD graphs containing unrelated objects select the Recipe object;
- raw ingredient lines and source URL remain in the preview evidence;
- quantity/unit parsing is conservative and emits review warnings;
- exact Grocy product and quantity-unit matches produce an apply plan;
- missing or duplicate products prevent the plan from being applied;
- duplicate recipe titles are rejected before mutation;
- zero, negative, fractional, missing, and oversized serving counts are
  rejected rather than truncated or defaulted;
- zero, negative, malformed, oversized, and duplicate ingredient quantities are
  rejected before a write plan is produced;
- a lost response after recipe or ingredient mutation is `OUTCOME UNKNOWN`;
- confirmation is required and a preview alone performs no write.

Still required before this is a production capability:

- register the staged MCP server in the deployed Hermes profile;
- test against a representative public structured-data site and verify URL
  fetching in the owner-facing path;
- exercise a representative structured-data site, a messy page, a duplicate,
  a changed re-import, serving resize, and shortage/add-missing composition;
- perform owner-visible acceptance.

The fallback for pages without usable Recipe JSON-LD is intentionally not
implemented yet. HADES must ask for pasted recipe text or report that the URL
requires a later supported extraction fallback rather than hallucinating a
recipe.
