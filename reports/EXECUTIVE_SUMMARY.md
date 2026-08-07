# MiniCPM-o 4.5 昇腾推理优化总结

## 项目概况

- 子赛道：vLLM-Omni 推理优化
- 平台分配：单卡 Ascend 910C；原始环境快照见 `evidence/environment/`
- 模型：MiniCPM-o 4.5
- 框架：vLLM-Omni `minicpm-challenge`
- 已验证提交：`4a0a48177862c0f1763eb4bc771358419faf8431`
- 当前候选：`token2wav_n_timesteps: 10 -> 9`
- 回退配置：`configs/baseline_minicpmo_4_5.yaml`

候选配置相对基线只有上述一处功能变化，目标是减少一次 Token2Wav flow-matching
迭代，从而降低流式语音生成 RTF。全部结论均保留原始 JSON，不使用冷启动请求或
4 请求 smoke 数据宣称正式性能收益。

## 同机严格 A/B

测试使用相同 HiDevLab 910C 分配、完整 Seed-TTS English、seed=0、并发 1、2 个完整
语音 warmup 和 32 个计时请求。三轮均为 32/32 成功、0 失败。

| 指标 | 基线 steps=10 | steps=9 run 1 | 相对基线 | steps=9 run 2 | 相对基线 |
|---|---:|---:|---:|---:|---:|
| Mean TTFT | 318.937 ms | 314.445 ms | -1.41% | 313.285 ms | -1.77% |
| Mean TTFP | 1021.933 ms | 973.763 ms | -4.71% | 966.361 ms | -5.44% |
| Mean RTF | 0.471207 | 0.444927 | -5.58% | 0.440935 | -6.42% |
| Mean E2E | 2000.559 ms | 1894.958 ms | -5.28% | 1878.938 ms | -6.08% |
| 吞吐 | 0.499764 req/s | 0.527579 req/s | +5.57% | 0.532074 req/s | +6.46% |

两次候选复测的主要指标差异均小于 1%，候选方向一致；基线只有一次，因此不能据此
估计基线波动或宣称统计显著。另一个候选
`codec_chunk_frames: 25 -> 20` 虽降低 TTFP，但 RTF 恶化 6.03%、E2E 恶化
6.23%，因此已淘汰。

## 三档请求矩阵

| 档位 | 成功/失败 | Mean TTFT | Mean TTFP | Mean RTF | Mean E2E | 吞吐 |
|---|---:|---:|---:|---:|---:|---:|
| c1/n32 | 32/0 | 313.285 ms | 966.361 ms | 0.440935 | 1878.938 ms | 0.532074 req/s |
| c4/n64 | 64/0 | 494.024 ms | 3279.353 ms | 1.427453 | 6034.233 ms | 0.654534 req/s |
| c8/n128 | 128/0 | 551.120 ms | 3646.525 ms | 2.115514 | 9613.281 ms | 0.820408 req/s |

本地 harness 对齐赛事请求数、并发数和主要参数，三档共 224 个计时请求全部成功、
0 失败；它未直接运行主办方正式 pytest harness。请求成功不等于尾延迟稳定：

| 档位 | p99 TTFP | p99 RTF | p99 E2E |
|---|---:|---:|---:|
| c1/n32 | 1.100 s | 0.596 | 2.507 s |
| c4/n64 | 21.346 s | 7.127 | 22.967 s |
| c8/n128 | 14.036 s | 4.557 | 21.174 s |

相对赛事配置内的跨运行参考值，c4/n64 和 c8/n128 的 Mean RTF 分别低 9.28%
和 8.12%；但 c8/n128 的 Mean TTFT、TTFP 分别高 0.69% 和 8.76%。跨运行参考
不替代同机 A/B，也不掩盖高并发长尾。

## 质量代理检查

| 检查 | 基线 | steps=9 | 结论 |
|---|---:|---:|---|
| Whisper large-v3 proxy Mean WER | 1.071238% | 1.071238% | 32 条 WER 全部一致 |
| WavLM/ECAPA CPU proxy Mean SIM | 0.02345999 | 0.02296496 | 17 对提高、15 对降低 |

ASV 配对均值差为 `-0.00049502`，95% CI 为
`[-0.00446985, 0.00347981]`，paired t-test `p=0.801`。在这一未校准 CPU
proxy 上，配对差异没有统计显著性；它不能证明完全等价，也不构成精度门禁。

两项检查均在结果 JSON 中标记 `official_protocol: false`。ASV CPU 代理的绝对
数值不能与赛事正式门槛比较；最终精度结论以主办方 WER/ASV 环境为准。
strict-v2 原始 JSON 已随包保存，并由离线 validator 校验运行指纹、96 个输入哈希、
三份源码哈希与质量门。

## 最短复现路径

```bash
cd /workspace/user_data/minicpm-vllm-omni/submission
bash scripts/collect_env.sh
CONFIG="$PWD/configs/experiment_steps9.yaml" bash scripts/start_server.sh
```

服务 ready 后，在第二个终端执行：

```bash
cd /workspace/user_data/minicpm-vllm-omni/submission
bash scripts/run_demo.sh
bash scripts/benchmark_matrix.sh
python3 scripts/validate_submission.py
```

详细实验、协议边界和录屏流程分别见 `EXPERIMENTS.md`、`ASV_PROXY.md` 和
`SUBMISSION_CHECKLIST.md`。
