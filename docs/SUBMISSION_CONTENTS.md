# GitHub提出内容

公開対象はこの `submission_ball_strike` リポジトリだけです。親の講義フォルダ全体は提出しません。

| 対象 | 公開する理由 |
|---|---|
| README.md、environment.json、tested_versions.json、constraints-colab.txt | 作品説明、動画リンク、環境とバージョン |
| scripts/、configs/、assets/ | 制御・教師生成・変換・学習・推論・録画で使用するコードと設定 |
| colab_strike_train.ipynb | 学習を再実行する手順 |
| data/strike_raw/、data/strike_lerobot/ | 使用した教師データと変換済みデータ |
| checkpoints/act_strike/ | 動画で使用した学習済み重み、モデル設定、loss |
| docs/AI_SWITCH.md | 固定制御とAI制御の違いの説明 |
| docs/experiments/ | 教師の元ログ、初回失敗、指令周期修正、録画試行の根拠 |
| docs/report_draft.md | PDFレポート用の下書き。これだけではPDF提出の代わりにならない |
| .gitignore、.gitattributes | 非公開ファイルの除外と改行設定 |

## 公開しないもの

- パスワード、個人用メモ、アカウント情報、講義動画の認証情報。
- 親フォルダの講義資料・宿題・旧お辞儀プロジェクト。
- `videos/` のMP4・スクリーンショット・録画素材（実演はYouTubeリンク）。
- `checkpoints/connection_check*` の短い接続試験用モデル。
- `results/` に増える全試行ログ。必要な試行だけ `docs/experiments/` に保存。
- `docs/status.md` の長い過去の作業メモ（手元には残す）。
- Pythonキャッシュ、仮想環境、Dockerイメージ、ZIP。

失敗記録内のコードと設定の写しは、調整前の状態を説明する資料です。現在の実行コードは `scripts/` を使用してください。

## 確認コマンド

```bash
git status --short
git ls-files
git ls-files videos _private checkpoints/connection_check
```

最後のコマンドで対象が出ないことを確認します。`.gitignore` は既に追跡されたファイルを自動では取り除かないので、公開対象は `git ls-files` で確認してください。
