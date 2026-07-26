# Apex Cleanup Candidates

## Removed by this implementation

- Retired methodology document identity and README links.
- Five checked-in geometry snapshots carrying the retired identity. They are
  recoverable from Git history and were not runtime dependencies.

## Retained pending proof

Eight tracked `.bak` files remain cleanup candidates. Before deletion, verify no
production import, dynamic import, test dependency, documented workflow, or
compatibility role. Candidate paths are discoverable with:

```bash
git ls-files '*.bak'
```

`defect_origin_matrix.json` and `pipeline_source_map.json` remain because they do
not contain the retired authority identity. Operator-facing “Trade plan” wording
also remains because it describes an actionable output, not the retired file.
