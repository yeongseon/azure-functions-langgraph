# Azure Functions LangGraph

[![PyPI](https://img.shields.io/pypi/v/azure-functions-langgraph.svg)](https://pypi.org/project/azure-functions-langgraph/)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://pypi.org/project/azure-functions-langgraph/)
[![CI](https://github.com/yeongseon/azure-functions-langgraph/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/azure-functions-langgraph/actions/workflows/ci-test.yml)
[![Release](https://github.com/yeongseon/azure-functions-langgraph/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/yeongseon/azure-functions-langgraph/actions/workflows/publish-pypi.yml)
[![Security Scans](https://github.com/yeongseon/azure-functions-langgraph/actions/workflows/security.yml/badge.svg)](https://github.com/yeongseon/azure-functions-langgraph/actions/workflows/security.yml)
[![codecov](https://codecov.io/gh/yeongseon/azure-functions-langgraph/branch/main/graph/badge.svg)](https://codecov.io/gh/yeongseon/azure-functions-langgraph)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)
[![Docs](https://img.shields.io/badge/docs-gh--pages-blue)](https://yeongseon.github.io/azure-functions-langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

この文書の言語: [한국어](README.ko.md) | **日本語** | [简体中文](README.zh-CN.md) | [English](README.md)

> **ベータ版について** — このパッケージは活発に開発中（`0.4.0`）です。コアAPIは安定化に向かっていますが、マイナーリリース間で変更される可能性があります。GitHubでイシューを報告してください。

最小限のボイラープレートで [LangGraph](https://github.com/langchain-ai/langgraph) グラフを **Azure Functions** HTTPエンドポイントとしてデプロイできます。

---

**Azure Functions Python DX Toolkit** の一部

## なぜ必要か

Azure FunctionsでLangGraphをデプロイするのは、思ったより大変です。

- LangGraphはAzure Functionsネイティブなデプロイアダプターを提供していません
- コンパイル済みグラフをHTTPエンドポイントとして公開するには、繰り返しの接続コードが必要です
- チームごとに同じinvoke/streamラッパーを毎回新たに実装しています

このパッケージは、Azure Functions Python v2でLangGraphグラフをサーブするための専用アダプターを提供します。

## 主な機能

- **ボイラープレート不要のデプロイ** — コンパイル済みグラフを登録するだけで、HTTPエンドポイントが自動生成されます
- **Invokeエンドポイント** — `POST /api/graphs/{name}/invoke` で同期実行
- **Streamエンドポイント** — `POST /api/graphs/{name}/stream` でバッファリングされたSSEレスポンス
- **Healthエンドポイント** — `GET /api/health` で登録済みグラフ一覧とチェックポインターの状態を確認
- **チェックポインター転送** — LangGraphネイティブのconfigによるスレッドベースの会話状態管理
- **Stateエンドポイント** — `GET /api/graphs/{name}/threads/{thread_id}/state` でスレッド状態を検査（サポートされている場合）
- **グラフごとの認証** — `register(graph, name, auth_level=...)` でアプリレベルの認証をグラフごとにオーバーライド
- **LangGraph Platform API互換** — スレッド、ラン、アシスタント、ステートのためのSDK互換エンドポイント (v0.3+)
- **永続ストレージバックエンド** — Azure Blob Storageチェックポインター及びAzure Table Storageスレッドストア (v0.4+)

## LangGraph Platformとの比較

| 機能 | LangGraph Platform | azure-functions-langgraph |
|------|-------------------|--------------------------|
| ホスティング | LangChain Cloud（有料） | ユーザーのAzureサブスクリプション |
| アシスタント | 組み込み | SDK互換API (v0.3+) |
| スレッドライフサイクル | 組み込み | 作成、取得、更新、削除、検索、カウント (v0.3+) |
| ラン | 組み込み | スレッド付き + スレッドレスラン (v0.4+) |
| ステート読み取り/更新 | 組み込み | get_state + update_state (v0.4+) |
| ステート履歴 | 組み込み | フィルタリング対応チェックポイント履歴 (v0.4+) |
| ストリーミング | True SSE | バッファリングSSE |
| 永続ストレージ | 組み込み | Azure Blob + Table Storage (v0.4+) |
| インフラ | マネージド | Azure Functions（サーバーレス） |
| コストモデル | 使用量/シートベース | Azure Functions料金プラン |

## 対象範囲

- Azure Functions Python **v2プログラミングモデル**
- LangGraphグラフのデプロイとHTTP公開
- LangGraphランタイムの関心事: invoke, stream, threads, runs, state
- バリデーションとOpenAPIのためのコンパニオンパッケージ連携

このパッケージは**デプロイアダプター**です — LangGraphをラップしますが、置き換えるものではありません。

## このパッケージが行わないこと

このパッケージは以下を担当しません:
- OpenAPIドキュメント生成またはSwagger UI — [`azure-functions-openapi`](https://github.com/yeongseon/azure-functions-openapi)を使用
- LangGraph契約外のリクエスト/レスポンスバリデーション — [`azure-functions-validation`](https://github.com/yeongseon/azure-functions-validation)を使用
- LangGraph以外の汎用グラフサーブ抽象化

> **注意 (v0.4.x):** このパッケージは後方互換性のため `GET /api/openapi.json` を引き続き提供しています。このエンドポイントはdeprecatedであり、v0.5.0で専用の `azure-functions-openapi` パッケージに移行されます。

## インストール

```bash
pip install azure-functions-langgraph
```

Azureサービスによる永続ストレージ:

```bash
# Azure Blob Storageチェックポインター
pip install azure-functions-langgraph[azure-blob]

# Azure Table Storageスレッドストア
pip install azure-functions-langgraph[azure-table]

# 両方
pip install azure-functions-langgraph[azure-blob,azure-table]
```

Azure Functionsアプリには以下の依存関係も含めてください:

```text
azure-functions
langgraph
azure-functions-langgraph
```

ローカル開発用インストール:

```bash
git clone https://github.com/yeongseon/azure-functions-langgraph.git
cd azure-functions-langgraph
pip install -e .[dev]
```

## クイックスタート

```python
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from azure_functions_langgraph import LangGraphApp


# 1. 状態を定義
class AgentState(TypedDict):
    messages: list[dict[str, str]]


# 2. ノード関数を定義
def chat(state: AgentState) -> dict:
    user_msg = state["messages"][-1]["content"]
    return {"messages": state["messages"] + [{"role": "assistant", "content": f"Echo: {user_msg}"}]}


# 3. グラフをビルド
builder = StateGraph(AgentState)
builder.add_node("chat", chat)
builder.add_edge(START, "chat")
builder.add_edge("chat", END)
graph = builder.compile()

# 4. デプロイ
app = LangGraphApp()
app.register(graph=graph, name="echo_agent")
func_app = app.function_app  # ← Azure Functionsアプリとして使用
```

### 生成されるエンドポイント

1. `POST /api/graphs/echo_agent/invoke` — エージェントの呼び出し
2. `POST /api/graphs/echo_agent/stream` — エージェントレスポンスのストリーミング（バッファリングSSE）
3. `GET /api/graphs/echo_agent/threads/{thread_id}/state` — スレッド状態の検査
4. `GET /api/health` — ヘルスチェック
5. `GET /api/openapi.json` — OpenAPIスペック *(deprecated; v0.5.0でazure-functions-openapiに移行)*

### リクエスト形式

```json
{
    "input": {
        "messages": [{"role": "human", "content": "Hello!"}]
    },
    "config": {
        "configurable": {"thread_id": "conversation-1"}
    }
}
```

### v0.3.0からのアップグレード

v0.4.0はv0.3.0と完全に後方互換です。ブレイキングチェンジはありません。

- **新しいオプショナルextras**: `pip install azure-functions-langgraph[azure-blob,azure-table]`で永続ストレージ
- **新しいプラットフォームエンドポイント**: スレッドCRUD、ステート更新/履歴、スレッドレスラン、アシスタントカウント
- **新しいプロトコル**: `UpdatableStateGraph`, `StateHistoryGraph` (`azure_functions_langgraph.protocols`から利用可能)

## 使用に適したケース

- LangGraphエージェントをAzure Functionsにデプロイしたい場合
- LangGraph Platformのコストなしでサーバーレスデプロイが必要な場合
- コンパイル済みグラフのHTTPエンドポイントを最小限の設定で必要とする場合
- LangGraphチェックポインターによるスレッドベースの会話状態が必要な場合
- Azure Blob/Table Storageによる永続的な状態保存が必要な場合

## ドキュメント

- プロジェクトドキュメント: `docs/`
- テスト済みサンプル: `examples/`
- 製品要件: `PRD.md`
- 設計原則: `DESIGN.md`

## エコシステム

このパッケージは **Azure Functions Python DX Toolkit** の一部です。

**設計原則:** `azure-functions-langgraph`はLangGraphランタイム公開を担当。`azure-functions-validation`はバリデーションを担当。`azure-functions-openapi`はAPIドキュメントを担当。

| パッケージ | 役割 |
|-----------|------|
| **azure-functions-langgraph** | Azure Functions用LangGraphデプロイアダプター |
| [azure-functions-validation](https://github.com/yeongseon/azure-functions-validation) | リクエスト/レスポンスバリデーションとシリアライゼーション |
| [azure-functions-openapi](https://github.com/yeongseon/azure-functions-openapi) | OpenAPI仕様生成とSwagger UI |
| [azure-functions-logging](https://github.com/yeongseon/azure-functions-logging) | 構造化ロギングとオブザーバビリティ |
| [azure-functions-doctor](https://github.com/yeongseon/azure-functions-doctor) | デプロイ前診断CLI |
| [azure-functions-scaffold](https://github.com/yeongseon/azure-functions-scaffold) | プロジェクトスキャフォールディング |
| [azure-functions-durable-graph](https://github.com/yeongseon/azure-functions-durable-graph) | Durable Functionsベースのマニフェストグラフランタイム |
| [azure-functions-python-cookbook](https://github.com/yeongseon/azure-functions-python-cookbook) | レシピとサンプル |

## 免責事項

このプロジェクトは独立したコミュニティプロジェクトであり、MicrosoftまたはLangChainとの提携、承認、保守関係にはありません。

AzureおよびAzure FunctionsはMicrosoft Corporationの商標です。
LangGraphおよびLangChainはLangChain, Inc.の商標です。

## ライセンス

MIT
