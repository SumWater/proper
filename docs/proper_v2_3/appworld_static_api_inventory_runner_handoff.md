# AppWorld hash-only static API inventory runner handoff

The runner verifies the exact project revision, clean tracked tree, external
AppWorld wheel, external dependency target, exact dependency versions, frozen
implementation hashes, apps-bundle identity, and prior aggregate dimensions.

It reads only `appworld/.source/apps.bundle`, decrypts once in memory, validates
every ZIP member, parses all 60 Python and 12 stub members without importing
them, and writes only the closed hash-only result. No protected plaintext,
source extraction, tests/data/task access, network, target selection, model, or
GPU operation is allowed.

Exactly one remote invocation is authorized after synchronization and commit.
Whether it passes or stops, preserve the unique output and do not rerun.
