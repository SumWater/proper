# P0 remote inventory audit

- Inventory: `outputs/paper_2026/p0_remote_inventory.json`
- SHA-256: `5575046e5306f6979512cb5e9e337ac6fc5d90f6296a0f6b7965ae6dce019758`
- Created UTC: `2026-08-09T04:05:24.234180+00:00`
- Repository HEAD: `44e5b11104e3d0e46933b22311527c22828ec1cd`
- Boundary: no weights loaded, no inference, no download

## Passed checks

- Qwen3-8B operational path exists;
- all 15 files pass `configs/proper_v1/qwen3_8b_model.sha256`;
- repository HEAD matches the local historical base commit;
- approximately 986 GB disk space was free at inventory time;
- both GPUs were visible.

## Hardware snapshot

| GPU | Model | Total MiB | Free MiB at inventory | Compute capability |
|---:|---|---:|---:|---:|
| 0 | NVIDIA RTX 5880 Ada Generation | 49,140 | 24,476 | 8.9 |
| 1 | NVIDIA RTX 5880 Ada Generation | 49,140 | 24,474 | 8.9 |

The GPUs were only about half free at the snapshot. Formal scheduling must not assume exclusive access;
smoke validation must record concurrent processes and actual free memory.

## Model findings

- Verified agent model A: Qwen3-8B, 16,397,461,266 bytes.
- Other instruction models found: Qwen3-0.6B and Qwen3.5-9B, both from the Qwen family.
- No non-Qwen 7B/8B-class instruction model was found. Agent model B remains unresolved.
- `BAAI/bge-large-en-v1.5` revision
  `d4aa6901d3a41ba39fb536a557fa166f842b0e09` was found and is the preferred Dense candidate.
- `princeton-nlp/sup-simcse-bert-base-uncased` was also found but is not preferred unless BGE fails
  validation.

## Environment findings

Active environment: `proper-toolsandbox`, Python 3.11.15.

Reported package metadata:

- Transformers 4.41.2;
- NumPy 1.26.4;
- SciPy 1.13.1;
- Torch, Accelerate, BitsAndBytes, SentenceTransformers, and scikit-learn not reported.

This metadata is not sufficient to conclude that imports are impossible, because Conda and pip
metadata can differ. A second inventory must directly import the packages and list all Conda
environments before any installation or environment mutation.

## Decisions

1. Qwen model A identity is accepted.
2. BGE-large-en-v1.5 is provisionally selected for Dense Retrieval, pending direct import and model
   directory hash.
3. Qwen3-8B is the provisional fixed LLM Judge to avoid downloading a third large model; judge prompt
   and structured output still require freezing.
4. Qwen3.5-9B does not satisfy the cross-family requirement and will not be model B.
5. No formal inference is authorized yet.

## Required next evidence

- import-level diagnostics for Torch and related libraries;
- complete Conda environment list;
- current GPU compute-process snapshot;
- BGE model-directory manifest;
- decision and authorization for obtaining one non-Qwen 7B/8B instruction model if none exists in
  another unscanned location.

## Second inventory result

- Inventory: `outputs/paper_2026/p0_remote_inventory_v2.json`
- SHA-256: `38b8b3637a5b737f3277c121ab109c2bce4be6cb0f009938039f5fb088e7056f`
- Created UTC: `2026-08-09T04:11:43.175846+00:00`

Direct imports confirmed that the active `proper-toolsandbox` environment cannot import Torch,
Accelerate, BitsAndBytes, SentenceTransformers, or scikit-learn. Only Transformers 4.41.2 imported
from the required stack. This environment is not authorized for model smoke tests.

The machine contains several other Conda environments, including `failure-memory-pilot`. Historical
locks require Python 3.11.15, Torch 2.12.0, Transformers 5.8.1, Accelerate 1.13.0, and scikit-learn
1.5.1. Existing environments must be probed before installing or recreating anything.

At the snapshot, two unrelated Python processes each occupied about 24 GB on one GPU. Model tests must
wait for adequate free memory or use an agreed scheduling window; the paper runner must not terminate
or interfere with those processes.

The BGE candidate is now content-identified:

- revision: `d4aa6901d3a41ba39fb536a557fa166f842b0e09`;
- files: 6;
- bytes: 1,341,560,790;
- manifest payload SHA-256:
  `532377f4427558e482a28ca65e2bb0c8b3057d6fc76dda4a9486d7862815efc5`;
