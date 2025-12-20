# Roo: Project Rules (NewFUHI)

## Absolute rules
- 作業前に必ず `pwd` と対象ファイルの存在確認（ls / cat）を行う
- 変更は「実ファイルの編集」を伴うこと（口頭で“完了”と言わない）
- 変更したファイル一覧と差分要約を最後に出す

## Admin / Permission work rules
- AdminSite を二重運用しない（/admin のみ。custom_admin を作らない）
- ロール判定は必ず Staff を参照（Staff.user == request.user）
- モデル登録漏れがないか admin.py を確認してから結論を出す
