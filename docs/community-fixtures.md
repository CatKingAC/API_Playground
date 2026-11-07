# 社区 fixture（false-green / co-review）

PrismLab（本仓库 `usermbzlj/API_Playground`）是 **EigenFlux 共审 false-green 探测器、relay 语义夹具及相关结构型负控** 的唯一交付目标。

独立仓库 [usermbzlj/llm-bench](https://github.com/usermbzlj/llm-bench) 仍保留历史记录与 MIT 引擎血缘，但 **不再接受新的社区 fixture PR**。请勿向该仓提交 `fixtures/` 更新；在本仓 `integrations/llm-bench/upstream/fixtures/` 下新增或演进版本即可。

## 目录约定

- 每个主题一个子目录（例如 `relay_error_semantics/`、`false_green_shapes/`、`credential_pool_exhaustion/`）。
- 版本脚本命名为 `{name}_v0_{n}.py`；说明与结构来源写在同级 `META_v0_{n}.txt`（保留 EigenFlux / 参与者致谢，行数据中去个人化）。
- 夹具均为 **analyze_only、stdlib only**；通过自测时进程 **exit 0**。
- 参考输出可提交为 `run_out_v0_*.json`（可选，便于 diff）。

引擎与网页压测桥接见 [integrations/llm-bench/README.md](../integrations/llm-bench/README.md)。

## 运行自测

仅需 Python 3.11+，无需 `httpx` 或压测虚拟环境：

```bash
python3 integrations/llm-bench/run_fixture_selftests.py
```

脚本读取各目录 `META*.txt` 中的 `run:` 行；若无 META，则对该目录执行最高版本号的 `*_v0_*.py`。也可在单个 fixture 目录内按 META 说明手动 `python3 …`。

上游 Python 单元测试（需 `npm run setup:bench` 后）：

```bash
cd integrations/llm-bench/upstream && python3 -m pytest tests/
```

## 提交前检查

1. 在 fixture 目录内运行对应脚本，确认 exit 0 与 META 中的 selftest 计数一致。
2. 根目录 `python3 integrations/llm-bench/run_fixture_selftests.py` 全部通过。
3. 不引入密钥、真实凭证或需付费 API 的默认路径；`fetch_*` 类脚本应仅用于可选复现并文档化。

## 与压测引擎的关系

社区 fixture 验证 **统计/门禁语义**（假绿、截断、relay 错误形态等），与网页/API 使用的 `bridge.py` 压测路径相互独立。融合说明中的引擎 pin 见 [fusion.md](fusion.md)。
