#!/usr/bin/env python3

import json
import logging
import pathlib

import flask
import my_lib.config
import my_lib.flask_util
import my_lib.webapp.config

import metrics.collector

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

        # メトリクス分析器を初期化
        analyzer = metrics.collector.MetricsAnalyzer(db_path)

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
        logging.error(f"メトリクス表示の生成エラー: {e}")
        return flask.Response(f"エラー: {str(e)}", mimetype="text/plain", status=500)


@blueprint.route("/favicon.ico", methods=["GET"])
def favicon():
    """favicon.icoを返す"""
    try:
        favicon_path = pathlib.Path(__file__).parent.parent.parent.parent / "react" / "dist" / "favicon.ico"
        if favicon_path.exists():
            return flask.send_file(favicon_path, mimetype="image/x-icon")
        else:
            return flask.Response("", status=404)
    except Exception as e:
        logging.error(f"favicon取得エラー: {e}")
        return flask.Response("", status=500)


def generate_metrics_html(
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
        .metrics-card {{ margin-bottom: 1.5rem; }}
        .stat-number {{ font-size: 2rem; font-weight: bold; }}
        .chart-container {{ position: relative; height: 450px; margin: 1rem 0; }}
        .chart-legend {{ margin-bottom: 1rem; }}
        .legend-item {{ display: inline-block; margin-right: 1rem; margin-bottom: 0.5rem; }}
        .legend-color {{ display: inline-block; width: 20px; height: 3px; margin-right: 0.5rem; vertical-align: middle; }}
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
        .hourly-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
        .japanese-font {{ font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans CJK JP", "Yu Gothic", sans-serif; }}
    </style>
</head>
<body class="japanese-font">
    <div class="container is-fluid">
        <section class="section">
            <div class="container">
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
        generateBoxplotCharts();
        generateTrendsCharts();
        generatePanelTrendsCharts();

        """
        + page_js.generate_chart_javascript()
        + """
    </script>
</html>
    """
    )

    return html


def generate_alerts_section(alerts):
    """アラートセクションのHTML生成。"""
    if not alerts:
        return """
        <div class="notification is-success">
            <span class="icon"><i class="fas fa-check-circle"></i></span>
            パフォーマンスアラートは検出されていません。
        </div>
        """

    alerts_html = '<div class="section"><h2 class="title is-4"><span class="icon"><i class="fas fa-exclamation-triangle"></i></span> パフォーマンスアラート</h2>'

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
        <h2 class="title is-4"><span class="icon"><i class="fas fa-chart-bar"></i></span> 基本統計（過去100日間）</h2>

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
                                    <p class="stat-number has-text-primary">{draw_panel.get("total_operations", 0):,}</p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">エラー回数</p>
                                    <p class="stat-number has-text-danger">{draw_panel.get("error_count", 0):,}</p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">平均処理時間（秒）</p>
                                    <p class="stat-number has-text-info">{draw_panel.get("avg_elapsed_time", 0):.2f}</p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">最大処理時間（秒）</p>
                                    <p class="stat-number has-text-warning">{draw_panel.get("max_elapsed_time", 0):.2f}</p>
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
                                    <p class="stat-number has-text-primary">{display_image.get("total_operations", 0):,}</p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">失敗回数</p>
                                    <p class="stat-number has-text-danger">{display_image.get("failure_count", 0):,}</p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">平均処理時間（秒）</p>
                                    <p class="stat-number has-text-info">{display_image.get("avg_elapsed_time", 0):.2f}</p>
                                </div>
                            </div>
                            <div class="column is-half">
                                <div class="has-text-centered">
                                    <p class="heading">最大処理時間（秒）</p>
                                    <p class="stat-number has-text-warning">{display_image.get("max_elapsed_time", 0):.2f}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def generate_hourly_patterns_section(hourly_patterns):
    """時間別パターンセクションのHTML生成。"""
    return """
    <div class="section">
        <h2 class="title is-4"><span class="icon"><i class="fas fa-clock"></i></span> 時間別パフォーマンスパターン</h2>

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


def generate_trends_section(trends):
    """パフォーマンス推移セクションのHTML生成。"""
    return """
    <div class="section">
        <h2 class="title is-4"><span class="icon"><i class="fas fa-trending-up"></i></span> パフォーマンス推移</h2>

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


def generate_anomalies_section(anomalies, performance_stats):
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
            <p>機械学習の<strong>Isolation Forest</strong>アルゴリズムを使用して、以下の要素から異常なパターンを検知しています：</p>
            <ul>
                <li><strong>処理時間</strong>：通常より極端に長い、または短い処理時間</li>
                <li><strong>曜日パターン</strong>：通常の曜日パターンと異なる実行</li>
                <li><strong>エラー発生</strong>：エラーの有無も考慮要素</li>
            </ul>
            <p>例：異常に長い処理時間、平日と休日の処理パターンの違い、エラーを伴う異常な処理時間など</p>
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
            hour = anomaly.get("hour", 0)
            error_code = anomaly.get("error_code", 0)

            # 異常の種類を分析（統計情報を使用）
            dp_stats = performance_stats.get("draw_panel", {})
            avg_time = dp_stats.get("avg_time", 0)
            std_time = dp_stats.get("std_time", 0)

            anomaly_reasons = []
            reason_tooltips = []

            anomaly_details = []

            if elapsed_time > 60:  # 1分以上
                anomaly_reasons.append('<span class="tag is-small is-warning">長時間処理</span>')
                if std_time > 0:
                    sigma_deviation = abs(elapsed_time - avg_time) / std_time
                    anomaly_details.append(f"平均値から<strong>{sigma_deviation:.1f}σ</strong>乖離")
                anomaly_details.append(f"実行時間: <strong>{elapsed_time:.2f}秒</strong>")
            elif elapsed_time < 1:  # 1秒未満
                anomaly_reasons.append('<span class="tag is-small is-info">短時間処理</span>')
                if std_time > 0:
                    sigma_deviation = abs(elapsed_time - avg_time) / std_time
                    anomaly_details.append(f"平均値から<strong>{sigma_deviation:.1f}σ</strong>乖離")
                anomaly_details.append(f"実行時間: <strong>{elapsed_time:.2f}秒</strong>")

            if error_code > 0:
                anomaly_reasons.append('<span class="tag is-small is-danger">エラー発生</span>')
                anomaly_details.append(f"エラーコード: <strong>{error_code}</strong>")

            if not anomaly_reasons:
                anomaly_reasons.append('<span class="tag is-small is-light">パターン異常</span>')
                if std_time > 0:
                    sigma_deviation = abs(elapsed_time - avg_time) / std_time
                    anomaly_details.append(f"平均値から<strong>{sigma_deviation:.1f}σ</strong>乖離")
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
            except:
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

            <div class="column">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">表示実行処理の異常</p>
                    </div>
                    <div class="card-content">
                        <div class="columns">
                            <div class="column has-text-centered">
                                <p class="heading">検出された異常数</p>
                                <p class="stat-number has-text-warning">{}</p>
                            </div>
                            <div class="column has-text-centered">
                                <p class="heading">異常率</p>
                                <p class="stat-number has-text-warning">{:.2f}%</p>
                            </div>
                        </div>
    """.format(di_anomaly_count, di_anomaly_rate)

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
            hour = anomaly.get("hour", 0)
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
                    sigma_deviation = abs(elapsed_time - avg_time_di) / std_time_di
                    anomaly_details.append(f"平均値から<strong>{sigma_deviation:.1f}σ</strong>乖離")
                anomaly_details.append(f"実行時間: <strong>{elapsed_time:.2f}秒</strong>")
            elif elapsed_time < 5:  # 5秒未満
                anomaly_reasons.append('<span class="tag is-small is-info">短時間処理</span>')
                if std_time_di > 0:
                    sigma_deviation = abs(elapsed_time - avg_time_di) / std_time_di
                    anomaly_details.append(f"平均値から<strong>{sigma_deviation:.1f}σ</strong>乖離")
                anomaly_details.append(f"実行時間: <strong>{elapsed_time:.2f}秒</strong>")

            if not success:
                anomaly_reasons.append('<span class="tag is-small is-danger">実行失敗</span>')
                anomaly_details.append("実行結果: <strong>失敗</strong>")

            if not anomaly_reasons:
                anomaly_reasons.append('<span class="tag is-small is-light">パターン異常</span>')
                if std_time_di > 0:
                    sigma_deviation = abs(elapsed_time - avg_time_di) / std_time_di
                    anomaly_details.append(f"平均値から<strong>{sigma_deviation:.1f}σ</strong>乖離")
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
            except:
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


def generate_panel_trends_section(panel_trends):
    """パネル別処理時間推移セクションのHTML生成。"""
    return """
    <div class="section">
        <h2 class="title is-4"><span class="icon"><i class="fas fa-puzzle-piece"></i></span> パネル別処理時間推移</h2>
        <p class="subtitle is-6">各パネルの処理時間分布を箱ヒゲ図で表示（縦軸スケール統一）</p>

        <div class="columns is-multiline" id="panelTrendsContainer">
            <!-- パネル別箱ヒゲ図がJavaScriptで動的に生成される -->
        </div>
    </div>
    """
