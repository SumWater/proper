# AppWorld offline wheel-inventory preparation

## Frozen artifact

The official PyPI JSON metadata is frozen for `appworld==0.1.3.post1`:

- wheel: `appworld-0.1.3.post1-py3-none-any.whl`;
- bytes: 625,317;
- SHA-256:
  `db77f8003982502383a50fa2974983894bd1c54f64e2fd3f7e1540d5edd037eb`;
- Python requirement: `>=3.11,<4.0`;
- metadata source: <https://pypi.org/pypi/appworld/0.1.3.post1/json>.

The identity freeze does not mean the wheel has been downloaded or accepted.
It only prevents a future mutable-latest dependency from silently changing the
source under qualification.

## Read-only boundary

The inventory accepts one absolute wheel path outside the tracked PROPER
project. Before reading it, the runner verifies the expected project revision,
clean tracked worktree, external path, and the closed no-install boundary. It
then verifies exact filename, bytes, SHA-256, ZIP path safety, duplicate names,
symbolic links, size and compression limits, package metadata, required
dist-info files, and the presence of encrypted `.bundle` members.

The wheel is never imported, installed, or extracted. Encrypted bundle bytes
are hashed but not decrypted or interpreted. No member content is persisted;
the result contains paths, sizes, hashes, and a canonical member-manifest hash
only. `appworld install` and `appworld download data` remain forbidden.

## Validation and authority

Five synthetic wheel tests cover a passing encrypted wheel, identity mismatch,
unsafe traversal, missing encrypted bundle, and package metadata mismatch. The
preparation validator also checks frozen ancestry, standard-library-only
inspection, atomic persistence, closed schemas, and all no-task/no-model gates.

A passing preparation authorizes one read-only inventory of the exact official
wheel. It does not authorize AppWorld installation, protected-material
decryption, data download, API inventory, task reading, target selection,
model loading, GPU use, or any scientific claim.
