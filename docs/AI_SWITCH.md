# 打撃を固定コードからAIへ切り替える

## 変わる範囲

| 区間 | 制御 |
|---|---|
| お辞儀・ぱちぱち・直立 | 従来の固定コード |
| 斜めの構え・振りかぶり・打つ高さへの準備 | 従来の固定コード |
| 球を出した後の打撃 | AIモードでは学習済みACTモデル |
| 終了時刻、指令の上限、物の配置 | 通常コード |

`bash scripts/preview.sh` は教師版。`bash scripts/ai.sh` はAI版です。AI版はモデルファイルがない場合にエラーで停止し、教師の角度列で代わりに動くことはありません。

## どの書き方がAIなのか

`scripts/act_server.py` の中心は次の処理です。

```python
policy = ACTPolicy.from_pretrained(model)  # 学習済みの重みを読む
policy.eval()
observation = {
    'observation.state': state,
    'observation.environment_state': state,
}
with torch.inference_mode():
    action = policy.select_action(observation)  # 現在の関節状態から動作を予測
```

`state` は現在の5つの関節角度です。手で用意した打撃の角度列を読むのではなく、学習したニューラルネットワークに入力し、出力を受け取ります。画像や球・的の座標は入力しないため、固定配置専用です。

予測した `action` を `scripts/preview.py` のAI分岐で受け取り、範囲・変化量を制限してROSへ送ります。教師用の補間式はAI分岐では使いません。補正前の予測 `raw_action` と実際の指令 `command` の両方をログに残します。

学習側の `scripts/strike_learning.py` では次を繰り返します。

```python
loss, _ = policy.forward(batch)  # お手本の指令との違いを計算
loss.backward()                 # 重みをどちらへ変えるか計算
optimizer.step()               # モデルの重みを更新
```

関数名にAIと付けるだけではAIにはなりません。実際に学習した重みを保存し、推論時にそのモデルを使う点が違いです。

## 今回の学習準備

直近の実測ログから `strike_teacher_preview` 区間のみを取り出します。挨拶、戻し、旧お辞儀データは混ぜません。ログと同じものを何度もコピーしてデータを水増しすることもしません。

現在の初回データは1回のお手本です。まず実装の接続を確認するための最小データで、汎化や安定した命中率の根拠にはなりません。必要なら追加試行を別々のエピソードとして集めてから学習し直します。

```bash
# コンテナ内
cd /workspace/submission_ball_strike
bash scripts/learning.sh prepare
bash scripts/learning.sh convert
bash scripts/learning.sh export
```

初回の抽出・変換は作成時に実行済みの可能性があるため、出力がある場合は上書きせず停止します。再実行前に状況を確認してください。今回のフォルダ以外は変更しません。

## Colabで本学習する

1. Windows側の課題フォルダにある `ball_strike_colab.zip` を確認する。
2. Colabでプロジェクト内の `colab_strike_train.ipynb` を開き、GPUランタイムを選ぶ。
3. ZIPをアップロードし、順番にセルを実行する。
4. ダウンロードした `act_strike.zip` の中身を `submission_ball_strike/checkpoints/act_strike/` に展開する。
5. 直下に `model.safetensors`、`config.json`、`experiment.json` があることを確認。

2026-11-01に利用者がColabのT4 GPUで1500ステップの学習を実行し、モデルをダウンロードしました。`checkpoints/act_strike/` が本学習の出力です。短いCPU接続テスト用のモデルは提出対象から除外します。

## AIを動かす

Gazeboは専用のfront_center.launch.pyで起動し、テレオペや他の制御は止めます。

```bash
cd /workspace/submission_ball_strike
bash scripts/ai.sh
```

モデルを先に読み込んでから、固定の挨拶と構えを行い、打撃時だけAIへ交代します。初めてのモデルはうまく動かない可能性があるため、Gazeboを見ながら確認します。止めるときは実行側でCtrl+C。

AI版の実行ログは `results/preview_*.json` の `phase: strike_ai` を確認します。学習条件はモデルフォルダの `experiment.json`、損失は `loss.csv`。球と箱の軌跡は `results/world_*.csv` です。学習損失・モデル出力・命中の成否はそれぞれ別に確認します。

## 提出時の表現

「挨拶と準備は固定制御。打撃部分は、自動生成した教師動作の実測ログを用いてACTで模倣学習し、現在の関節状態から予測した指令で制御した」と説明します。教師の成功動画をAIの成功動画として扱いません。
