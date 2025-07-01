#!/usr/bin/env python3

import io
import json
import logging
import pathlib

import flask
import my_lib.config
import my_lib.flask_util
import my_lib.webapp.config
from PIL import Image, ImageDraw

import weather_display.metrics.collector

from . import page_js

blueprint = flask.Blueprint("metrics", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)


@blueprint.route("/api/metrics", methods=["GET"])
@my_lib.flask_util.gzipped
def metrics_view():
    # NOTE: @gzipped をつけた場合、キャッシュ用のヘッダを付与しているので、
    # 無効化する。
    flask.g.disable_cache = True

    try:
        # 設定ファイルからデータベースパスを取得
        config_file = flask.current_app.config.get("CONFIG_FILE_NORMAL", "config.yaml")
        config = my_lib.config.load(config_file, pathlib.Path("config.schema"))

        # 設定からデータベースパスを取得
        db_path = config.get("metrics", {}).get("data", "data/metrics.db")

        # データベースファイルの存在確認
        if not pathlib.Path(db_path).exists():
            return flask.Response(
                f"<html><body><h1>メトリクスデータベースが見つかりません</h1>"
                f"<p>データベースファイル: {db_path}</p>"
                f"<p>システムが十分に動作してからメトリクスが生成されます。</p></body></html>",
                mimetype="text/html",
                status=503,
            )

        # メトリクス分析器を初期化
        analyzer = weather_display.metrics.collector.MetricsAnalyzer(db_path)

        # すべてのメトリクスデータを収集
        basic_stats = analyzer.get_basic_statistics(days=100)
        hourly_patterns = analyzer.get_hourly_patterns(days=100)
        anomalies = analyzer.detect_anomalies(days=100)
        trends = analyzer.get_performance_trends(days=100)
        alerts = analyzer.check_performance_alerts()
        panel_trends = analyzer.get_panel_performance_trends(days=100)
        performance_stats = analyzer.get_performance_statistics(days=100)

        # HTMLを生成
        html_content = generate_metrics_html(
            basic_stats, hourly_patterns, anomalies, trends, alerts, panel_trends, performance_stats
        )

        return flask.Response(html_content, mimetype="text/html")

    except Exception as e:
        logging.exception("メトリクス表示の生成エラー")
        return flask.Response(f"エラー: {e!s}", mimetype="text/plain", status=500)


