# Synthetic finance bakeoff fixture

This fixture is entirely fictional and contains no owner financial data. It is
designed for disposable staging only. Amounts are signed from the account's
perspective: positive is money in, negative is money out.

The common columns are:

```text
external_id,date,account,payee,amount,category,transfer_account,memo
```

Import sequence:

1. `batch-a.csv` establishes the baseline.
2. Import `batch-a.csv` again unchanged; a safe importer should not duplicate
   the 12 baseline rows.
3. `batch-b.csv` overlaps four rows from A and adds a nearby but distinct
   purchase plus new recurring activity.
4. Correct `tx-grocery-001` in the candidate UI, then import B again; record
   whether the manual correction survives.
5. `batch-c.csv` adds a refund, a new paycheck, and a deliberate transfer pair.

The expected canonical invariants are recorded in `expected.json`. Candidates
may represent transfers, pending state, splits, or credit-card payments
differently; those differences belong in the acceptance record.

Never point these imports at production finance or real provider accounts.
