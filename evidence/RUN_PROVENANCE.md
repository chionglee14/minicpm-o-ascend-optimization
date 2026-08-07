# Run provenance

This note records how the bundled files were associated with the remote runs.
It is an audit aid, not a cryptographic attestation by HiDevLab or the contest.
The performance JSON schema does not embed the configuration hash, so the
config-to-result association below comes from the recorded run sequence.

## Runtime identity

- Environment capture: `2026-08-06T08:59:10,669678690+00:00`
- vLLM-Omni commit: `4a0a48177862c0f1763eb4bc771358419faf8431`
- CANN Toolkit: `9.0.0` (`V100R001C10SPC001B250`)
- vLLM-Omni: `0.25.0+npu`
- vLLM-Ascend: `0.19.1rc2.dev1014+g8092d3f66`
- Python: `3.12.13`
- NPU snapshot: `evidence/environment/npu-smi.txt`

## Config and result hashes

| Role | File | SHA-256 |
|---|---|---|
| baseline config | `configs/baseline_minicpmo_4_5.yaml` | `7998080ad13be6328d283765e0face1c670d1098249d53992941be0bd1b6f285` |
| steps9 config | `configs/experiment_steps9.yaml` | `15c4ffa921c64d86f062a97c6d105e3ef4bc4f597082443ed4d7a377447f7069` |
| rejected codec20 config | `configs/experiment_codec20.yaml` | `d645a2698b43d2463087a83137c8d283a5dc56b0d662cd69c1aa4cc580d0ffae` |
| baseline c1/n32 | `results/performance/baseline_repeat_full_c1_n32.json` | `94c72c3aca75a7d3e85cb5005010777c74958b953b55c469bc92ad41b132e4cd` |
| steps9 run 1 | `results/performance/steps9_full_c1_n32.json` | `6529a9094b7d9ca377715ded18c7ae08405675af8f47f0329d969184e8d12563` |
| steps9 run 2 | `results/performance/steps9_repeat_c1_n32.json` | `03ed8b3644a45d0c9fc317d273a0b456f87c25e6e914993686369344a1134674` |
| steps9 c4/n64 | `results/performance/steps9_matrix_c4_n64.json` | `a6053e16ff5893219a1c0bbc01553d497b52976bc7eeb1af4f665d44dd8e944d` |
| steps9 c8/n128 | `results/performance/steps9_matrix_c8_n128.json` | `55484ba6e06778b68c5e1ebc40a2fc6a81bf67e537b6f9256258a0da87cdffb4` |
| Whisper proxy | `results/accuracy/whisper_ab_c1_n32.json` | `422dd1a06532a982e31eb19a65134a4f0016742dbf58d7c5a1470af156c05260` |
| strict ASV proxy v2 | `results/accuracy/asv_ab_c1_n32_strict.json` | `56b098b71138dd618c98d859cc91ef1423d036c6dbd374b4a561f5707ddf30c2` |

## Remote service log pointers

Full server logs remain in the competition workspace and are not published in
this repository. Their SHA-256 values at the time of review were:

| Run | Remote path | SHA-256 |
|---|---|---|
| steps9 matrix | `/workspace/user_data/minicpm-vllm-omni/results/server/steps9_matrix/server.log` | `397f339629cb70e8a7a30f812fc098608be8711e43289c3f385dfa506aefb00a` |
| baseline repeat | `/workspace/user_data/minicpm-vllm-omni/results/server_baseline_repeat/server.log` | `eb4eb9f62e0ce940b8eec95e8dc4c6bef4ca2add742fb6ca5387cb0ad2e76aa2` |
| steps9 c1 | `/workspace/user_data/minicpm-vllm-omni/results/server_steps9/server.log` | `83b3b73dd27c2e4d7a81d85fae277a54bafa76726bd285781de2e162f3c439ff` |
| codec20 | `/workspace/user_data/minicpm-vllm-omni/results/server_codec20/server.log` | `6da000ee37e3823727f1e7e6cdcb8006b8307953ae081bb3e0b681e6e9c0d29d` |

The reviewed steps9 matrix log contained these relevant lines:

```text
50: Resolved architecture: MiniCPMO45Code2Wav
283: Patched Step-Audio2 HiFT linear downsample for Ascend NPU
381: Started server process
383: Application startup complete.
```

Process identifiers and terminal color escapes were omitted from this excerpt.
The remote log hash above identifies the full source file.