def generate_metrics_icon():
    """メトリクス用のアイコンを動的生成（アンチエイリアス対応）"""
    # アンチエイリアスのため4倍サイズで描画してから縮小
    scale = 4
    size = 32
    large_size = size * scale

    # 大きなサイズで描画
    img = Image.new("RGBA", (large_size, large_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 背景円（メトリクスらしい青色）
    margin = 2 * scale
    draw.ellipse(
        [margin, margin, large_size - margin, large_size - margin],
        fill=(52, 152, 219, 255),
        outline=(41, 128, 185, 255),
        width=2 * scale,
    )

    # グラフっぽい線を描画（座標を4倍に拡大）
    points = [
        (8 * scale, 20 * scale),
        (12 * scale, 16 * scale),
        (16 * scale, 12 * scale),
        (20 * scale, 14 * scale),
        (24 * scale, 10 * scale),
    ]

    # 折れ線グラフ
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=(255, 255, 255, 255), width=2 * scale)

    # データポイント
    point_size = 1 * scale
    for point in points:
        draw.ellipse(
            [point[0] - point_size, point[1] - point_size, point[0] + point_size, point[1] + point_size],
            fill=(255, 255, 255, 255),
        )

    # 32x32に縮小してアンチエイリアス効果を得る
    return img.resize((size, size), Image.LANCZOS)


@blueprint.route("/favicon.ico", methods=["GET"])
def favicon():
    """動的生成されたメトリクス用favicon.icoを返す"""
    try:
        # メトリクスアイコンを生成
        img = generate_metrics_icon()

        # ICO形式で出力
        output = io.BytesIO()
        img.save(output, format="ICO", sizes=[(32, 32)])
        output.seek(0)

        return flask.Response(
            output.getvalue(),
            mimetype="image/x-icon",
            headers={
                "Cache-Control": "public, max-age=3600",  # 1時間キャッシュ
                "Content-Type": "image/x-icon",
            },
        )
    except Exception:
        logging.exception("favicon生成エラー")
        return flask.Response("", status=500)


def generate_metrics_html(  # noqa: PLR0913
    basic_stats, hourly_patterns, anomalies, trends, alerts, panel_trends, performance_stats
):
    """Bulma CSSを使用した包括的なメトリクスHTMLを生成。"""
    # JavaScript チャート用にデータをJSONに変換
    hourly_data_json = json.dumps(hourly_patterns)
    trends_data_json = json.dumps(trends)
    anomalies_data_json = json.dumps(anomalies)
    panel_trends_data_json = json.dumps(panel_trends)

    # URL_PREFIXを取得してfaviconパスを構築
    favicon_path = f"{my_lib.webapp.config.URL_PREFIX}/favicon.ico"

    html = (
        f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>天気パネル メトリクス ダッシュボード</title>
    <link rel="icon" type="image/x-icon" href="{favicon_path}">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@sgratzl/chartjs-chart-boxplot"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .metrics-card {{ margin-bottom: 1rem; }}
        @media (max-width: 768px) {{
            .metrics-card {{ margin-bottom: 0.75rem; }}
        }}
        .stat-number {{ font-size: 2rem; font-weight: bold; }}
        .chart-container {{ position: relative; height: 350px; margin: 0.5rem 0; }}
        @media (max-width: 768px) {{
            .chart-container {{ height: 300px; margin: 0.25rem 0; }}
            .container.is-fluid {{ padding: 0.25rem !important; }}
            .section {{ padding: 0.5rem 0.25rem !important; }}
            .card {{ margin-bottom: 1rem !important; }}
            .columns {{ margin: 0 !important; }}
            .column {{ padding: 0.25rem !important; }}
        }}
        .chart-legend {{ margin-bottom: 1rem; }}
        .legend-item {{ display: inline-block; margin-right: 1rem; margin-bottom: 0.5rem; }}
        .legend-color {{
            display: inline-block; width: 20px; height: 3px;
            margin-right: 0.5rem; vertical-align: middle;
        }}
        .legend-dashed {{ border-top: 3px dashed; height: 0; }}
        .legend-dotted {{ border-top: 3px dotted; height: 0; }}
        .anomaly-item {{
            margin-bottom: 1rem;
            padding: 0.75rem;
            background-color: #fafafa;
            border-radius: 6px;
            border-left: 4px solid #ffdd57;
        }}
        .alert-item {{ margin-bottom: 1rem; }}
        .hourly-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }}
        .japanese-font {{
            font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN",
                         "Noto Sans CJK JP", "Yu Gothic", sans-serif;
        }}
    </style>
</head>
<body class="japanese-font">
    <div class="container is-fluid" style="padding: 0.5rem;">
        <section class="section" style="padding: 1rem 0.5rem;">
            <div class="container" style="max-width: 100%; padding: 0;">
                <h1 class="title is-2 has-text-centered">
                    <span class="icon is-large"><i class="fas fa-chart-line"></i></span>
                    天気パネル メトリクス ダッシュボード
                </h1>
                <p class="subtitle has-text-centered">過去100日間のパフォーマンス監視と異常検知</p>

                <!-- アラート -->
                {generate_alerts_section(alerts)}

                <!-- 基本統計 -->
                {generate_basic_stats_section(basic_stats)}

                <!-- 時間別パターン -->
                {generate_hourly_patterns_section(hourly_patterns)}

                <!-- 表示タイミング -->
                {generate_diff_sec_section()}

                <!-- パフォーマンス推移 -->
                {generate_trends_section(trends)}

                <!-- パネル別処理時間推移 -->
                {generate_panel_trends_section(panel_trends)}

                <!-- 異常検知 -->
                {generate_anomalies_section(anomalies, performance_stats)}
            </div>
        </section>
    </div>

    <script>
        const hourlyData = """
        + hourly_data_json
        + """;
        const trendsData = """
        + trends_data_json
        + """;
        const anomaliesData = """
        + anomalies_data_json
        + """;
        const panelTrendsData = """
        + panel_trends_data_json
        + """;

        // チャート生成
        generateHourlyCharts();
        generateDiffSecCharts();
        generateBoxplotCharts();
        generateTrendsCharts();
        generatePanelTrendsCharts();
        generatePanelTimeSeriesChart();

        """
        + page_js.generate_chart_javascript()
        + """
    </script>
