# AppWorld controlled-install and static-inventory protocol

## Why the official setup commands are not used

The public `appworld==0.1.3.post1` installation code shows that `appworld
install` decrypts both `apps.bundle` and `tests.bundle` and then uses ZIP
`extractall`. The public data downloader removes an existing data directory,
downloads `data-0.1.0.bundle`, decrypts it immediately, and deletes the bundle.
Those operations are broader and more destructive than the current source
qualification requires.

PROPER therefore does not call either official command at this gate. The
tests bundle and data bundle remain closed.

## Minimal protected-code boundary

The first future operation is not installation. It is one in-memory inventory
of the exact `appworld/.source/apps.bundle` whose encrypted SHA-256 and size
were frozen by the wheel inventory. The public cryptographic format is frozen:
PBKDF2-HMAC-SHA256 with 100,000 iterations, a 32-byte key, and AES-256-CFB with
a 16-byte IV prefix.

After decryption, every ZIP member must be validated before extraction could
ever be considered. Absolute paths, parent traversal, backslashes, duplicate
members, symbolic links, excessive sizes, and excessive compression ratios
stop closed. This inventory has an extraction budget of zero.

To respect AppWorld's protected-material boundary, the persisted result may
contain only aggregate counts, extension counts, content hashes, path hashes,
the decrypted ZIP hash, and a canonical manifest. It must not contain member
paths, app/API names, source snippets, or decrypted bytes. Raw protected
material remains outside Git.

## Later static API inventory

Only after the aggregate bundle inventory is returned and frozen may a new
protocol consider safe extraction into an isolated root outside PROPER. That
later inventory must exclude tests, data, tasks, ground truth, evaluators, and
arbitrary module imports. It must build a complete API registry using static
AST or OpenAPI evidence and preserve the four v2.3 effect classes. One named
API call must remain one ActionExecutionLedger event.

## Current gate

This CPU-only protocol design decrypts nothing and reads no task, API, model,
or evaluator output. Passing authorizes implementation and synthetic testing
of an aggregate-only apps-bundle inspector. It does not authorize protected
bundle decryption, source installation, static API inventory, model loading,
GPU use, target-capacity claims, or confirmation.
