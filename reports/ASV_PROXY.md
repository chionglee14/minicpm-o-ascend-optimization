# Seed-TTS ASV 成对代理评测

## 结论

在与性能测试相同的 Seed-TTS English、`seed=0`、`c1/n32` 样本上，
steps9 与 baseline 的 WavLM speaker-similarity 成对差异很小，32 个样本中
17 个提高、15 个降低。在这一未校准 CPU proxy 上，配对差异没有统计显著性；
该结论不能作为赛事 ASV 精度门禁。

| 指标 | baseline | steps9 | steps9 - baseline |
|---|---:|---:|---:|
| mean similarity | 0.02345999 | 0.02296496 | -0.00049502 |
| median similarity | 0.01554724 | 0.01793795 | +0.00239071 |

成对差值标准差为 `0.01102471`，95% t 区间为
`[-0.00446985, 0.00347981]`；paired t-test `p=0.8012`，Wilcoxon
signed-rank `p=0.8754`。这些统计量只说明本次 32 对 A/B 没有检测到一致方向的
变化，不能证明两个配置完全等价。

## 口径边界

这不是比赛官方 ASV，绝对分数不能与赛事 `ASV >= 0.689` 门槛比较。

- 上游 `cal_sim.sh` 把设备写为 `cuda:$rank`，当前 Ascend 容器没有 CUDA。
- 上游依赖锁定到 `s3prl==0.3.1`、`torchaudio==0.9.0` 和
  `scipy==1.7.1`；当前环境为 Python 3.12、PyTorch/torchaudio 2.10，且没有
  fairseq，无法原样安装旧栈。
- 代理脚本使用相同的 `wavlm_large_finetune.pth` 权重、Seed-TTS 仓库中的
  ECAPA-TDNN 代码，以及其 README 指定 commit 的 s3prl WavLM 实现；仅把
  CUDA 调用改为 CPU，并绕开 s3prl 对无关 upstream experts 的全量导入。
- 因设备和运行栈不同，结果仅用于 baseline/steps9 的同输入成对方向判断。

## 固定版本与校验

- seed-tts-eval commit：`752f4297f090c46bb1a55a1f7439e5944ddefe8d`
- s3prl commit：`7ab62aaf2606d83da6c71ee74e7d16e0979edbc3`
- WavLM checkpoint SHA-256：
  `51f07e3b94d9e0262a6a675ef5a087be3dd09e8c62e9d886827f44f82fe7f94b`
- WavLM.py SHA-256：
  `de2b981038102edafd88f0aa80bf1d9d0ecab8a8da83aff60f3139a58512dcf2`
- modules.py SHA-256：
  `7a06a14a7dc95c5f65cd6b09ed126013821512489dcfec2e58bd8b544ce46656`
- ecapa_tdnn.py SHA-256：
  `847ef748d91acaec8b58859757481f7642772999b1e702680f06dc8dbdd2408d`
- 模型加载检查：`missing_keys=[]`；唯一忽略项为训练期分类头
  `loss_calculator.projection.weight`
- 本地原始指标文件：`results/accuracy/asv_ab_c1_n32.json`
- 随包严格 v2 结果：`results/accuracy/asv_ab_c1_n32_strict.json`
- 远端来源路径：
  `/workspace/user_data/minicpm-vllm-omni/results/accuracy/asv_proxy/asv_ab_c1_n32_strict.json`
- 严格运行指纹：
  `97bb7c4af9ead07bf1c94aff9093b0f669866036d5d23663a0a80f763b5485dc`

`validate_submission.py` 会校验随包 strict-v2 JSON 的固定运行指纹、96 个输入
WAV 哈希、三份源码哈希、32/32 完成状态及 `quality_gate_passed=true`，并确认其
核心统计值与旧版结果一致。这里的 quality gate 仅表示代理计算完整且数值有限，
不是比赛 ASV 阈值。

严格 v2 复跑会把 checkpoint、meta、三份源码、seed/范围以及每条 prompt、
baseline、candidate WAV 的路径和内容 SHA-256 共同写入运行指纹。旧版进度文件的
负向测试按预期以返回码 1 拒绝恢复；非有限相似度、缺样本或失败样本均会令
`quality_gate_passed=false`。严格复跑仍为 32/32、0 失败，统计值与上表完全一致。

## 复现命令

```bash
OMP_NUM_THREADS=32 MKL_NUM_THREADS=32 TORCH_DEVICE_BACKEND_AUTOLOAD=0 \
/usr/local/python3.12.13/bin/python3 \
  submission/scripts/eval_seed_tts_wavlm_proxy.py \
  --checkpoint /workspace/shared_assets/datasets/CowboyZ/seed-tts-eval/wavlm_large_finetune.pth \
  --dataset-root /workspace/user_data/minicpm-vllm-omni/datasets/seedtts_testset \
  --baseline-wav-dir /workspace/user_data/minicpm-vllm-omni/results/accuracy/baseline/wavs \
  --candidate-wav-dir /workspace/user_data/minicpm-vllm-omni/results/accuracy/steps9/wavs \
  --seed-tts-eval-root /workspace/user_data/minicpm-vllm-omni/seed-tts-eval \
  --s3prl-root /workspace/user_data/minicpm-vllm-omni/asv_deps/s3prl-7ab62 \
  --num-prompts 32 --seed 0 --threads 32 \
  --output /workspace/user_data/minicpm-vllm-omni/results/accuracy/asv_proxy/asv_ab_c1_n32.json
```

共享目录只读使用，评测过程中没有修改 `/workspace/shared_assets`。