</html>
    """
    )

    return html  # noqa: RET504


def generate_alerts_section(alerts):
    """アラートセクションのHTML生成。"""
    if not alerts:
        return """
        <div class="notification is-success">
            <span class="icon"><i class="fas fa-check-circle"></i></span>
            パフォーマンスアラートは検出されていません。
        </div>
        """

    alerts_html = (
        '<div class="section"><h2 class="title is-4">'
        '<span class="icon"><i class="fas fa-exclamation-triangle"></i></span> '
        "パフォーマンスアラート</h2>"
    )

    for alert in alerts:
        severity_class = {"critical": "is-danger", "warning": "is-warning", "info": "is-info"}.get(
            alert.get("severity", "info"), "is-info"
        )

        alert_type = alert.get("type", "アラート").replace("_", " ")
        alert_message = alert.get("message", "メッセージなし")

        alerts_html += f"""
        <div class="notification {severity_class} alert-item">
            <strong>{alert_type}:</strong> {alert_message}
        </div>
        """

    alerts_html += "</div>"
    return alerts_html


def generate_basic_stats_section(basic_stats):
    """基本統計セクションのHTML生成。"""
    draw_panel = basic_stats.get("draw_panel", {})
    display_image = basic_stats.get("display_image", {})

    return f"""
    <div class="section">
        <h2 class="title is-4">
            <span class="icon"><i class="fas fa-chart-bar"></i></span>
            基本統計（過去100日間）
        </h2>

        <div class="columns">
            <div class="column">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">画像生成処理</p>
                    </div>
                    <div class="card-content">
                        <div class="columns is-multiline">
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">総実行回数</p>
                                    <p class="stat-number has-text-primary">
                                    {draw_panel.get("total_operations", 0):,}
                                </p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">エラー回数</p>
                                    <p class="stat-number has-text-danger">
                                    {draw_panel.get("error_count", 0):,}
                                </p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">平均処理時間（秒）</p>
                                    <p class="stat-number has-text-info">
                                    {draw_panel.get("avg_elapsed_time", 0):.2f}
                                </p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">最大処理時間（秒）</p>
                                    <p class="stat-number has-text-warning">
                                    {draw_panel.get("max_elapsed_time", 0):.2f}
                                </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="column">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">表示実行処理</p>
                    </div>
                    <div class="card-content">
                        <div class="columns is-multiline">
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">総実行回数</p>
                                    <p class="stat-number has-text-primary">
                                    {display_image.get("total_operations", 0):,}
                                </p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">失敗回数</p>
                                    <p class="stat-number has-text-danger">
                                    {display_image.get("failure_count", 0):,}
                                </p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">平均処理時間（秒）</p>
                                    <p class="stat-number has-text-info">
                                    {display_image.get("avg_elapsed_time", 0):.2f}
                                </p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">最大処理時間（秒）</p>
                                    <p class="stat-number has-text-warning">
                                    {display_image.get("max_elapsed_time", 0):.2f}
                                </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def generate_hourly_patterns_section(hourly_patterns):  # noqa: ARG001
    """時間別パターンセクションのHTML生成。"""
    return """
    <div class="section">
        <h2 class="title is-4">
            <span class="icon"><i class="fas fa-clock"></i></span>
            時間別パフォーマンスパターン
        </h2>

        <div class="columns">
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">画像生成処理 - 時間別パフォーマンス</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="drawPanelHourlyChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">画像生成処理 - 時間別分布（箱ひげ図）</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="drawPanelBoxplotChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="columns">
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">表示実行処理 - 時間別パフォーマンス</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="displayImageHourlyChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">表示実行処理 - 時間別分布（箱ひげ図）</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="displayImageBoxplotChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def generate_trends_section(trends):  # noqa: ARG001
    """パフォーマンス推移セクションのHTML生成。"""
    return """
    <div class="section">
        <h2 class="title is-4">
            <span class="icon"><i class="fas fa-trending-up"></i></span>
            パフォーマンス推移
        </h2>

        <div class="columns">
            <div class="column">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">画像生成処理 - 日別推移</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="drawPanelTrendsChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="columns">
            <div class="column">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">表示実行処理 - 日別推移</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="displayImageTrendsChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def generate_anomalies_section(anomalies, performance_stats):  # noqa: C901, PLR0912, PLR0915
    """異常検知セクションのHTML生成。"""
    draw_panel_anomalies = anomalies.get("draw_panel", {})
    display_image_anomalies = anomalies.get("display_image", {})

    # 異常の表示用フォーマット
    dp_anomaly_count = draw_panel_anomalies.get("anomalies_detected", 0)
    di_anomaly_count = display_image_anomalies.get("anomalies_detected", 0)
    dp_anomaly_rate = draw_panel_anomalies.get("anomaly_rate", 0) * 100
    di_anomaly_rate = display_image_anomalies.get("anomaly_rate", 0) * 100

    anomalies_html = f"""
    <div class="section">
        <h2 class="title is-4"><span class="icon"><i class="fas fa-search"></i></span> 異常検知</h2>

        <div class="notification is-info is-light">
            <p><strong>異常検知について：</strong></p>
            <p>機械学習の<strong>Isolation Forest</strong>アルゴリズムを使用して、
               以下の要素から異常なパターンを検知しています：</p>
            <ul>
                <li><strong>処理時間</strong>：通常より極端に長い、または短い処理時間</li>
                <li><strong>エラー発生</strong>：エラーの有無も考慮要素</li>
            </ul>
            <p>例：異常に長い処理時間、エラーを伴う異常な処理時間など</p>
        </div>

        <div class="columns">
            <div class="column">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">画像生成処理の異常</p>
                    </div>
                    <div class="card-content">
                        <div class="columns">
                            <div class="column has-text-centered">
                                <p class="heading">検出された異常数</p>
                                <p class="stat-number has-text-warning">{dp_anomaly_count}</p>
                            </div>
                            <div class="column has-text-centered">
                                <p class="heading">異常率</p>
                                <p class="stat-number has-text-warning">{dp_anomaly_rate:.2f}%</p>
                            </div>
                        </div>
    """

    # 個別の異常がある場合は表示
    if draw_panel_anomalies.get("anomalies"):
        anomalies_html += '<div class="content"><h5>最近の異常:</h5>'
        # 新しいもの順でソート
        sorted_anomalies = sorted(
            draw_panel_anomalies["anomalies"], key=lambda x: x.get("timestamp", ""), reverse=True
        )
        for anomaly in sorted_anomalies[:20]:  # 最新20件を表示
            timestamp_str = anomaly.get("timestamp", "不明")
            elapsed_time = anomaly.get("elapsed_time", 0)
            # hour = anomaly.get("hour", 0)  # unused
            error_code = anomaly.get("error_code", 0)

            # 異常の種類を分析（統計情報を使用）
            dp_stats = performance_stats.get("draw_panel", {})
            avg_time = dp_stats.get("avg_time", 0)
            std_time = dp_stats.get("std_time", 0)

            anomaly_reasons = []

            anomaly_details = []

            if elapsed_time > 60:  # 1分以上
                anomaly_reasons.append('<span class="tag is-small is-warning">長時間処理</span>')
                if std_time > 0:
                    sigma_deviation = (elapsed_time - avg_time) / std_time
                    sign = "+" if sigma_deviation >= 0 else ""
                    anomaly_details.append(f"平均値から<strong>{sign}{sigma_deviation:.1f}σ</strong>乖離")
                anomaly_details.append(f"実行時間: <strong>{elapsed_time:.2f}秒</strong>")
            elif elapsed_time < 1:  # 1秒未満
                anomaly_reasons.append('<span class="tag is-small is-info">短時間処理</span>')
                if std_time > 0:
                    sigma_deviation = (elapsed_time - avg_time) / std_time
                    sign = "+" if sigma_deviation >= 0 else ""
                    anomaly_details.append(f"平均値から<strong>{sign}{sigma_deviation:.1f}σ</strong>乖離")
                anomaly_details.append(f"実行時間: <strong>{elapsed_time:.2f}秒</strong>")

            if error_code > 0:
                anomaly_reasons.append('<span class="tag is-small is-danger">エラー発生</span>')
                anomaly_details.append(f"エラーコード: <strong>{error_code}</strong>")

            if not anomaly_reasons:
                anomaly_reasons.append('<span class="tag is-small is-light">パターン異常</span>')
                if std_time > 0:
                    sigma_deviation = (elapsed_time - avg_time) / std_time
                    sign = "+" if sigma_deviation >= 0 else ""
                    anomaly_details.append(f"平均値から<strong>{sign}{sigma_deviation:.1f}σ</strong>乖離")
                anomaly_details.append(f"実行時間: <strong>{elapsed_time:.2f}秒</strong>")

            # 日時を自然な日本語形式に変換
            try:
                import datetime

                if timestamp_str != "不明":
                    # ISO形式の日時をパース
                    dt = datetime.datetime.fromisoformat(timestamp_str.replace("+09:00", "+09:00"))
                    # 日本語形式に変換 (年も含める)
                    formatted_time = dt.strftime("%Y年%m月%d日 %H時%M分")

                    # 経過時間を計算
                    now = datetime.datetime.now(dt.tzinfo)
                    elapsed_delta = now - dt

                    if elapsed_delta.days > 0:
                        elapsed_text = f"{elapsed_delta.days}日前"
                    elif elapsed_delta.seconds // 3600 > 0:
                        hours = elapsed_delta.seconds // 3600
                        elapsed_text = f"{hours}時間前"
                    elif elapsed_delta.seconds // 60 > 0:
                        minutes = elapsed_delta.seconds // 60
                        elapsed_text = f"{minutes}分前"
                    else:
                        elapsed_text = "たった今"

                    formatted_time += f" ({elapsed_text})"
                else:
                    formatted_time = "不明"
            except Exception:
                formatted_time = timestamp_str

            reason_tags = " ".join(anomaly_reasons)
            detail_text = " | ".join(anomaly_details)
            anomalies_html += f"""<div class="anomaly-item">
                <div class="mb-2">
                    <span class="tag is-warning">{formatted_time}</span>
                    {reason_tags}
                </div>
                <div class="pl-3 has-text-grey-dark" style="font-size: 0.9rem;">
                    {detail_text}
                </div>
            </div>"""
        anomalies_html += "</div>"

    anomalies_html += f"""
                    </div>
                </div>
            </div>

            <div class="column">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">表示実行処理の異常</p>
                    </div>
                    <div class="card-content">
                        <div class="columns">
                            <div class="column has-text-centered">
                                <p class="heading">検出された異常数</p>
                                <p class="stat-number has-text-warning">{di_anomaly_count}</p>
                            </div>
                            <div class="column has-text-centered">
                                <p class="heading">異常率</p>
                                <p class="stat-number has-text-warning">{di_anomaly_rate:.2f}%</p>
                            </div>
                        </div>
    """

    # 個別の異常がある場合は表示
    if display_image_anomalies.get("anomalies"):
        anomalies_html += '<div class="content"><h5>最近の異常:</h5>'
        # 新しいもの順でソート
        sorted_anomalies = sorted(
            display_image_anomalies["anomalies"], key=lambda x: x.get("timestamp", ""), reverse=True
        )
        for anomaly in sorted_anomalies[:20]:  # 最新20件を表示
            timestamp_str = anomaly.get("timestamp", "不明")
            elapsed_time = anomaly.get("elapsed_time", 0)
            # hour = anomaly.get("hour", 0)  # unused
            success = anomaly.get("success", True)

            # 異常の種類を分析（表示実行処理用、統計情報を使用）
            di_stats = performance_stats.get("display_image", {})
            avg_time_di = di_stats.get("avg_time", 0)
            std_time_di = di_stats.get("std_time", 0)

            anomaly_reasons = []

            anomaly_details = []

            if elapsed_time > 120:  # 2分以上
                anomaly_reasons.append('<span class="tag is-small is-warning">長時間処理</span>')
                if std_time_di > 0:
                    sigma_deviation = (elapsed_time - avg_time_di) / std_time_di
                    sign = "+" if sigma_deviation >= 0 else ""
                    anomaly_details.append(f"平均値から<strong>{sign}{sigma_deviation:.1f}σ</strong>乖離")
                anomaly_details.append(f"実行時間: <strong>{elapsed_time:.2f}秒</strong>")
            elif elapsed_time < 5:  # 5秒未満
                anomaly_reasons.append('<span class="tag is-small is-info">短時間処理</span>')
                if std_time_di > 0:
                    sigma_deviation = (elapsed_time - avg_time_di) / std_time_di
                    sign = "+" if sigma_deviation >= 0 else ""
                    anomaly_details.append(f"平均値から<strong>{sign}{sigma_deviation:.1f}σ</strong>乖離")
                anomaly_details.append(f"実行時間: <strong>{elapsed_time:.2f}秒</strong>")

            if not success:
                anomaly_reasons.append('<span class="tag is-small is-danger">実行失敗</span>')
                anomaly_details.append("実行結果: <strong>失敗</strong>")

            if not anomaly_reasons:
                anomaly_reasons.append('<span class="tag is-small is-light">パターン異常</span>')
                if std_time_di > 0:
                    sigma_deviation = (elapsed_time - avg_time_di) / std_time_di
                    sign = "+" if sigma_deviation >= 0 else ""
                    anomaly_details.append(f"平均値から<strong>{sign}{sigma_deviation:.1f}σ</strong>乖離")
                anomaly_details.append(f"実行時間: <strong>{elapsed_time:.2f}秒</strong>")

            # 日時を自然な日本語形式に変換
            try:
                import datetime

                if timestamp_str != "不明":
                    # ISO形式の日時をパース
                    dt = datetime.datetime.fromisoformat(timestamp_str.replace("+09:00", "+09:00"))
                    # 日本語形式に変換 (年も含める)
                    formatted_time = dt.strftime("%Y年%m月%d日 %H時%M分")

                    # 経過時間を計算
                    now = datetime.datetime.now(dt.tzinfo)
                    elapsed_delta = now - dt

                    if elapsed_delta.days > 0:
                        elapsed_text = f"{elapsed_delta.days}日前"
                    elif elapsed_delta.seconds // 3600 > 0:
                        hours = elapsed_delta.seconds // 3600
                        elapsed_text = f"{hours}時間前"
                    elif elapsed_delta.seconds // 60 > 0:
                        minutes = elapsed_delta.seconds // 60
                        elapsed_text = f"{minutes}分前"
                    else:
                        elapsed_text = "たった今"

                    formatted_time += f" ({elapsed_text})"
                else:
                    formatted_time = "不明"
            except Exception:
                formatted_time = timestamp_str

            reason_tags = " ".join(anomaly_reasons)
            detail_text = " | ".join(anomaly_details)
            anomalies_html += f"""<div class="anomaly-item">
                <div class="mb-2">
                    <span class="tag is-warning">{formatted_time}</span>
                    {reason_tags}
                </div>
                <div class="pl-3 has-text-grey-dark" style="font-size: 0.9rem;">
                    {detail_text}
                </div>
            </div>"""
        anomalies_html += "</div>"

    anomalies_html += """
                    </div>
                </div>
            </div>
        </div>
    </div>
    """

    return anomalies_html


