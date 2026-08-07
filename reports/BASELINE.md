# 基线记录

日期：2026-08-06

## 已完成

- challenge 分支三阶段服务在 HiDevLab 单卡 910C 分配上启动成功；环境快照见
  `evidence/environment/`。
- `/health` 返回 HTTP 200。
- 文本请求成功并返回合理中文。
- 文本到流式语音请求成功，保存了 9 个合法的 24 kHz 单声道 WAV chunk，
  总音频时长 8.2 秒。
- 远端服务日志显示 Thinker、Talker、Code2Wav 三阶段均完成加载，Ascend NPU 的
  HiFT linear downsample 补丁已启用；完整日志未纳入公开仓库。

## 冷启动观测，不作正式对比

第一次语音请求触发 Code2Wav/ONNX Runtime 冷初始化：

| 指标 | 冷请求观测 |
|---|---:|
| 文本首输出 | 591 ms |
| Talker 首输出 | 849.9 ms |
| 首个音频输出 | 48,679.7 ms |
| 音频总时长 | 8.2 s |
| 请求墙钟时间 | 约 80.85 s |

该请求包含首次运行初始化，不能与赛事热态基线比较，也不代表稳定性能。

## 完整热态同机基线（c1/n32）

原始结果：`results/performance/baseline_repeat_full_c1_n32.json`。

该轮使用完整 Seed-TTS 英文数据、官方 seed=0 shuffle 顺序、2 个完整语音 warmup、
并发 1 和 32 个计时请求，是后续单变量候选的共同同机基线。

| 指标 | 实测 |
|---|---:|
| 完成/失败 | 32 / 0 |
| 吞吐 | 0.499764 req/s |
| Mean TTFT | 318.936767 ms |
| Mean E2EL | 2000.559246 ms |
| Mean TTFP | 1021.933432 ms |
| Mean RTF | 0.471207 |
| 音频总时长 | 139.0 s |

它与候选配置使用完全相同的数据、顺序、并发和计时口径，因此同机 A/B 优先于
跨环境引用赛事配置中的官方参考值。

## 热态快速基线（固定 4 条，仅用于工程 A/B）

原始结果：`results/performance/quick_c1_n4.json`

| 指标 | 实测 |
|---|---:|
| 完成请求 | 4 / 4 |
| 失败请求 | 0 |
| 吞吐 | 0.5385 req/s |
| Mean TTFT | 295.16 ms |
| Mean E2EL | 1856.69 ms |
| Mean TTFP | 999.96 ms |
| Mean RTF | 0.4909 |

这 4 条来自本地最小闭包数据集，并非官方 seed=0 后的完整 32 条集合，因此不能用
来宣称超过赛事官方 `333.27 ms / 986.47 ms / 0.4423` 基线。它的用途是确保后续
候选配置使用完全相同输入做单变量 A/B。

## 已排除的非模型故障

第一次执行快速 benchmark 时，客户端把 API 模型名当成 Hugging Face 仓库名并
尝试联网加载 tokenizer，因环境无外网而在发出任何推理请求前退出。脚本现已通过
`--tokenizer /workspace/shared_assets/models/OpenBMB/MiniCPM-o-4_5` 固定使用本地
只读权重；该失败没有产生性能样本。
