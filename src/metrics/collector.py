#!/usr/bin/env python3
"""
Performance metrics collection and anomaly detection for weather panel system.

This module provides functionality to:
- Collect elapsed time metrics from create_image and display_image operations
- Store metrics in SQLite database
- Perform statistical analysis and anomaly detection
- Analyze relationships with time patterns
"""

import datetime
import logging
import pathlib
import sqlite3
import statistics
import zoneinfo
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

TIMEZONE = zoneinfo.ZoneInfo("Asia/Tokyo")
DEFAULT_DB_PATH = pathlib.Path("data/metrics.db")


class MetricsCollector:
    """Collects and stores performance metrics for weather panel operations."""

    def __init__(self, db_path: Union[str, pathlib.Path] = DEFAULT_DB_PATH):
        self.db_path = pathlib.Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database with required tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create table for draw_panel metrics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS draw_panel_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    hour INTEGER NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    total_elapsed_time REAL NOT NULL,
                    is_small_mode BOOLEAN NOT NULL,
                    is_test_mode BOOLEAN NOT NULL,
                    is_dummy_mode BOOLEAN NOT NULL,
                    error_code INTEGER DEFAULT 0,
                    panel_count INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create table for individual panel metrics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS panel_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draw_panel_id INTEGER NOT NULL,
                    panel_name TEXT NOT NULL,
                    elapsed_time REAL NOT NULL,
                    has_error BOOLEAN DEFAULT FALSE,
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (draw_panel_id) REFERENCES draw_panel_metrics (id)
                )
            """)

            # Create table for display_image metrics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS display_image_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    hour INTEGER NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    elapsed_time REAL NOT NULL,
                    is_small_mode BOOLEAN NOT NULL,
                    is_test_mode BOOLEAN NOT NULL,
                    is_one_time BOOLEAN NOT NULL,
                    rasp_hostname TEXT,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    sleep_time REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for better query performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_draw_panel_timestamp ON draw_panel_metrics (timestamp)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_display_image_timestamp ON display_image_metrics (timestamp)"
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_draw_panel_hour ON draw_panel_metrics (hour)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_display_image_hour ON display_image_metrics (hour)"
            )

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logging.error("Database error: %s", e)
            raise
        finally:
            if conn:
                conn.close()

    def log_draw_panel_metrics(
        self,
        total_elapsed_time: float,
        panel_metrics: List[Dict],
        is_small_mode: bool = False,
        is_test_mode: bool = False,
        is_dummy_mode: bool = False,
        error_code: int = 0,
        timestamp: Optional[datetime.datetime] = None,
    ) -> int:
        """
        Log draw_panel operation metrics.

        Args:
            total_elapsed_time: Total time taken for draw_panel operation
            panel_metrics: List of dicts with panel metrics (name, elapsed_time, has_error, error_message)
            is_small_mode: Whether small mode was used
            is_test_mode: Whether test mode was used
            is_dummy_mode: Whether dummy mode was used
            error_code: Error code if any (0 = success)
            timestamp: When the operation occurred (default: now)

        Returns:
            ID of the inserted draw_panel_metrics record
        """
        if timestamp is None:
            timestamp = datetime.datetime.now(TIMEZONE)

        hour = timestamp.hour
        day_of_week = timestamp.weekday()
        panel_count = len(panel_metrics)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Insert main metrics record
                cursor.execute(
                    """
                    INSERT INTO draw_panel_metrics
                    (timestamp, hour, day_of_week, total_elapsed_time, is_small_mode,
                     is_test_mode, is_dummy_mode, error_code, panel_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        timestamp,
                        hour,
                        day_of_week,
                        total_elapsed_time,
                        is_small_mode,
                        is_test_mode,
                        is_dummy_mode,
                        error_code,
                        panel_count,
                    ),
                )

                draw_panel_id = cursor.lastrowid

                # Insert individual panel metrics
                for panel in panel_metrics:
                    cursor.execute(
                        """
                        INSERT INTO panel_metrics
                        (draw_panel_id, panel_name, elapsed_time, has_error, error_message)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            draw_panel_id,
                            panel["name"],
                            panel["elapsed_time"],
                            panel.get("has_error", False),
                            panel.get("error_message"),
                        ),
                    )

                conn.commit()
                logging.debug(
                    "Logged draw_panel metrics: total=%.3fs, panels=%d", total_elapsed_time, panel_count
                )
                return draw_panel_id

        except Exception as e:
            logging.error("Failed to log draw_panel metrics: %s", e)
            return -1

    def log_display_image_metrics(
        self,
        elapsed_time: float,
        is_small_mode: bool = False,
        is_test_mode: bool = False,
        is_one_time: bool = False,
        rasp_hostname: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        timestamp: Optional[datetime.datetime] = None,
        sleep_time: Optional[float] = None,
    ) -> int:
        """
        Log display_image operation metrics.

        Args:
            elapsed_time: Time taken for display_image operation
            is_small_mode: Whether small mode was used
            is_test_mode: Whether test mode was used
            is_one_time: Whether one-time mode was used
            rasp_hostname: Raspberry Pi hostname
            success: Whether the operation succeeded
            error_message: Error message if any
            timestamp: When the operation occurred (default: now)

        Returns:
            ID of the inserted record
        """
        if timestamp is None:
            timestamp = datetime.datetime.now(TIMEZONE)

        hour = timestamp.hour
        day_of_week = timestamp.weekday()

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO display_image_metrics
                    (timestamp, hour, day_of_week, elapsed_time, is_small_mode, is_test_mode,
                     is_one_time, rasp_hostname, success, error_message, sleep_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        timestamp,
                        hour,
                        day_of_week,
                        elapsed_time,
                        is_small_mode,
                        is_test_mode,
                        is_one_time,
                        rasp_hostname,
                        success,
                        error_message,
                        sleep_time,
                    ),
                )

                conn.commit()
                logging.debug(
                    "Logged display_image metrics: elapsed=%.3fs, success=%s", elapsed_time, success
                )
                return cursor.lastrowid

        except Exception as e:
            logging.error("Failed to log display_image metrics: %s", e)
            return -1


class MetricsAnalyzer:
    """Analyzes metrics data for patterns and anomalies."""

    def __init__(self, db_path: Union[str, pathlib.Path] = DEFAULT_DB_PATH):
        self.db_path = pathlib.Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Metrics database not found: {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            logging.error("Database error: %s", e)
            raise
        finally:
            if conn:
                conn.close()

    def get_basic_statistics(self, days: int = 30) -> Dict:
        """Get basic statistics for the last N days."""
        since = datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Draw panel statistics
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_operations,
                    AVG(total_elapsed_time) as avg_elapsed_time,
                    MIN(total_elapsed_time) as min_elapsed_time,
                    MAX(total_elapsed_time) as max_elapsed_time,
                    SUM(CASE WHEN error_code > 0 THEN 1 ELSE 0 END) as error_count
                FROM draw_panel_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            draw_panel_stats = dict(cursor.fetchone())

            # Display image statistics
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_operations,
                    AVG(elapsed_time) as avg_elapsed_time,
                    MIN(elapsed_time) as min_elapsed_time,
                    MAX(elapsed_time) as max_elapsed_time,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
                FROM display_image_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            display_image_stats = dict(cursor.fetchone())

            return {
                "period_days": days,
                "draw_panel": draw_panel_stats,
                "display_image": display_image_stats,
            }

    def get_hourly_patterns(self, days: int = 30) -> Dict:
        """Analyze performance patterns by hour of day."""
        since = datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Draw panel hourly patterns (aggregated)
            cursor.execute(
                """
                SELECT
                    hour,
                    COUNT(*) as count,
                    AVG(total_elapsed_time) as avg_elapsed_time,
                    MIN(total_elapsed_time) as min_elapsed_time,
                    MAX(total_elapsed_time) as max_elapsed_time,
                    SUM(CASE WHEN error_code > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM draw_panel_metrics
                WHERE timestamp >= ?
                GROUP BY hour
                ORDER BY hour
            """,
                (since,),
            )
            draw_panel_hourly = [dict(row) for row in cursor.fetchall()]

            # Display image hourly patterns (aggregated)
            cursor.execute(
                """
                SELECT
                    hour,
                    COUNT(*) as count,
                    AVG(elapsed_time) as avg_elapsed_time,
                    MIN(elapsed_time) as min_elapsed_time,
                    MAX(elapsed_time) as max_elapsed_time,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM display_image_metrics
                WHERE timestamp >= ?
                GROUP BY hour
                ORDER BY hour
            """,
                (since,),
            )
            display_image_hourly = [dict(row) for row in cursor.fetchall()]

            # Get raw data for boxplots
            cursor.execute(
                """
                SELECT hour, total_elapsed_time
                FROM draw_panel_metrics
                WHERE timestamp >= ?
                ORDER BY hour
            """,
                (since,),
            )
            draw_panel_raw = cursor.fetchall()

            cursor.execute(
                """
                SELECT hour, elapsed_time
                FROM display_image_metrics
                WHERE timestamp >= ?
                ORDER BY hour
            """,
                (since,),
            )
            display_image_raw = cursor.fetchall()

            # Group raw data by hour for boxplots
            draw_panel_boxplot = {}
            for row in draw_panel_raw:
                hour = row[0]
                if hour not in draw_panel_boxplot:
                    draw_panel_boxplot[hour] = []
                draw_panel_boxplot[hour].append(row[1])

            display_image_boxplot = {}
            for row in display_image_raw:
                hour = row[0]
                if hour not in display_image_boxplot:
                    display_image_boxplot[hour] = []
                display_image_boxplot[hour].append(row[1])

            return {
                "draw_panel": draw_panel_hourly,
                "display_image": display_image_hourly,
                "draw_panel_boxplot": draw_panel_boxplot,
                "display_image_boxplot": display_image_boxplot,
            }

    def detect_anomalies(self, days: int = 30, contamination: float = 0.1) -> Dict:
        """
        Detect anomalies in performance metrics using Isolation Forest.

        Args:
            days: Number of days to analyze
            contamination: Expected proportion of anomalies (0.0 to 0.5)

        Returns:
            Dictionary with anomaly detection results
        """
        since = datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get draw panel data
            cursor.execute(
                """
                SELECT id, timestamp, hour, day_of_week, total_elapsed_time, error_code
                FROM draw_panel_metrics
                WHERE timestamp >= ?
                ORDER BY timestamp
            """,
                (since,),
            )
            draw_panel_data = [dict(row) for row in cursor.fetchall()]

            # Get display image data
            cursor.execute(
                """
                SELECT id, timestamp, hour, day_of_week, elapsed_time, success
                FROM display_image_metrics
                WHERE timestamp >= ?
                ORDER BY timestamp
            """,
                (since,),
            )
            display_image_data = [dict(row) for row in cursor.fetchall()]

        results = {}

        # Analyze draw panel anomalies
        if len(draw_panel_data) > 10:
            features = np.array(
                [
                    [row["hour"], row["day_of_week"], row["total_elapsed_time"], row["error_code"]]
                    for row in draw_panel_data
                ]
            )

            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)

            isolation_forest = IsolationForest(contamination=contamination, random_state=42)
            anomaly_labels = isolation_forest.fit_predict(features_scaled)

            draw_panel_anomalies = []
            for i, label in enumerate(anomaly_labels):
                if label == -1:  # Anomaly
                    draw_panel_anomalies.append(
                        {
                            "id": draw_panel_data[i]["id"],
                            "timestamp": draw_panel_data[i]["timestamp"],
                            "elapsed_time": draw_panel_data[i]["total_elapsed_time"],
                            "hour": draw_panel_data[i]["hour"],
                            "error_code": draw_panel_data[i]["error_code"],
                        }
                    )

            results["draw_panel"] = {
                "total_samples": len(draw_panel_data),
                "anomalies_detected": len(draw_panel_anomalies),
                "anomaly_rate": len(draw_panel_anomalies) / len(draw_panel_data),
                "anomalies": draw_panel_anomalies,
            }

        # Analyze display image anomalies
        if len(display_image_data) > 10:
            features = np.array(
                [
                    [row["hour"], row["day_of_week"], row["elapsed_time"], int(not row["success"])]
                    for row in display_image_data
                ]
            )

            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)

            isolation_forest = IsolationForest(contamination=contamination, random_state=42)
            anomaly_labels = isolation_forest.fit_predict(features_scaled)

            display_image_anomalies = []
            for i, label in enumerate(anomaly_labels):
                if label == -1:  # Anomaly
                    display_image_anomalies.append(
                        {
                            "id": display_image_data[i]["id"],
                            "timestamp": display_image_data[i]["timestamp"],
                            "elapsed_time": display_image_data[i]["elapsed_time"],
                            "hour": display_image_data[i]["hour"],
                            "success": display_image_data[i]["success"],
                        }
                    )

            results["display_image"] = {
                "total_samples": len(display_image_data),
                "anomalies_detected": len(display_image_anomalies),
                "anomaly_rate": len(display_image_anomalies) / len(display_image_data),
                "anomalies": display_image_anomalies,
            }

        return results

    def get_performance_trends(self, days: int = 30) -> Dict:
        """Analyze performance trends over time."""
        since = datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Daily trends for draw panel
            cursor.execute(
                """
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as operations,
                    AVG(total_elapsed_time) as avg_elapsed_time,
                    SUM(CASE WHEN error_code > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM draw_panel_metrics
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date
            """,
                (since,),
            )
            draw_panel_trends = [dict(row) for row in cursor.fetchall()]

            # Daily trends for display image
            cursor.execute(
                """
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as operations,
                    AVG(elapsed_time) as avg_elapsed_time,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM display_image_metrics
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date
            """,
                (since,),
            )
            display_image_trends = [dict(row) for row in cursor.fetchall()]

            return {
                "draw_panel": draw_panel_trends,
                "display_image": display_image_trends,
            }

    def check_performance_alerts(self, thresholds: Optional[Dict] = None) -> List[Dict]:
        """
        Check for performance alerts based on thresholds.

        Args:
            thresholds: Custom thresholds (default: reasonable values)

        Returns:
            List of alert dictionaries
        """
        if thresholds is None:
            thresholds = {
                "draw_panel_max_time": 60.0,  # seconds
                "display_image_max_time": 120.0,  # seconds
                "error_rate_threshold": 10.0,  # percent
                "recent_hours": 24,  # hours to check
            }

        alerts = []
        since = datetime.datetime.now(TIMEZONE) - datetime.timedelta(hours=thresholds["recent_hours"])

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check for slow draw_panel operations
            cursor.execute(
                """
                SELECT COUNT(*) as slow_count, MAX(total_elapsed_time) as max_time
                FROM draw_panel_metrics
                WHERE timestamp >= ? AND total_elapsed_time > ?
            """,
                (since, thresholds["draw_panel_max_time"]),
            )
            row = cursor.fetchone()
            if row["slow_count"] > 0:
                alerts.append(
                    {
                        "type": "slow_draw_panel",
                        "message": f"Found {row['slow_count']} slow draw_panel operations (max: {row['max_time']:.1f}s)",
                        "severity": "warning",
                    }
                )

            # Check for slow display_image operations
            cursor.execute(
                """
                SELECT COUNT(*) as slow_count, MAX(elapsed_time) as max_time
                FROM display_image_metrics
                WHERE timestamp >= ? AND elapsed_time > ?
            """,
                (since, thresholds["display_image_max_time"]),
            )
            row = cursor.fetchone()
            if row["slow_count"] > 0:
                alerts.append(
                    {
                        "type": "slow_display_image",
                        "message": f"Found {row['slow_count']} slow display_image operations (max: {row['max_time']:.1f}s)",
                        "severity": "warning",
                    }
                )

            # Check error rates
            cursor.execute(
                """
                SELECT
                    SUM(CASE WHEN error_code > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM draw_panel_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            row = cursor.fetchone()
            if row["error_rate"] and row["error_rate"] > thresholds["error_rate_threshold"]:
                alerts.append(
                    {
                        "type": "high_draw_panel_error_rate",
                        "message": f"High draw_panel error rate: {row['error_rate']:.1f}%",
                        "severity": "critical",
                    }
                )

            cursor.execute(
                """
                SELECT
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM display_image_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            row = cursor.fetchone()
            if row["error_rate"] and row["error_rate"] > thresholds["error_rate_threshold"]:
                alerts.append(
                    {
                        "type": "high_display_image_error_rate",
                        "message": f"High display_image error rate: {row['error_rate']:.1f}%",
                        "severity": "critical",
                    }
                )

        return alerts

    def get_panel_performance_trends(self, days: int = 30) -> Dict:
        """パネル別の処理時間推移を取得する。"""
        since = datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # パネル別の処理時間データを取得
            cursor.execute(
                """
                SELECT
                    pm.panel_name,
                    pm.elapsed_time,
                    dpm.timestamp
                FROM panel_metrics pm
                JOIN draw_panel_metrics dpm ON pm.draw_panel_id = dpm.id
                WHERE dpm.timestamp >= ?
                ORDER BY pm.panel_name, dpm.timestamp
            """,
                (since,),
            )
            panel_data = cursor.fetchall()

            # パネル名ごとにグループ化
            panel_groups = {}
            for row in panel_data:
                panel_name = row[0]
                elapsed_time = row[1]

                if panel_name not in panel_groups:
                    panel_groups[panel_name] = []
                panel_groups[panel_name].append(elapsed_time)

            return panel_groups

    def get_performance_statistics(self, days: int = 30) -> dict:
        """パフォーマンス統計情報を取得する（異常検知詳細用）"""
        since = datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 画像生成処理の統計
            cursor.execute(
                """
                SELECT
                    AVG(total_elapsed_time) as avg_time,
                    COUNT(*) as count,
                    MIN(total_elapsed_time) as min_time,
                    MAX(total_elapsed_time) as max_time
                FROM draw_panel_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            draw_panel_stats = dict(cursor.fetchone())

            # 標準偏差を計算（SQLiteにはSTDDEV関数がないため、手動計算）
            cursor.execute(
                """
                SELECT total_elapsed_time
                FROM draw_panel_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            draw_panel_times = [row[0] for row in cursor.fetchall()]

            if len(draw_panel_times) > 1:
                import statistics

                draw_panel_stats["std_time"] = statistics.stdev(draw_panel_times)
            else:
                draw_panel_stats["std_time"] = 0

            # 表示実行処理の統計
            cursor.execute(
                """
                SELECT
                    AVG(elapsed_time) as avg_time,
                    COUNT(*) as count,
                    MIN(elapsed_time) as min_time,
                    MAX(elapsed_time) as max_time
                FROM display_image_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            display_image_stats = dict(cursor.fetchone())

            cursor.execute(
                """
                SELECT elapsed_time
                FROM display_image_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            display_image_times = [row[0] for row in cursor.fetchall()]

            if len(display_image_times) > 1:
                display_image_stats["std_time"] = statistics.stdev(display_image_times)
            else:
                display_image_stats["std_time"] = 0

            return {"draw_panel": draw_panel_stats, "display_image": display_image_stats}


# Global instance for easy access
_metrics_collector = None


def get_metrics_collector(db_path: Union[str, pathlib.Path] = DEFAULT_DB_PATH) -> MetricsCollector:
    """Get or create global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None or _metrics_collector.db_path != pathlib.Path(db_path):
        _metrics_collector = MetricsCollector(db_path)
    return _metrics_collector


def collect_draw_panel_metrics(*args, db_path: Union[str, pathlib.Path] = None, **kwargs) -> int:
    """Convenience function to collect draw_panel metrics."""
    if db_path is not None:
        kwargs.pop("db_path", None)  # Remove db_path from kwargs to avoid duplicate
        return get_metrics_collector(db_path).log_draw_panel_metrics(*args, **kwargs)
    return get_metrics_collector().log_draw_panel_metrics(*args, **kwargs)


def collect_display_image_metrics(*args, db_path: Union[str, pathlib.Path] = None, **kwargs) -> int:
    """Convenience function to collect display_image metrics."""
    if db_path is not None:
        kwargs.pop("db_path", None)  # Remove db_path from kwargs to avoid duplicate
        return get_metrics_collector(db_path).log_display_image_metrics(*args, **kwargs)
    return get_metrics_collector().log_display_image_metrics(*args, **kwargs)
