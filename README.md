# E-Ink Weather Panel

## 概要

電子ペーパディスプレイに、Raspberry Pi を通じて下記の情報を表示するためのスクリプトです。

-   天気予報
-   各種センサーの情報

## デモ

表示サンプルは下記になります。

![表示サンプル](img/example.png)

実際にリアルタイムに画像を生成する様を下記で確認いただけます。

https://weather-panel-webapp-demo.kubernetes.green-rabbit.net/weather_panel/

## 詳細

大きく次の処理を行います。

-   Yahoo から天気予報の情報を取得
-   気象庁のページから雨雲画像を取得
-   Influx DB からセンサー情報を取得
-   センサ情報を Matplotlib で描画
-   夜間、照度に応じてライトのアイコンを描画
-   Raspberry Pi にログインして、フレームバッファに描画

## 設定

同封されている `config.example.yaml` を `config.yaml` に名前変更して，お手元の環境に合わせて書き換えてください。
また、表示に使う Raspberry Pi のホスト名を `compose.yaml` の RASP_HOSTNAME にて指定します。

下記に含まれる Influx DB からセンサー情報を取得する関数 `fetch_data` は、
お手元の環境に合わせて修正が必要かもしれません。

-   `src/weather_display/sensor_graph.py`
-   `src/weather_display/power_graph.py`

## 準備
nn
### Raspberry Pi

ディプレイと接続する Rapsberry Pi では以下の準備を行なっておきます。

#### パッケージののインストール

```bash:bash
apt-get install -y fbi
```

#### 出力解像度設定

電子ペーパデバイスの解像度で HDMI 出力を行うため、 `/boot/firmware/config.txt` に設定を記載します。

##### BOOX Mira Pro を使う場合

解像度が 3200x1800 なので、次のようにします。

```text
framebuffer_width=3200
framebuffer_height=1800
max_framebuffer_width=3200
max_framebuffer_height=1800
hdmi_group=2
hdmi_mode=87
hdmi_timings=3200 1 48 32 80 1800 1 3 5 54 0 0 0 10 0 183422400 3
```

#### BOOX Mira 33 を使う場合

解像度が 2200x1650 なので、次のようにします。

```text
framebuffer_width=2200
framebuffer_height=1650
max_framebuffer_width=2200
max_framebuffer_height=1650
hdmi_group=2
hdmi_mode=87
hdmi_timings=2200 1 48 32 80 1650 1 3 5 54 0 0 0 10 0 160000000 1
```

#### 画面の消灯禁止

`/boot/firmware/cmdline.txt` に `consoleblank=0` を追記して画面が消灯しないようにします。

### 描画用 SSH 公開鍵のコピー

画面表示を行う `display_image.py` は、描画のために Raspberry Pi にログインする際に、`key/panel.id_rsa` を使います。
そのため、次のようにして秘密鍵を Raspberry Pi にコピーしておきます。

```bash
ssh-copy-id -i key/panel.id_rsa.pub ubuntu@"Raspberry Pi のホスト名"
```

### ホスト側

#### パッケージのインストール

```bash:bash
sudo apt install npm docker
```

## 実行 (Docker 使用)

```bash:bash
cd react
npm ci
npm run build
cd -
docker compose run --build --rm weather_panel
```

## 実行 (Docker 不使用)

[Rye](https://rye.astral.sh/) がインストールされた環境であれば，
下記のようにして Docker を使わずに実行できます．

```bash:bash
rye sync
env RASP_HOSTNAME="Raspberry Pi のホスト名" rye run python src/display_image.py
```

## Kubernetes で動かす場合

Kubernetes で実行するため設定ファイルが `kubernetes/e-ink_weater_panel.yaml` に入っていますので，
適宜カスタマイズして使っていただければと思います。


## テスト結果

-   https://kimata.github.io/e-ink_weather_panel/
-   https://kimata.github.io/e-ink_weather_panel/coverage/

# ライセンス

Apache License Version 2.0 を適用します。