def generate_diff_sec_section():
    """表示タイミングセクションのHTML生成。"""
    return """
    <div class="section">
        <h2 class="title is-4"><span class="icon"><i class="fas fa-clock"></i></span> 表示タイミング</h2>
        <p class="subtitle is-6">表示実行時の分単位での秒数の偏差（0秒が理想的なタイミング）</p>

        <div class="columns">
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">表示タイミング - 時間別パフォーマンス</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="diffSecHourlyChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="column is-half">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">表示タイミング - 時間別分布（箱ひげ図）</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="diffSecBoxplotChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def generate_panel_trends_section(panel_trends):  # noqa: ARG001
    """パネル別処理時間推移セクションのHTML生成。"""
    return """
    <div class="section">
        <h2 class="title is-4">
            <span class="icon"><i class="fas fa-puzzle-piece"></i></span>
            パネル別処理時間ヒストグラム
        </h2>
        <p class="subtitle is-6">各パネルの処理時間分布をヒストグラムで表示（横軸：時間、縦軸：割合）</p>

        <div class="columns is-multiline is-variable is-1" id="panelTrendsContainer"
             style="justify-content: flex-start;">
            <!-- パネル別ヒストグラムがJavaScriptで動的に生成される -->
        </div>
    </div>

    <div class="section">
        <h2 class="title is-4">
            <span class="icon"><i class="fas fa-chart-line"></i></span>
            パネル別処理時間推移
        </h2>
        <p class="subtitle is-6">各パネルの処理時間の時系列推移グラフ（時間軸での処理時間変化）</p>

        <div class="columns">
            <div class="column">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">パネル別処理時間推移</p>
                    </div>
                    <div class="card-content">
                        <div class="chart-container">
                            <canvas id="panelTimeSeriesChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
