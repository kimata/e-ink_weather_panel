"""実行時間の変動を平滑化するための簡易カルマンフィルタ実装"""


class TimingKalmanFilter:
    """実行時間推定用の1次元カルマンフィルタ"""

    def __init__(
        self, initial_estimate=30.0, initial_variance=10.0, process_noise=0.5, measurement_noise=2.0
    ):
        """
        初期化.

        Args:
            initial_estimate: 初期推定値（秒）
            initial_variance: 初期分散
            process_noise: プロセスノイズ（システムの変動）
            measurement_noise: 観測ノイズ（測定の変動）

        """
        self.x = initial_estimate  # 状態推定値
        self.P = initial_variance  # 誤差共分散
        self.Q = process_noise  # プロセスノイズ
        self.R = measurement_noise  # 観測ノイズ

    def update(self, measurement):
        """新しい測定値で状態を更新.

        Args:
            measurement: 実測された実行時間（秒）

        Returns:
            更新された推定値

        """
        # 予測ステップ（状態遷移なし、実行時間は基本的に一定と仮定）
        x_pred = self.x
        P_pred = self.P + self.Q

        # 更新ステップ
        K = P_pred / (P_pred + self.R)  # カルマンゲイン
        self.x = x_pred + K * (measurement - x_pred)
        self.P = (1 - K) * P_pred

        return self.x

    def get_estimate(self):
        """現在の推定値を取得"""
        return self.x


class TimingController:
    """実行タイミング制御クラス"""

    def __init__(self, update_interval=60, target_second=0):
        """初期化.

        Args:
            update_interval: 更新間隔（秒）
            target_second: 目標とする秒（0-59）

        """
        self.update_interval = update_interval
        self.target_second = target_second
        self.kalman_filter = TimingKalmanFilter()

    def calculate_sleep_time(self, elapsed_time, current_datetime):
        """次の実行までのスリープ時間を計算.

        Args:
            elapsed_time: 今回の実行時間（秒）
            current_datetime: 現在時刻（timezone aware）

        Returns:
            tuple: (sleep_time, diff_sec)

        """
        # カルマンフィルタで実行時間を更新
        estimated_elapsed = self.kalman_filter.update(elapsed_time)

        # 現在の秒を取得
        current_second = current_datetime.second

        # 目標時刻からのずれを計算
        diff_sec = current_second - self.target_second
        if diff_sec > 30:
            diff_sec = diff_sec - 60
        elif diff_sec < -30:
            diff_sec = diff_sec + 60

        # 次の目標時刻までの時間を計算
        # 推定実行時間を考慮してスリープ時間を決定
        sleep_time = self.update_interval - estimated_elapsed - current_second

        # 目標秒に合わせる調整
        if self.target_second > 0:
            sleep_time += self.target_second

        # スリープ時間が負の場合は次の周期に調整
        while sleep_time < 0:
            sleep_time += self.update_interval

        return sleep_time, diff_sec
