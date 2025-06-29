#!/usr/bin/env python3

import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent / "src"))

from weather_display.metrics.collector import MetricsAnalyzer
import datetime

def debug_zero_time_anomalies():
    """0秒の処理時間の異常を調査"""
    
    # メトリクス分析器を初期化
    analyzer = MetricsAnalyzer("data/metrics.db")
    
    # データベース接続を取得
    with analyzer._get_connection() as conn:
        cursor = conn.cursor()
        
        # 0秒の処理時間のレコードを取得
        cursor.execute("""
            SELECT timestamp, total_elapsed_time, error_code, is_test_mode, is_dummy_mode, panel_count
            FROM draw_panel_metrics 
            WHERE total_elapsed_time = 0.0 
            ORDER BY timestamp DESC 
            LIMIT 20
        """)
        
        zero_time_records = cursor.fetchall()
        
        print("=== 処理時間0.00秒のレコード ===")
        print(f"件数: {len(zero_time_records)}")
        print()
        
        for record in zero_time_records:
            timestamp, elapsed_time, error_code, is_test_mode, is_dummy_mode, panel_count = record
            print(f"時刻: {timestamp}")
            print(f"処理時間: {elapsed_time}秒")
            print(f"エラーコード: {error_code}")
            print(f"テストモード: {is_test_mode}")
            print(f"ダミーモード: {is_dummy_mode}")
            print(f"パネル数: {panel_count}")
            print("-" * 40)
        
        # 統計情報も取得
        cursor.execute("""
            SELECT 
                COUNT(*) as total_count,
                COUNT(CASE WHEN total_elapsed_time = 0.0 THEN 1 END) as zero_count,
                AVG(total_elapsed_time) as avg_time,
                MIN(total_elapsed_time) as min_time,
                MAX(total_elapsed_time) as max_time
            FROM draw_panel_metrics 
            WHERE timestamp >= date('now', '-7 days')
        """)
        
        stats = cursor.fetchone()
        total, zero, avg, min_time, max_time = stats
        
        print("\n=== 過去7日間の統計 ===")
        print(f"総レコード数: {total}")
        print(f"0秒レコード数: {zero}")
        print(f"0秒の割合: {(zero/total*100):.1f}%")
        print(f"平均処理時間: {avg:.2f}秒")
        print(f"最小処理時間: {min_time:.2f}秒")
        print(f"最大処理時間: {max_time:.2f}秒")

if __name__ == "__main__":
    debug_zero_time_anomalies()