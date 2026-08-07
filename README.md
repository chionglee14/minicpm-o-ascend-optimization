# MiniCPM-o 4.5 Ascend Optimization

> 项目的完整实现、实验原始结果、报告与发布审计记录见 [PR #1](https://github.com/chionglee14/minicpm-o-ascend-optimization/pull/1)。

MiniCPM-o 4.5 在昇腾 NPU 上的 vLLM-Omni 推理适配、流式语音性能优化与可审计
评测工程。原创代码和文档采用 [Apache-2.0](LICENSE) 许可；模型、数据集和第三方
checkpoint 不随仓库分发，详见 [THIRD_PARTY.md](THIRD_PARTY.md)。

本目录对应赛道一子赛道 B，目标是在单卡 Ascend 910C 上复现并优化
MiniCPM-o 4.5 的流式文本和语音推理。

评委快速阅读入口：`reports/EXECUTIVE_SUMMARY.md`。提交前可直接运行
`python3 scripts/validate_submission.py`，离线检查核心文件哈希、配置单变量和全部
原始结果完整性。

当前策略只有三步：

1. 保留官方 `minicpm-challenge` 配置作为不可变基线。
2. 用同一数据、同一请求数和同一并发做单变量 A/B。
3. 只有完整请求成功且本地 proxy gate 未见明显退化，才保留候选；官方 WER/ASV
   仍以主办方环境为准。

共享目录 `/workspace/shared_assets` 是只读资源。本工程只会读取其中的模型和
Seed-TTS 压缩包，所有配置、日志和结果均写入
`/workspace/user_data/minicpm-vllm-omni`。

## 报告运行环境

- 平台分配：单卡 Ascend 910C；`npu-smi` 原始快照显示通用名称 `Ascend910`，
  服务配置使用容器内设备 `0`
- 模型：`/workspace/shared_assets/models/OpenBMB/MiniCPM-o-4_5`
- 框架分支：`vllm-project/vllm-omni:minicpm-challenge`
- 已验证提交：`4a0a48177862c0f1763eb4bc771358419faf8431`
- CANN Toolkit：`9.0.0`；`torch_npu 2.10.0`
- vLLM-Ascend：`0.19.1rc2.dev1014+g8092d3f66`
- Python：`/usr/local/python3.12.13/bin/python3`
- 服务地址：`127.0.0.1:8091`

环境原始快照位于 `evidence/environment/`。它能核对提交、架构、Python、软件包和
NPU 状态，但不构成硬件提供方或主办方的独立认证。

## 目录

```text
configs/baseline_minicpmo_4_5.yaml  官方 challenge 基线配置副本
configs/experiment_codec20.yaml     只改首个 codec 窗口 25→20 的实验配置
configs/experiment_steps9.yaml      只改 Token2Wav 迭代 10→9 的实验配置
scripts/collect_env.sh              保存环境指纹
scripts/install_challenge.sh        在官方镜像内安装 challenge 分支
scripts/start_server.sh             前台启动三阶段服务
scripts/prepare_seed_tts_mini.sh    从只读 tar 提取 4 条快速测试数据
scripts/smoke_audio.sh              文本到流式语音冒烟测试
scripts/run_demo.sh                 一键执行录屏所需健康检查、NPU信息和语音 Demo
scripts/inspect_wavs.py             校验 Demo WAV 格式、时长和 SHA-256
scripts/build_pdf_report.py         从原始 JSON 生成正式性能报告 PDF
scripts/benchmark_quick.sh          对现有服务跑 4 请求热态验证
scripts/benchmark_matrix.sh         对现有服务依次跑 c1/n32、c4/n64、c8/n128
scripts/benchmark_official.sh       停服后跑官方三档 benchmark
scripts/compare_results.py          校验完成率并比较固定输入 A/B
scripts/eval_seed_tts_openai_whisper.py  对已保存音频做配对 WER 代理评测
scripts/run_whisper_ab_shards.sh    将 32 对音频切成 8 个 CPU 分片并行转写
scripts/merge_seed_tts_wer_shards.py 校验分片覆盖范围并合并结果
scripts/eval_seed_tts_wavlm_proxy.py 用发布的 WavLM/ECAPA 权重做配对 ASV 代理评测
scripts/validate_submission.py      离线检查配置单变量、结果完整性和代理口径
evidence/environment/               远端运行时环境与 NPU 状态快照
evidence/RUN_PROVENANCE.md           配置、结果和远端服务日志哈希关联说明
tests/data/seed_tts_mini/           4 条 Seed-TTS 元数据
reports/BASELINE.md                 当前实测证据和结论边界
reports/EXPERIMENTS.md              单变量 A/B、回退理由和精度门禁
reports/ASV_PROXY.md                ASV CPU 代理的完整命令、依赖和协议边界
reports/EXECUTIVE_SUMMARY.md        可直接提供给评委的精简结果总结
reports/SUBMISSION_CHECKLIST.md     必交项状态和 60～90 秒 Demo 录屏流程
requirements-proxy.txt              离线质量代理的额外 Python 依赖
requirements-report.txt             PDF 报告重建依赖
RESULT_MANIFEST.sha256              核心配置、脚本和原始结果的 SHA-256 清单
output/pdf/                         已渲染校验的正式性能报告 PDF
results/performance/                严格 c1/n32 的原始性能 JSON
results/accuracy/                   32 条配对 WER/ASV 代理评测及 strict-v2 原始 JSON
.github/workflows/offline-ci.yml    GitHub 离线结构与哈希校验
```

## 当前实测结论

严格 `c1/n32` 下，`token2wav_n_timesteps: 10 → 9` 的两次复测相对同机基线：

- Mean RTF 改善 `5.58%` / `6.42%`
- Mean TTFP 改善 `4.71%` / `5.44%`
- Mean E2E 改善 `5.28%` / `6.08%`
- 吞吐改善 `5.57%` / `6.46%`

32 条配对 WER 代理评测中，基线与候选均为 `1.071238%`，32 条的归一化 WER
全部一致。ASV 代理的平均相似度变化为 `-2.11%`，32 对样本中 17 对提高、15 对
降低；在这一未校准 CPU proxy 上，配对差异没有统计显著性（t-test `p=0.801`）。
该结果不构成 ASV 精度门禁。两项检查都显式标记为非官方协议，不能据此宣称官方
WER/ASV 已通过。

严格 ASV v2 原始 JSON 已纳入 `results/accuracy/asv_ab_c1_n32_strict.json`；它绑定
checkpoint、三份源码、meta 和 96 个输入 WAV 哈希，运行指纹为
`97bb7c4af9ead07bf1c94aff9093b0f669866036d5d23663a0a80f763b5485dc`。

对齐赛事请求数、并发数和主要参数的本地三档矩阵共 224 个计时请求全部成功、
0 失败；这只代表请求级功能完整，不代表尾延迟稳定。`c4/n64` 的 p99 TTFP、RTF、
E2E 分别达到 `21.346 s`、`7.127`、`22.967 s`，`c8/n128` 分别为 `14.036 s`、
`4.557`、`21.174 s`。当前提交候选为 `steps9`，基线配置继续作为一键回退；完整
均值、尾延迟和跨运行参考见 `reports/EXPERIMENTS.md`。

## PDF 报告重建（可选）

成品 PDF 已放在 `output/pdf/`，提交时无需重建。若替换原始结果 JSON 后需要重新
生成报告，请准备包含中文字符的 TrueType 字体目录，然后执行：

```bash
python3 -m pip install -r requirements-report.txt
python3 scripts/build_pdf_report.py --font-dir /path/to/chinese-fonts
```

脚本会从 `results/performance/` 与 `results/accuracy/` 读取主 A/B、矩阵和代理质量
数据并重新计算核心表格。报告日期、框架提交和赛事配置内参考值仍属于报告元数据，
替换实验环境后需要人工复核。

## 复现

以下命令均在官方 `vllm-omni:v0.25.0-a3` 镜像内运行。

```bash
export PROJECT_ROOT=/workspace/user_data/minicpm-vllm-omni/submission
cd "$PROJECT_ROOT"

bash scripts/collect_env.sh
bash scripts/prepare_seed_tts_mini.sh
bash scripts/start_server.sh
```

服务就绪后，在第二个 SSH 终端执行：

```bash
cd /workspace/user_data/minicpm-vllm-omni/submission
bash scripts/run_demo.sh
bash scripts/benchmark_quick.sh
```

快速测试固定为并发 1、2 个 warmup、4 个正式请求。它只验证请求、流式音频和
指标落盘是否正常，不能代替赛事的 32 请求单并发结果。
benchmark 的 API 模型名保持为 `openbmb/MiniCPM-o-4_5`，但 tokenizer 显式从
共享本地权重加载，因此不会因 Hugging Face 网络不可达而卡住。

要对完整本地 Seed-TTS 数据跑官方 seed=0 的 32 请求顺序，可执行：

```bash
DATASET_ROOT=/workspace/user_data/minicpm-vllm-omni/datasets/seedtts_testset \
NUM_PROMPTS=32 DISABLE_SHUFFLE=0 LABEL=baseline_full \
  bash scripts/benchmark_quick.sh
```

复现当前 `steps9` 候选时，先在服务终端停止基线服务，再用候选配置启动：

```bash
cd /workspace/user_data/minicpm-vllm-omni/submission
CONFIG="$PWD/configs/experiment_steps9.yaml" \
LOG_DIR=/workspace/user_data/minicpm-vllm-omni/results/server/steps9_matrix \
  bash scripts/start_server.sh
```

服务就绪后，在第二个终端执行对齐赛事请求数、并发数和主要参数的本地矩阵：

```bash
cd /workspace/user_data/minicpm-vllm-omni/submission
DATASET_ROOT=/workspace/user_data/minicpm-vllm-omni/datasets/seedtts_testset \
LABEL_PREFIX=steps9_matrix \
  bash scripts/benchmark_matrix.sh
python3 scripts/validate_submission.py
```

`benchmark_official.sh` 保留为上游 pytest harness 入口；它使用官方配置中的在线
模型/数据集标识，只有评测环境能够解析这些标识时才直接运行。本次机器外网不可用，
因此实测使用本地只读模型、解压后的完整 Seed-TTS 和对齐的 c/n 参数，避免把联网
失败误记为模型失败。该路径不等同于主办方正式 pytest harness 或最终评测环境。

正式结果必须同时满足：

- `completed == num_prompts`
- `failed == 0`
- 正式提交时同时保留原始 JSON、服务日志和环境指纹（仓库已含环境快照，完整服务日志仍在远端）
- 本地 proxy gate 重新验证通过，主办方正式 WER/ASV 另行通过

## 官方单并发参考值

赛事文档给出的 vLLM-Omni 单并发基线为：TTFT `333.27 ms`、TTFP
`986.47 ms`、RTF `0.4423`。快速 4 请求结果不与该值直接宣称胜负；最终对比使用
官方测试配置的 32 请求结果。

官方资料：

- [赛事评测规范](https://modelbest.feishu.cn/docx/U41vdXMmQo7tv3xW2p9c9uEanKe)
- [MiniCPM-o 4.5 challenge recipe](https://github.com/vllm-project/vllm-omni/blob/4a0a4817/recipes/OpenBMB/MiniCPM-o-4_5.md)
- [官方 benchmark 配置](https://github.com/vllm-project/vllm-omni/blob/4a0a4817/tests/dfx/perf/tests/test_minicpmo_4_5.json)
