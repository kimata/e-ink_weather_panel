"""
Performance metrics collection and anomaly detection for unit cooler system.

This module provides functionality to:
- Collect elapsed time metrics from unit cooler actuator operations
- Store metrics in SQLite database
- Perform statistical analysis and anomaly detection
- Analyze relationships with time patterns
"""

import datetime
import logging
import pathlib
import sqlite3
import zoneinfo
from contextlib import contextmanager

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

TIMEZONE = zoneinfo.ZoneInfo("Asia/Tokyo")
DEFAULT_DB_PATH = pathlib.Path("data/unit_cooler_metrics.db")


class MetricsCollector:
    """Collects and stores performance metrics for unit cooler operations."""  # noqa: D203

    def __init__(self, db_path: str | pathlib.Path = DEFAULT_DB_PATH):
        """Initialize MetricsCollector with database path."""
        self.db_path = pathlib.Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database with required tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create table for actuator operation metrics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS actuator_operation_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    hour INTEGER NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    operation_type TEXT NOT NULL,
                    elapsed_time REAL NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    parameters TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create table for sensor reading metrics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensor_reading_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    hour INTEGER NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    sensor_type TEXT NOT NULL,
                    elapsed_time REAL NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    value REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create table for control loop metrics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS control_loop_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    hour INTEGER NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    loop_cycle_time REAL NOT NULL,
                    target_temperature REAL,
                    current_temperature REAL,
                    temperature_error REAL,
                    control_action TEXT,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for better query performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_actuator_timestamp ON actuator_operation_metrics (timestamp)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_reading_metrics (timestamp)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_control_timestamp ON control_loop_metrics (timestamp)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_actuator_hour ON actuator_operation_metrics (hour)"
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor_hour ON sensor_reading_metrics (hour)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_control_hour ON control_loop_metrics (hour)")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception:
            if conn:
                conn.rollback()
            logging.exception("Database error")
            raise
        finally:
            if conn:
                conn.close()

    def log_actuator_operation_metrics(  # noqa: PLR0913
        self,
        operation_type: str,
        elapsed_time: float,
        success: bool = True,  # noqa: FBT001
        error_message: str | None = None,
        parameters: str | None = None,
        timestamp: datetime.datetime | None = None,
    ) -> int:
        """
        Log actuator operation metrics.

        Args:
            operation_type: Type of operation (e.g., 'start', 'stop', 'speed_change')
            elapsed_time: Time taken for the operation
            success: Whether the operation succeeded
            error_message: Error message if any
            parameters: Operation parameters as JSON string
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
                    INSERT INTO actuator_operation_metrics
                    (timestamp, hour, day_of_week, operation_type, elapsed_time,
                     success, error_message, parameters)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        timestamp,
                        hour,
                        day_of_week,
                        operation_type,
                        elapsed_time,
                        success,
                        error_message,
                        parameters,
                    ),
                )

                conn.commit()
                logging.debug(
                    "Logged actuator operation metrics: type=%s, elapsed=%.3fs, success=%s",
                    operation_type,
                    elapsed_time,
                    success,
                )
                return cursor.lastrowid

        except Exception:
            logging.exception("Failed to log actuator operation metrics")
            return -1

    def log_sensor_reading_metrics(  # noqa: PLR0913
        self,
        sensor_type: str,
        elapsed_time: float,
        success: bool = True,  # noqa: FBT001
        error_message: str | None = None,
        value: float | None = None,
        timestamp: datetime.datetime | None = None,
    ) -> int:
        """
        Log sensor reading metrics.

        Args:
            sensor_type: Type of sensor (e.g., 'temperature', 'humidity')
            elapsed_time: Time taken for the reading
            success: Whether the reading succeeded
            error_message: Error message if any
            value: Sensor value if reading succeeded
            timestamp: When the reading occurred (default: now)

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
                    INSERT INTO sensor_reading_metrics
                    (timestamp, hour, day_of_week, sensor_type, elapsed_time,
                     success, error_message, value)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        timestamp,
                        hour,
                        day_of_week,
                        sensor_type,
                        elapsed_time,
                        success,
                        error_message,
                        value,
                    ),
                )

                conn.commit()
                logging.debug(
                    "Logged sensor reading metrics: type=%s, elapsed=%.3fs, success=%s",
                    sensor_type,
                    elapsed_time,
                    success,
                )
                return cursor.lastrowid

        except Exception:
            logging.exception("Failed to log sensor reading metrics")
            return -1

    def log_control_loop_metrics(  # noqa: PLR0913
        self,
        loop_cycle_time: float,
        target_temperature: float | None = None,
        current_temperature: float | None = None,
        temperature_error: float | None = None,
        control_action: str | None = None,
        success: bool = True,  # noqa: FBT001
        error_message: str | None = None,
        timestamp: datetime.datetime | None = None,
    ) -> int:
        """
        Log control loop metrics.

        Args:
            loop_cycle_time: Time taken for one control loop cycle
            target_temperature: Target temperature
            current_temperature: Current temperature
            temperature_error: Temperature error (target - current)
            control_action: Control action taken
            success: Whether the control loop succeeded
            error_message: Error message if any
            timestamp: When the control loop occurred (default: now)

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
                    INSERT INTO control_loop_metrics
                    (timestamp, hour, day_of_week, loop_cycle_time, target_temperature,
                     current_temperature, temperature_error, control_action, success, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        timestamp,
                        hour,
                        day_of_week,
                        loop_cycle_time,
                        target_temperature,
                        current_temperature,
                        temperature_error,
                        control_action,
                        success,
                        error_message,
                    ),
                )

                conn.commit()
                logging.debug(
                    "Logged control loop metrics: cycle_time=%.3fs, success=%s",
                    loop_cycle_time,
                    success,
                )
                return cursor.lastrowid

        except Exception:
            logging.exception("Failed to log control loop metrics")
            return -1


class MetricsAnalyzer:
    """Analyzes metrics data for patterns and anomalies."""  # noqa: D203

    def __init__(self, db_path: str | pathlib.Path = DEFAULT_DB_PATH):
        """Initialize MetricsAnalyzer with database path."""
        self.db_path = pathlib.Path(db_path)
        if not self.db_path.exists():
            msg = f"Metrics database not found: {self.db_path}"
            raise FileNotFoundError(msg)

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception:
            logging.exception("Database error")
            raise
        finally:
            if conn:
                conn.close()

    def get_basic_statistics(self, days: int = 30) -> dict:
        """Get basic statistics for the last N days."""
        since = datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Actuator operation statistics
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_operations,
                    AVG(elapsed_time) as avg_elapsed_time,
                    MIN(elapsed_time) as min_elapsed_time,
                    MAX(elapsed_time) as max_elapsed_time,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
                FROM actuator_operation_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            actuator_stats = dict(cursor.fetchone())

            # Sensor reading statistics
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_operations,
                    AVG(elapsed_time) as avg_elapsed_time,
                    MIN(elapsed_time) as min_elapsed_time,
                    MAX(elapsed_time) as max_elapsed_time,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
                FROM sensor_reading_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            sensor_stats = dict(cursor.fetchone())

            # Control loop statistics
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_operations,
                    AVG(loop_cycle_time) as avg_cycle_time,
                    MIN(loop_cycle_time) as min_cycle_time,
                    MAX(loop_cycle_time) as max_cycle_time,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
                FROM control_loop_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            control_stats = dict(cursor.fetchone())

            return {
                "period_days": days,
                "actuator_operations": actuator_stats,
                "sensor_readings": sensor_stats,
                "control_loops": control_stats,
            }

    def get_hourly_patterns(self, days: int = 30) -> dict:
        """Analyze performance patterns by hour of day."""
        since = datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Actuator operation hourly patterns
            cursor.execute(
                """
                SELECT
                    hour,
                    COUNT(*) as count,
                    AVG(elapsed_time) as avg_elapsed_time,
                    MIN(elapsed_time) as min_elapsed_time,
                    MAX(elapsed_time) as max_elapsed_time,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM actuator_operation_metrics
                WHERE timestamp >= ?
                GROUP BY hour
                ORDER BY hour
            """,
                (since,),
            )
            actuator_hourly = [dict(row) for row in cursor.fetchall()]

            # Sensor reading hourly patterns
            cursor.execute(
                """
                SELECT
                    hour,
                    COUNT(*) as count,
                    AVG(elapsed_time) as avg_elapsed_time,
                    MIN(elapsed_time) as min_elapsed_time,
                    MAX(elapsed_time) as max_elapsed_time,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM sensor_reading_metrics
                WHERE timestamp >= ?
                GROUP BY hour
                ORDER BY hour
            """,
                (since,),
            )
            sensor_hourly = [dict(row) for row in cursor.fetchall()]

            # Control loop hourly patterns
            cursor.execute(
                """
                SELECT
                    hour,
                    COUNT(*) as count,
                    AVG(loop_cycle_time) as avg_cycle_time,
                    MIN(loop_cycle_time) as min_cycle_time,
                    MAX(loop_cycle_time) as max_cycle_time,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM control_loop_metrics
                WHERE timestamp >= ?
                GROUP BY hour
                ORDER BY hour
            """,
                (since,),
            )
            control_hourly = [dict(row) for row in cursor.fetchall()]

            return {
                "actuator_operations": actuator_hourly,
                "sensor_readings": sensor_hourly,
                "control_loops": control_hourly,
            }

    def detect_anomalies(self, days: int = 30, contamination: float = 0.1) -> dict:
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

            # Get actuator operation data
            cursor.execute(
                """
                SELECT id, timestamp, hour, day_of_week, elapsed_time, success
                FROM actuator_operation_metrics
                WHERE timestamp >= ?
                ORDER BY timestamp
            """,
                (since,),
            )
            actuator_data = [dict(row) for row in cursor.fetchall()]

            # Get control loop data
            cursor.execute(
                """
                SELECT id, timestamp, hour, day_of_week, loop_cycle_time, success
                FROM control_loop_metrics
                WHERE timestamp >= ?
                ORDER BY timestamp
            """,
                (since,),
            )
            control_data = [dict(row) for row in cursor.fetchall()]

        results = {}

        # Analyze actuator operation anomalies
        if len(actuator_data) > 10:
            features = np.array(
                [
                    [row["hour"], row["day_of_week"], row["elapsed_time"], int(not row["success"])]
                    for row in actuator_data
                ]
            )

            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)

            isolation_forest = IsolationForest(contamination=contamination, random_state=42)
            anomaly_labels = isolation_forest.fit_predict(features_scaled)

            actuator_anomalies = []
            for i, label in enumerate(anomaly_labels):
                if label == -1:  # Anomaly
                    actuator_anomalies.append(
                        {
                            "id": actuator_data[i]["id"],
                            "timestamp": actuator_data[i]["timestamp"],
                            "elapsed_time": actuator_data[i]["elapsed_time"],
                            "hour": actuator_data[i]["hour"],
                            "success": actuator_data[i]["success"],
                        }
                    )

            results["actuator_operations"] = {
                "total_samples": len(actuator_data),
                "anomalies_detected": len(actuator_anomalies),
                "anomaly_rate": len(actuator_anomalies) / len(actuator_data),
                "anomalies": actuator_anomalies,
            }

        # Analyze control loop anomalies
        if len(control_data) > 10:
            features = np.array(
                [
                    [row["hour"], row["day_of_week"], row["loop_cycle_time"], int(not row["success"])]
                    for row in control_data
                ]
            )

            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)

            isolation_forest = IsolationForest(contamination=contamination, random_state=42)
            anomaly_labels = isolation_forest.fit_predict(features_scaled)

            control_anomalies = []
            for i, label in enumerate(anomaly_labels):
                if label == -1:  # Anomaly
                    control_anomalies.append(
                        {
                            "id": control_data[i]["id"],
                            "timestamp": control_data[i]["timestamp"],
                            "cycle_time": control_data[i]["loop_cycle_time"],
                            "hour": control_data[i]["hour"],
                            "success": control_data[i]["success"],
                        }
                    )

            results["control_loops"] = {
                "total_samples": len(control_data),
                "anomalies_detected": len(control_anomalies),
                "anomaly_rate": len(control_anomalies) / len(control_data),
                "anomalies": control_anomalies,
            }

        return results

    def get_performance_trends(self, days: int = 30) -> dict:
        """Analyze performance trends over time."""
        since = datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Daily trends for actuator operations
            cursor.execute(
                """
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as operations,
                    AVG(elapsed_time) as avg_elapsed_time,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM actuator_operation_metrics
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date
            """,
                (since,),
            )
            actuator_trends = [dict(row) for row in cursor.fetchall()]

            # Daily trends for control loops
            cursor.execute(
                """
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as operations,
                    AVG(loop_cycle_time) as avg_cycle_time,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM control_loop_metrics
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date
            """,
                (since,),
            )
            control_trends = [dict(row) for row in cursor.fetchall()]

            return {
                "actuator_operations": actuator_trends,
                "control_loops": control_trends,
            }

    def check_performance_alerts(self, thresholds: dict | None = None) -> list[dict]:
        """
        Check for performance alerts based on thresholds.

        Args:
            thresholds: Custom thresholds (default: reasonable values)

        Returns:
            List of alert dictionaries

        """
        if thresholds is None:
            thresholds = {
                "actuator_max_time": 5.0,  # seconds
                "sensor_max_time": 2.0,  # seconds
                "control_max_time": 1.0,  # seconds
                "error_rate_threshold": 5.0,  # percent
                "recent_hours": 24,  # hours to check
            }

        alerts = []
        since = datetime.datetime.now(TIMEZONE) - datetime.timedelta(hours=thresholds["recent_hours"])

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check for slow actuator operations
            cursor.execute(
                """
                SELECT COUNT(*) as slow_count, MAX(elapsed_time) as max_time
                FROM actuator_operation_metrics
                WHERE timestamp >= ? AND elapsed_time > ?
            """,
                (since, thresholds["actuator_max_time"]),
            )
            row = cursor.fetchone()
            if row["slow_count"] > 0:
                alerts.append(
                    {
                        "type": "slow_actuator_operations",
                        "message": (
                            f"Found {row['slow_count']} slow actuator operations "
                            f"(max: {row['max_time']:.1f}s)"
                        ),
                        "severity": "warning",
                    }
                )

            # Check for slow sensor readings
            cursor.execute(
                """
                SELECT COUNT(*) as slow_count, MAX(elapsed_time) as max_time
                FROM sensor_reading_metrics
                WHERE timestamp >= ? AND elapsed_time > ?
            """,
                (since, thresholds["sensor_max_time"]),
            )
            row = cursor.fetchone()
            if row["slow_count"] > 0:
                alerts.append(
                    {
                        "type": "slow_sensor_readings",
                        "message": (
                            f"Found {row['slow_count']} slow sensor readings (max: {row['max_time']:.1f}s)"
                        ),
                        "severity": "warning",
                    }
                )

            # Check for slow control loops
            cursor.execute(
                """
                SELECT COUNT(*) as slow_count, MAX(loop_cycle_time) as max_time
                FROM control_loop_metrics
                WHERE timestamp >= ? AND loop_cycle_time > ?
            """,
                (since, thresholds["control_max_time"]),
            )
            row = cursor.fetchone()
            if row["slow_count"] > 0:
                alerts.append(
                    {
                        "type": "slow_control_loops",
                        "message": (
                            f"Found {row['slow_count']} slow control loops (max: {row['max_time']:.1f}s)"
                        ),
                        "severity": "warning",
                    }
                )

            # Check actuator operation error rate
            cursor.execute(
                """
                SELECT
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM actuator_operation_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            row = cursor.fetchone()
            if row["error_rate"] and row["error_rate"] > thresholds["error_rate_threshold"]:
                alerts.append(
                    {
                        "type": "high_actuator_operations_error_rate",
                        "message": f"High actuator operations error rate: {row['error_rate']:.1f}%",
                        "severity": "critical",
                    }
                )

            # Check sensor reading error rate
            cursor.execute(
                """
                SELECT
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM sensor_reading_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            row = cursor.fetchone()
            if row["error_rate"] and row["error_rate"] > thresholds["error_rate_threshold"]:
                alerts.append(
                    {
                        "type": "high_sensor_readings_error_rate",
                        "message": f"High sensor readings error rate: {row['error_rate']:.1f}%",
                        "severity": "critical",
                    }
                )

            # Check control loop error rate
            cursor.execute(
                """
                SELECT
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as error_rate
                FROM control_loop_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            row = cursor.fetchone()
            if row["error_rate"] and row["error_rate"] > thresholds["error_rate_threshold"]:
                alerts.append(
                    {
                        "type": "high_control_loops_error_rate",
                        "message": f"High control loops error rate: {row['error_rate']:.1f}%",
                        "severity": "critical",
                    }
                )

        return alerts

    def get_operation_performance_trends(self, days: int = 30) -> dict:
        """操作別の処理時間推移を取得する。"""
        since = datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 操作別の処理時間データを取得
            cursor.execute(
                """
                SELECT
                    operation_type,
                    elapsed_time,
                    timestamp
                FROM actuator_operation_metrics
                WHERE timestamp >= ?
                ORDER BY operation_type, timestamp
            """,
                (since,),
            )
            operation_data = cursor.fetchall()

            # 操作タイプごとにグループ化
            operation_groups = {}
            for row in operation_data:
                operation_type = row[0]
                elapsed_time = row[1]

                if operation_type not in operation_groups:
                    operation_groups[operation_type] = []
                operation_groups[operation_type].append(elapsed_time)

            return operation_groups

    def get_performance_statistics(self, days: int = 30) -> dict:
        """パフォーマンス統計情報を取得する（異常検知詳細用）"""
        since = datetime.datetime.now(TIMEZONE) - datetime.timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # アクチュエータ操作の統計
            cursor.execute(
                """
                SELECT
                    AVG(elapsed_time) as avg_time,
                    COUNT(*) as count,
                    MIN(elapsed_time) as min_time,
                    MAX(elapsed_time) as max_time
                FROM actuator_operation_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            actuator_stats = dict(cursor.fetchone())

            # 標準偏差を計算（SQLiteにはSTDDEV関数がないため、手動計算）
            cursor.execute(
                """
                SELECT elapsed_time
                FROM actuator_operation_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            actuator_times = [row[0] for row in cursor.fetchall()]

            if len(actuator_times) > 1:
                actuator_stats["std_time"] = np.std(actuator_times, ddof=1)
            else:
                actuator_stats["std_time"] = 0

            # 制御ループの統計
            cursor.execute(
                """
                SELECT
                    AVG(loop_cycle_time) as avg_time,
                    COUNT(*) as count,
                    MIN(loop_cycle_time) as min_time,
                    MAX(loop_cycle_time) as max_time
                FROM control_loop_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            control_stats = dict(cursor.fetchone())

            cursor.execute(
                """
                SELECT loop_cycle_time
                FROM control_loop_metrics
                WHERE timestamp >= ?
            """,
                (since,),
            )
            control_times = [row[0] for row in cursor.fetchall()]

            if len(control_times) > 1:
                control_stats["std_time"] = np.std(control_times, ddof=1)
            else:
                control_stats["std_time"] = 0

            return {"actuator_operations": actuator_stats, "control_loops": control_stats}


# Global instance for easy access
_metrics_collector = None


def get_metrics_collector(db_path: str | pathlib.Path = DEFAULT_DB_PATH) -> MetricsCollector:
    """Get or create global metrics collector instance."""
    global _metrics_collector  # noqa: PLW0603
    if _metrics_collector is None or _metrics_collector.db_path != pathlib.Path(db_path):
        _metrics_collector = MetricsCollector(db_path)
    return _metrics_collector


def collect_actuator_operation_metrics(*args, db_path: str | pathlib.Path | None = None, **kwargs) -> int:
    """Collect actuator operation metrics with convenience wrapper."""
    if db_path is not None:
        kwargs.pop("db_path", None)
        return get_metrics_collector(db_path).log_actuator_operation_metrics(*args, **kwargs)
    return get_metrics_collector().log_actuator_operation_metrics(*args, **kwargs)


def collect_sensor_reading_metrics(*args, db_path: str | pathlib.Path | None = None, **kwargs) -> int:
    """Collect sensor reading metrics with convenience wrapper."""
    if db_path is not None:
        kwargs.pop("db_path", None)
        return get_metrics_collector(db_path).log_sensor_reading_metrics(*args, **kwargs)
    return get_metrics_collector().log_sensor_reading_metrics(*args, **kwargs)


def collect_control_loop_metrics(*args, db_path: str | pathlib.Path | None = None, **kwargs) -> int:
    """Collect control loop metrics with convenience wrapper."""
    if db_path is not None:
        kwargs.pop("db_path", None)
        return get_metrics_collector(db_path).log_control_loop_metrics(*args, **kwargs)
    return get_metrics_collector().log_control_loop_metrics(*args, **kwargs)
