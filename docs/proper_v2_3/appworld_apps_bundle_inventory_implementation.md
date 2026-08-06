# Aggregate-only AppWorld apps-bundle inventory implementation

## Implementation

The dependency-light inspector verifies the encrypted apps-bundle identity,
derives the public AppWorld key, decrypts into memory, validates the complete
ZIP before any member can be accepted, hashes every path and content payload,
and discards plaintext at process exit. It never calls `extractall` or writes
decrypted data.

The persisted result contains only aggregate extension counts, sizes, encrypted
and decrypted archive hashes, per-member path/content hashes, and a canonical
hashed-member manifest. It contains no protected member path, app/API name,
source snippet, or decrypted byte payload.

Seven synthetic encrypted-bundle tests cover successful aggregate inventory,
identity mismatch before decryption, wrong cryptographic material, path
traversal, duplicate members, symbolic links, and archive limits. The runner
also guards the exact project revision, clean worktree, external wheel path,
frozen inputs, and cryptography version.

## Authority

One remote inventory of the exact apps bundle is authorized after this result
is committed and synchronized. That command will decrypt protected application
code in memory, so any success or failure is final and must be returned and
frozen. It does not read or decrypt the tests bundle, download data, extract
source, import AppWorld, inventory APIs, load a model, or use a GPU.

Installation, static API inventory, target selection, and scientific claims
remain unauthorized regardless of the inventory outcome.
