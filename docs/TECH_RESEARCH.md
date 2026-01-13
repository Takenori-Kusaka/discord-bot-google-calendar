# AI Agent技術調査レポート

*調査日: 2026-01-14*

## 調査目的

本プロジェクト「家庭内執事 黒田」に最適なAI Agent技術を選定する。

---

## 2025-2026年 AI Agentフレームワーク比較

### 主要フレームワーク一覧

| フレームワーク | 提供元 | Claude対応 | 本番対応 | 学習曲線 |
|--------------|--------|-----------|---------|---------|
| Claude Agent SDK | Anthropic | ◎ 公式 | ◎ | 低 |
| LangGraph | LangChain | ○ | ◎ | 高 |
| CrewAI | CrewAI | ○ | ○ | 低 |
| OpenAI Agents SDK | OpenAI | ✕ | ◎ | 低 |
| AutoGen | Microsoft | △ | △ | 中 |
| OpenAI Swarm | OpenAI | ✕ | ✕ 教育用 | 低 |

---

## 各フレームワーク詳細

### 1. Claude Agent SDK（推奨）

**概要**: Anthropic公式のエージェントSDK。Claude Codeの基盤技術。

**特徴**:
- エージェントにコンピュータを与える設計思想
- ファイル書き込み、コマンド実行、作業の反復が可能
- MCP（Model Context Protocol）対応

**アーキテクチャ**:
```
Agent Loop:
1. Context Gather → 2. Action Execute → 3. Verify Work → (repeat)
```

**メリット**:
- Claude APIに最適化
- シンプルなエージェントループ
- 本番環境で実証済み（Claude Code）

**デメリット**:
- 他のLLMへの移行は難しい

**参考**: [Building agents with the Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)

---

### 2. LangGraph

**概要**: LangChainの後継。グラフベースのワークフロー管理。

**特徴**:
- 各エージェントが独立したノードとして機能
- 有向グラフで接続
- 複雑な分岐・ループに対応

**メリット**:
- 最も柔軟なワークフロー制御
- 状態管理が強力
- マルチLLM対応

**デメリット**:
- 学習曲線が急
- デバッグが難しい

**参考**: [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)

---

### 3. CrewAI

**概要**: ロールベースのマルチエージェントフレームワーク。

**特徴**:
- 各エージェントに役割（研究者、開発者など）を割り当て
- YAML設定で簡単にセットアップ
- 組み込みメモリ機能

**メリット**:
- 初心者に優しい
- 本番向けシステムに適合
- 短期間での開発が可能

**デメリット**:
- 線形タスクフロー中心
- 複雑な要件には限界あり（6-12ヶ月でリライトが必要になるケースあり）

**参考**: [CrewAI Documentation](https://docs.crewai.com/)

---

### 4. OpenAI Swarm / Agents SDK

**概要**: OpenAIの軽量マルチエージェントフレームワーク。

**注意**:
- **Swarmは教育目的で本番非推奨**
- 2025年3月にAgents SDKに移行
- **OpenAI API専用（Claude非対応）**

**参考**: [OpenAI Agents SDK](https://openai.com/index/new-tools-for-building-agents/)

---

### 5. AutoGen（Microsoft）

**概要**: Microsoftのマルチエージェントフレームワーク。

**注意**:
- 2025年10月にSemantic Kernelと統合
- 2026年Q1にMicrosoft Agent Frameworkとして正式リリース予定

**参考**: [Microsoft AutoGen](https://microsoft.github.io/autogen/)

---

## 本プロジェクトへの適用

### 決定事項

| Phase | アプローチ | 理由 |
|-------|----------|------|
| **Phase 1 (MVP)** | フレームワークなし | シンプルな予定通知のみ |
| **Phase 2+** | Claude Agent SDK検討 | 必要に応じて導入 |

### MVP実装方針

```python
# シンプルなエージェントループ
async def butler_loop():
    # 1. カレンダー取得
    events = await get_calendar_events()

    # 2. Claude APIで判断
    important_events = await claude_filter_events(events)

    # 3. Discord通知
    await send_discord_notification(important_events)
```

### Phase 2以降の拡張

複雑なワークフローが必要になった場合：
- Claude Agent SDKを導入
- MCPでツール連携を拡張
- 状態管理が必要ならLangGraphも検討

---

## 既存コードの問題点

現在の`agents/`ディレクトリはOpenAI Swarmを使用：

```python
# agents/base_agent.py
from swarm import Agent as SwarmAgent
```

**問題**:
1. SwarmはOpenAI API専用（Claude非対応）
2. Swarmは本番環境非推奨
3. 既存コードは動作しない

**対応**: Phase 1では既存コードを参考にしつつ、新規実装する

---

## 参考リンク

- [Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Top 5 Open-Source Agentic Frameworks in 2026](https://research.aimultiple.com/agentic-frameworks/)
- [LangGraph vs AutoGen vs CrewAI Comparison](https://latenode.com/blog/platform-comparisons-alternatives/automation-platform-comparisons/langgraph-vs-autogen-vs-crewai-complete-ai-agent-framework-comparison-architecture-analysis-2025)

---

*最終更新: 2026-01-14*
