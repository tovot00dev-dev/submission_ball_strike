# お辞儀してボールを打つ CRANE+ V2

Physical AI 応用1 最終課題（ID：142097）。ROS 2 HumbleとGazeboで、お辞儀・ハンドの開閉のあと、アームを振ってボールを箱の的へ転がします。

実演動画：https://www.youtube.com/watch?v=L1a21ANGflg （約1分47秒、倍速編集なし）。

## AIが担当する部分

お辞儀・ハンド開閉・構えは固定コード、最後の打撃は学習済みACTが関節状態から動作指令を予測します。モデルがない場合に教師軌道へフォールバックしません。

教師動作の実測ログから打撃1エピソードを抽出し、20 Hz・66フレームへ変換しました。ColabのT4 GPUで1500ステップ学習し、その重み・設定・lossを checkpoints/act_strike/ に同梱しています。

ボール・的は固定配置です。画像・物体座標を入力するモデルではなく、異なる配置への対応や安定した成功率は未検証です。初回AI試行では外れ、推論時間が指令周期に余分に加算される処理を修正した後、利用者が命中を目視確認しました。録画時にも結果にばらつきがあり、接触センサーによる自動採点は未実装です。

## 構成

- scripts/preview.py：固定区間とACT打撃のROS制御・ログ。
- scripts/act_server.py：ACT重みのロードと policy.select_action() による推論。
- scripts/strike_learning.py：教師ログ抽出、LeRobot形式への変換、ACT学習。
- configs/：シーン・動作・学習設定。
- data/strike_raw/、data/strike_lerobot/：今回の教師データと変換済みデータ。
- checkpoints/act_strike/：使用モデル、設定、学習loss。
- docs/experiments/：失敗記録、周期修正、撮影試行。
- colab_strike_train.ipynb：Colab学習ノートブック。
- environment.json、constraints-colab.txt：環境と依存バージョン。

## 実行

Dockerを利用できるLinux/WSL環境を想定します。ROS・Gazeboは教材のDockerイメージ、ACTは pai_training のpixi環境を使用します。

```bash
# このリポジトリ内。新規コンテナを作る場合のみ。
bash scripts/start_container.sh
```

ブラウザで http://localhost:6080 を開き、Terminatorを使います。既存の同名コンテナは削除・上書きしません。

```bash
# コンテナ内：初回のACT環境準備
cd /workspace/submission_ball_strike
bash scripts/setup_learning_env.sh
```

空の環境からの全手順は未検証です。実際に使用したリビジョンは environment.json を参照してください。pixiの導入が必要な場合は https://pixi.sh を参照します。

ターミナルA：

```bash
source /opt/ros/humble/setup.bash
source /home/ubuntu/airobot_ws/install/setup.bash
ros2 launch /workspace/submission_ball_strike/scripts/front_center.launch.py
```

ターミナルB（Gazeboの起動後）：

```bash
cd /workspace/submission_ball_strike
python3 scripts/preview.py --check
bash scripts/ai.sh
```

他のテレオペ・制御プログラムは止めます。開始時に球を除去し、構えた後に生成します。ログは results/ に保存。停止はCtrl+C。シミュレーション専用です。教師版との比較は bash scripts/preview.sh で行えますが、これはAI制御ではありません。

## 学習の再実行

同梱データを使う場合、抽出・変換は不要です。

```bash
bash scripts/learning.sh export
```

親フォルダへ生成される ball_strike_colab.zip を、Colabで開いた colab_strike_train.ipynb の最初のセルへアップロードします。GPUを選び、上から順に実行します。出力の act_strike.zip を checkpoints/act_strike/ へ展開します。既存のZIPやモデルは先に別の場所へ保存してください。学習出力の上書きを防ぐチェックがあります。

新しい教師データは教師版をGazeboで実行し、生成ログを明示指定します。既存データは先に別の場所へ保存してください。

```bash
bash scripts/learning.sh prepare --logs results/preview_実行番号.json
bash scripts/learning.sh convert
```

AIの詳細は [AI_SWITCH.md](docs/AI_SWITCH.md)、初回失敗は [実験記録](docs/experiments/2026-11-01_act_strike_miss_01/README.md) を参照。lossは命中率ではありません。学習の乱数seedは固定していますが、物理シミュレーションの結果まで保証しません。

## 参考・利用した上流コード

- https://github.com/matsuolab/pai_training ：学習環境。
- https://github.com/huggingface/lerobot ：ACT実装・データセット。
- https://github.com/matsuolab/physicalai_teleop ：操作手順・関節・トピックの参考。
- https://github.com/AI-Robot-Book-Humble/docker-ros2-desktop-ai-robot-book-humble ：ROS・Gazebo・CRANE+環境。

front_center.launch.py は教材環境の起動ファイルを元に初期配置の読み込みを変更したもので、元のRT Corporationの著作権・Apache-2.0表示を保持しています。独自の変更は固定挨拶、教師軌道、球配置、打撃のみの学習・推論、指令周期調整、実験記録と動画作成です。
