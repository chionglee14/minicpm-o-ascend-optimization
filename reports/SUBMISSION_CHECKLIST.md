# 最终提交清单

## 已完成

- [x] MiniCPM-o 4.5 在单卡 Ascend 910C 上完成 vLLM-Omni 三阶段部署。
- [x] 保留可读基线配置和一键回退配置。
- [x] `steps9` 只修改 `token2wav_n_timesteps: 10 -> 9`。
- [x] 完成同机严格 `c1/n32` 基线与候选 A/B，并做两次候选复测。
- [x] 完成 `c1/n32`、`c4/n64`、`c8/n128` 三档矩阵，共 224 个计时请求。
- [x] 完成 32 条 WER 配对代理和 32 条 ASV 配对代理。
- [x] 保存原始 JSON、环境脚本、benchmark 脚本、性能报告和复现说明。
- [x] ASV 严格脚本绑定 checkpoint、源码和输入 WAV 哈希，并通过旧进度拒绝负测。
- [x] 将 strict-v2 ASV 原始 JSON 与环境快照纳入证据包和 SHA-256 校验。
- [x] 在性能报告中披露高并发 median/p99 长尾和未覆盖指标。
- [x] 生成正式 PDF 性能报告，并逐页渲染检查版式与中文显示。

## 仍需正式完成

- [ ] 使用主办方最终环境运行正式 WER/ASV；本地代理结果不能替代官方成绩。
- [ ] 正式赛事提交包补入完整服务日志；公开 GitHub 仓库只保留脱敏环境快照。
- [ ] 录制 Demo 可用视频。这需要展示真实终端和播放效果，建议由参赛者本人录屏。
- [ ] 提交前核对赛事平台最新文件命名、压缩包大小及上传截止时间。

## 建议的 60～90 秒 Demo 录屏流程

终端 A 启动候选服务：

```bash
cd /workspace/user_data/minicpm-vllm-omni/submission
CONFIG="$PWD/configs/experiment_steps9.yaml" \
  bash scripts/start_server.sh
```

服务显示 ready 后，终端 B 执行：

```bash
cd /workspace/user_data/minicpm-vllm-omni/submission
curl -fsS http://127.0.0.1:8091/health && echo
npu-smi info
bash scripts/run_demo.sh
```

录屏应清楚展示：

1. 使用的是 Ascend 910C 和 `experiment_steps9.yaml`。
2. `/health` 正常，文本与流式语音请求成功。
3. `WAV_OK` 和 `WAV_SUMMARY` 校验通过，并实际播放一小段生成 WAV。
4. 不需要在视频里宣称官方 WER/ASV 已通过。

## 提交前最后核验

```bash
bash -n scripts/*.sh
python3 -m py_compile scripts/*.py
python3 scripts/validate_submission.py
sha256sum -c RESULT_MANIFEST.sha256
unzip -l ../vllm_omni_submission_final.zip
sha256sum ../vllm_omni_submission_final.zip
```

性能选择结论以 `reports/EXPERIMENTS.md` 为准；ASV 协议边界以
`reports/ASV_PROXY.md` 为准。
