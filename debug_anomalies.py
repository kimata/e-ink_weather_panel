#!/usr/bin/env python3

import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent / "src"))

from weather_display.metrics.collector import MetricsAnalyzer
import datetime

def debug_anomaly_detection():
    """異常検知の詳細を調査"""
    
    # メトリクス分析器を初期化
    analyzer = MetricsAnalyzer("data/metrics.db")
    
    # 異常検知を実行
    anomalies = analyzer.detect_anomalies(days=100)
    
    print("=== 異常検知結果 ===")
    
    # 画像生成処理の異常
    draw_panel_anomalies = anomalies.get("draw_panel", {})
    print(f"画像生成処理の異常数: {draw_panel_anomalies.get('anomalies_detected', 0)}")
    
    anomaly_list = draw_panel_anomalies.get("anomalies", [])
    
    print("\n=== 検出された異常の詳細 ===")
    for i, anomaly in enumerate(anomaly_list[:10]):  # 最初の10件
        print(f"異常 {i+1}:")
        print(f"  ID: {anomaly.get('id')}")
        print(f"  タイムスタンプ: {anomaly.get('timestamp')}")
        print(f"  処理時間: {anomaly.get('elapsed_time')}秒")  # ← ここが問題の可能性
        print(f"  時間: {anomaly.get('hour')}")
        print(f"  エラーコード: {anomaly.get('error_code')}")
        print("-" * 30)
    
    # 実際のデータベースから該当するIDのレコードを確認
    if anomaly_list:
        print("\n=== データベースでの実際の値 ===")
        with analyzer._get_connection() as conn:
            cursor = conn.cursor()
            
            # 異常として検出されたIDの実際のデータを取得
            for anomaly in anomaly_list[:5]:
                anomaly_id = anomaly.get('id')
                cursor.execute("""
                    SELECT id, timestamp, total_elapsed_time, error_code, is_test_mode, is_dummy_mode
                    FROM draw_panel_metrics 
                    WHERE id = ?
                """, (anomaly_id,))
                
                record = cursor.fetchone()
                if record:
                    print(f"ID {record[0]}: 実際の処理時間 = {record[2]}秒, 異常検知での値 = {anomaly.get('elapsed_time')}秒")

if __name__ == "__main__":
    debug_anomaly_detection()