# PROPER v1/v2 artifact migration

The `codex/proper-v2-unified` branch introduces explicit version namespaces for
configuration, documentation, experiment entry points, curated outputs, and
result schemas:

```text
configs/{proper_v1,proper_v2}
docs/{proper_v1,proper_v2}
experiments/{proper_v1,proper_v2}
outputs/{proper_v1,proper_v2}
schemas/{proper_v1,proper_v2}
```

The move does not change the bytes of frozen PROPER v1 configurations, locks,
schemas, or result artifacts. Historical manifests therefore retain their
experiment-time paths and hashes. Code that validates a historical source
manifest maps its versioned top-level paths into `proper_v1` after the move.

PROPER v1 artifacts must not be overwritten or used to retune PROPER v2 after
their model outcomes have been observed. PROPER v2 work must use new files,
locks, output paths, and exclusion manifests under the `proper_v2` namespaces.
