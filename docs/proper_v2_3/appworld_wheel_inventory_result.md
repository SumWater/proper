# Frozen AppWorld wheel-inventory result

## Result

The one authorized read-only inventory passed at remote project revision
`cc297f055b0439ed32c89cc18974a066eba10de5`. The returned result SHA-256 is
`2390843c1ede6839a3b9eae350d21c5ae6c0e7bbed09db068d7a87adf6454037`.

The exact `appworld==0.1.3.post1` wheel contains 44 regular members totaling
1,272,412 uncompressed bytes. The canonical member-manifest SHA-256 is
`65c1229057d82899d55f435e38b01ac62c037703f4b441dec44c6a2d5918aead`.
Two encrypted protected-code members are present:

- `appworld/.source/apps.bundle`, 177,209 bytes;
- `appworld/.source/tests.bundle`, 171,334 bytes.

All remote preflight checks passed. The wheel was not extracted, installed, or
imported; neither bundle was decrypted or interpreted. No task or API data was
read, and no model or GPU was used.

## Interpretation

This establishes exact package identity and confirms that protected AppWorld
application code is present behind an encrypted boundary. It does not establish
the number or effect classes of APIs, task inventory, recoverable branches,
base-model capability, target capacity, held-out status, or any PROPER result.

The successful inventory must not be rerun. Local freeze validation recomputes
member ordering, path safety, unique paths, counts, total sizes, the canonical
manifest, and both bundle hashes from the returned JSON.

## Next gate

Only design of a controlled installation and static API-inventory protocol is
authorized. Installation, bundle decryption, data download, API/task inventory,
model execution, GPU use, and confirmatory claims remain closed until that
separate protocol is frozen and validated.
