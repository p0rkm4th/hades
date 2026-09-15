# Recipe URL ingestion dogfood

Status: **PASS / synthetic dogfood; owner acceptance remains**.

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
- changing a reviewed quantity invalidates the preview, and current Grocy
  state is revalidated before an apply;

Still required before this is a production capability:

- register the staged MCP server in the deployed Hermes profile;
- test against a representative public structured-data site and verify URL
  fetching in the owner-facing path (`scripts/test-recipe-public-url.sh`);
- exercise a representative structured-data site, a messy page, a duplicate,
  a changed re-import, serving resize, and shortage/add-missing composition;
- perform owner-visible acceptance.

The opt-in public acceptance currently passes against King Arthur Baking's
Banana Bread page, producing a title, 14 ingredients, and 8 instruction steps
on 2026-09-15. Simply Recipes and Allrecipes also passed the same live check.
BBC Good Food returned HTTP 402 during evaluation and is recorded as an
upstream access limitation, not a parser failure. Fetched pages without usable
Recipe JSON-LD now receive the same conservative visible-text section parser
used for pasted HTML. Successful fallback results are explicitly marked
review-required; pages without a clear title and Ingredients section still
fail rather than producing an inferred recipe.

The normalized contract now also accepts explicitly sectioned pasted recipe
text plus raw pasted HTML or JSON-LD through `recipe_paste_preview`. These
inputs converge on the same ingredient, serving, instruction, review, Grocy
resolution, and apply-plan path as URL ingestion. The contract test verifies
that underspecified paste is rejected and that preview remains write-free.
