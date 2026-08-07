# Runtime evidence

This directory contains the small, text-only environment snapshot captured by
`scripts/collect_env.sh` during the Ascend run. The files were copied from:

```text
/workspace/user_data/minicpm-vllm-omni/submission/results/environment
```

Included evidence:

- `environment/timestamp.txt`: UTC capture time.
- `environment/vllm-omni-commit.txt`: pinned framework commit.
- `environment/python.txt`: Python version.
- `environment/uname.txt`: container kernel and architecture.
- `environment/npu-smi.txt`: NPU health and memory snapshot.
- `environment/pip-freeze.txt`: package snapshot from the container.
- `environment/runtime-versions.txt`: concise CANN, torch_npu, vLLM-Omni, and
  vLLM-Ascend version summary queried from the same container.

The HiDevLab allocation was recorded as a single 910C card. `npu-smi` reports
the generic device name `Ascend910` and two chip rows under the allocated
logical NPU; the text snapshot alone does not distinguish every Ascend 910
submodel. Full server logs are intentionally not published because they are
large and contain noisy container-local paths and process details.

The strict ASV proxy result is stored separately at
`results/accuracy/asv_ab_c1_n32_strict.json`. It includes the checkpoint,
source, metadata, and 96 input WAV hashes in its run fingerprint. It remains a
non-official CPU proxy (`official_protocol=false`), not the competition ASV
score.

`RESULT_MANIFEST.sha256` protects the bundled evidence against accidental
changes. It verifies repository-internal consistency; it is not an independent
attestation by the hardware provider or competition organizer.
