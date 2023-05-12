# E-Ink Weather Panel

## 概要

電子ペーパディスプレイに，Raspberry Pi を通じて下記の情報を表示するためのスクリプトです．

-   天気予報
-   各種センサーの情報

表示サンプルは下記になります．

![表示サンプル](img/example.png)

## 詳細

大きく次の処理を行います．

-   Yahoo から天気予報の情報を取得
-   気象庁のページから雨雲画像を取得
-   Influx DB からセンサー情報を取得
-   センサ情報を Matplotlib で描画
-   夜間，照度に応じてライトのアイコンを描画
-   Raspberry Pi にログインして，フレームバッファに描画


## 準備

### ライブラリのインストール

```bash:bash
apt-get install -y python3 python3-pip
apt-get install -y python3-yaml python3-coloredlogs
apt-get install -y python3-pil python3-matplotlib python3-pandas
apt-get install -y python3-opencv
apt-get install -y python3-paramiko
pip3 install -r requirements.txt
```

後述する Docker を使った方法で実行する場合は，インストール不要です．

また，Raspberry Pi 側では下記を行っておきます．

```bash:bash
apt-get install -y fbi
```

## 設定

### 設定ファイルの編集
`config.yaml` に記述します．サンプルを `config.example.yaml` として登録してありますので参考にしてください．

Raspberry Pi のホスト名については，`docker-compose.yaml` の RASP_HOSTNAME にて設定します．

Influx DB からセンサー情報を取得する部分( `sensor_data.py` の `fetch_data` )はお手元の環境に合わせて修正が必要かもしれません．

### Raspberry Pi の画面消灯禁止

`/boot/firmware/cmdline.txt` に `consoleblank=0` を追記して画面が消灯しないようにします

## 実行方法

```bash:bash
./src/update.py
```

Docker で実行する場合，下記のようにします．

```bash:bash
docker-compose build
docker-compose up -d
```

## ちょっと頑張った点

雨雲レーダと天気予報のアイコンを表示する部分だけ割と試行錯誤しました．
雨雲レーダーのページの画像はそのまま電子ペーパに表示すると雨の強さが分かりにくいので，色を変換しています．
また，天気予報のアイコンは Yahoo のものをそのまま表示すると小さすぎるので，あまり破綻がないように手間をかけて拡大処理してます．
