# Third-party resources

This repository contains original adaptation, benchmarking, validation, and
reporting code. It does not redistribute MiniCPM-o 4.5 weights, benchmark
datasets, generated WAV files, or third-party model checkpoints.

The workflow refers to the following upstream projects and resources:

- [MiniCPM-o 4.5](https://www.modelscope.cn/models/OpenBMB/MiniCPM-o-4_5)
- [vLLM-Omni](https://github.com/vllm-project/vllm-omni)
- [vLLM Ascend](https://github.com/vllm-project/vllm-ascend)
- [Seed-TTS-Eval](https://github.com/BytedanceSpeech/seed-tts-eval)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [s3prl / WavLM](https://github.com/s3prl/s3prl)
- [Mozilla Common Voice](https://commonvoice.mozilla.org/)

The Apache-2.0 license in this repository covers only the original material in
this repository. Users must obtain third-party models and datasets separately
and comply with each upstream license and usage policy.

Paths such as `/workspace/shared_assets/...` in scripts and result JSON files
are provenance from the competition container. They are not downloadable
assets and do not imply redistribution rights.