- portable file manifest: `configs/paper_2026/bge_large_en_v1_5.sha256`.

Dense model identity is frozen to this snapshot. Pooling, normalization, query prefix, maximum length,
and batch settings remain to be frozen after a no-outcome smoke validation.

## Existing Conda environment probe result

- Probe: `outputs/paper_2026/p0_conda_probe.json`
- SHA-256: `a71f30a3b550b38eefd2fea3a5fde0646768a94898af83eefba4f5e3ac106f60`
- Created UTC: `2026-08-09T04:16:15.292855+00:00`

`failure-memory-pilot` exactly matches the historical core dependency versions:

- Python 3.11.15;
- Torch 2.12.0 with CUDA 12.9 and BF16 support;
- Transformers 5.8.1;
- Accelerate 1.13.0;
- scikit-learn 1.5.1.

It lacks BitsAndBytes and SentenceTransformers, but neither is required: full BF16 7B/8B weights fit
the available GPU, and BGE will use a frozen Transformers mean-pooling implementation. This environment
is selected for smoke validation without mutation. A current full Conda/pip lock is still required
before formal runs.

`AINegoProject` can import all optional libraries but uses Python 3.9 and different core versions. It
is not selected because matching the historical Qwen stack is more important than using the
SentenceTransformers convenience API.

## Model B storage gate result

- Probe: `outputs/paper_2026/p0_remote_storage.json`
- SHA-256: `a4576f8a07ec028c6ac8e896296e4a4dc5e6398e565297a6c365fae97623aa3b`
- Created UTC: `2026-08-09T04:28:03.858880+00:00`

The model target, project, and Hugging Face cache are on the same filesystem. Its total capacity is
1,880.02 decimal GB, with 797.75 GB used and 986.69 GB free. The existing LLM directory occupies
58.55 GB, the full project 93.91 GB, and the Hugging Face cache 4.02 GB. Free space must not be summed
across these paths because they share one device.

The predeclared storage gate passed both the 25 GB hard minimum and the 35 GB recommended-headroom
threshold. A filtered 14.6 GB download would leave approximately 972 GB free, so storage does not
block the pinned Model B download. The probe confirms that no download had started at capture time.

## First Model B download attempt

The authorized download script started in the selected `failure-memory-pilot` environment and reached
the Hugging Face client, but the initial repository metadata request failed with
`httpx.ConnectTimeout: [Errno 110] Connection timed out`. The exception occurred inside
`HfApi.repo_info` before snapshot file transfer, so this is a remote network-connectivity failure, not
a model-path, storage, environment, license, or GPU failure. No model manifest was produced. Preserve
the target directory for resumability and retry only after an explicit connectivity probe.

The official endpoint then failed an explicit IPv4 `curl` probe after a 30-second connection timeout.
The alternative transport endpoint `https://hf-mirror.com` returned HTTP/2 200 for the same repository
metadata route on 2026-08-09. The mirror is authorized only as a transport workaround: repository ID
and immutable revision remain unchanged, and downloaded content must pass the generated per-file SHA-256
manifest audit before model loading.

## Current environment lock result

- Lock: `outputs/paper_2026/p0_environment_lock.json`
- SHA-256: `fb943ddec5a962883c0e70cd1b863ad8c5547a0847107a76a175b53174a02443`
- Created UTC: `2026-08-09T09:14:09.602517+00:00`
- Capture passed: yes

The interpreter and prefix exactly match `/home/amax/miniconda3/envs/failure-memory-pilot`. The lock
contains 56 installed distributions, 56 pip-freeze entries, and 94 Conda explicit entries. The Conda
explicit digest is `ed07021e8c5584886c6a31c639811e0bfaf66143a10dc263ab27797dcfd72679`,
which exactly matches the historical formal environment. The current and historical pip locks contain
the same 56 package-version entries as sets; the current normalized digest is
`fecf22e4297d1748af586a617e313f0e853bb56ce9903f92763e386ec51e2043`, while the historical artifact
digest reflects its original ordering/serialization.

At capture time both GPUs had 24,462 MiB free out of 49,140 MiB. This is below the predeclared 40,000
MiB smoke threshold, so the lock capture passes but model smoke remains blocked. `CUDA_VISIBLE_DEVICES`
was intentionally unset for this non-model diagnostic; the smoke runner requires an explicit single-GPU
pin and fails closed otherwise.
