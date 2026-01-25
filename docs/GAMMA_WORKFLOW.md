# Gamma Workflow

## 概要

Gammaプロジェクトは、betaのLevel3を使って新しいアプリ/機能開発を行うためのワークフローです。beta自体を壊さないよう、成果物は別ディレクトリに生成します。

## 作業ディレクトリ命名規則

- 命名規則: `~/NewFUHI-gamma-YYYYMMDD` (例: `~/NewFUHI-gamma-20260105`)
- YYYYMMDDは開始日の日付を使用

## 運用手順

1. 作業ディレクトリを作成:
   ```bash
   mkdir ~/NewFUHI-gamma-$(date '+%Y%m%d')
   ```

2. ディレクトリに移動し、バージョン管理を開始:
   ```bash
   cd ~/NewFUHI-gamma-$(date '+%Y%m%d')
   git init
   ```

## Level3開始時のrequirements_textテンプレ

Level3を開始する際のrequirements_textに、以下の内容を明記してください:

```
Create a new app/feature in the directory: ~/NewFUHI-gamma-YYYYMMDD

Constraints:
- Do not modify any files outside of this directory
- Generate all code and files within the specified directory
- Use the directory as the project root
- Do not touch or alter the existing NewFUHI-beta system
```

## stuck proposalが出たときの人間の判断手順

Level3の実行中にstuck proposalが出た場合:

1. stuck proposalの内容を確認 (承認UIで表示される選択肢)
2. 以下の選択肢から適切なものを選ぶ:
   - **A: 最小修正** - 現在の問題を特定して小さな修正を試す
   - **B: やり直し/リセット** - プロジェクトをリセットして最初からやり直す
   - **C: 確認質問** - 人間に詳細を聞く
3. 選択したアクションを承認して、次のステップに進める

提案は自動実行されず、人間による判断を待つため、慎重に選択してください。

## Bridge Dashboard 開発運用

Bridge Dashboard (ポート8502) と Roo Orchestrator の開発・テスト時は、以下のスクリプトを使用してください:

- **起動**: `bash apps/bridge-dashboard/scripts/dev_up_bg.sh`
  - バックグラウンドで両プロセスを起動
  - 8502ポート競合時は自動で既存プロセスを停止
  - 起動後にhealthチェックを実施

- **状態確認**: `bash apps/bridge-dashboard/scripts/dev_status_bg.sh`
  - プロセス実行状態、ポート状態、healthチェックを表示

- **ログ確認**: `bash apps/bridge-dashboard/scripts/dev_logs_bg.sh`
  - 両プロセスのログを tail -F で表示
  - `--bridge` または `--orchestrator` で個別表示可能

- **停止**: `bash apps/bridge-dashboard/scripts/dev_down_bg.sh`
  - 両プロセスを安全に停止 (TERM→待機→KILL)

**環境変数**: `BRIDGE_DATA_ROOT` (未指定時は `$HOME/AI_WORKSPACE_SAFE/bridge-data`)
- inbox/outbox/approvals ディレクトリが配置される場所