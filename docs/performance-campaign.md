# Performance acceptance

Performance checks are bounded by request type and do not query unrelated
services. Measure simple inventory lookup, broad status composition,
multi-source diagnosis, inference catalog retrieval, and actual inference
latency separately. Record source latency, cache use, freshness, and timeout
behavior without presenting catalog latency as generation time.

Use synthetic endpoints in CI. Private service URLs, model placement, host load,
and live measurements belong in `hades-infra`. A performance snapshot is not a
historical trend or root-cause diagnosis.
