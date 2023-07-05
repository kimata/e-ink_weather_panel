#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InfluxDB から電子機器の使用時間を取得します．

Usage:
  sensor_data.py [-c CONFIG]  [-e EVERY] [-w WINDOW]

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -e EVERY     : 何分ごとのデータを取得するか [default: 1]
  -w WINDOWE   : 算出に使うウィンドウ [default: 5]
"""

from docopt import docopt

import influxdb_client
import datetime
import os
import logging
import traceback

# NOTE: データが欠損している期間も含めてデータを敷き詰めるため，
# timedMovingAverage を使う．timedMovingAverage の計算の結果，データが後ろに
# ずれるので，あらかじめ offset を使って前にずらしておく．
FLUX_QUERY = """
from(bucket: "{bucket}")
|> range(start: {start}, stop: {stop})
    |> filter(fn:(r) => r._measurement == "{measure}")
    |> filter(fn: (r) => r.hostname == "{hostname}")
    |> filter(fn: (r) => r["_field"] == "{field}")
    |> aggregateWindow(every: {window}m, offset:-{window}m, fn: mean, createEmpty: {create_empty})
    |> fill(usePrevious: true)
    |> timedMovingAverage(every: {every}m, period: {window}m)
"""

FLUX_SUM_QUERY = """
from(bucket: "{bucket}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn:(r) => r._measurement == "{measure}")
    |> filter(fn: (r) => r.hostname == "{hostname}")
    |> filter(fn: (r) => r["_field"] == "{field}")
    |> aggregateWindow(every: {every}m, offset:-{every}m, fn: mean, createEmpty: {create_empty})
    |> filter(fn: (r) => exists r._value)
    |> fill(usePrevious: true)
    |> reduce(
        fn: (r, accumulator) => ({{sum: r._value + accumulator.sum, count: accumulator.count + 1}}),
        identity: {{sum: 0.0, count: 0}},
    )
"""


def fetch_data_impl(
    db_config,
    template,
    measure,
    hostname,
    field,
    start,
    stop,
    every,
    window,
    create_empty,
    last=False,
):
    try:
        token = os.environ.get("INFLUXDB_TOKEN", db_config["token"])

        query = template.format(
            bucket=db_config["bucket"],
            measure=measure,
            hostname=hostname,
            field=field,
            start=start,
            stop=stop,
            every=every,
            window=window,
            create_empty=str(create_empty).lower(),
        )
        if last:
            query += " |> last()"

        logging.debug("Flux query = {query}".format(query=query))
        client = influxdb_client.InfluxDBClient(
            url=db_config["url"], token=token, org=db_config["org"]
        )
        query_api = client.query_api()

        return query_api.query(query=query)
    except Exception as e:
        logging.warning(e)
        logging.warning(traceback.format_exc())
        raise


def fetch_data(
    db_config,
    measure,
    hostname,
    field,
    start="-30h",
    stop="now()",
    every_min=1,
    window_min=3,
    create_empty=True,
    last=False,
):
    logging.debug(
        (
            "Fetch data (measure: {measure}, host: {host}, field: {field}, "
            + "start: {start}, stop: {stop}, every: {every}min, window: {window}min, "
            + "create_empty: {create_empty}, last: {last})"
        ).format(
            measure=measure,
            host=hostname,
            field=field,
            start=start,
            stop=stop,
            every=every_min,
            window=window_min,
            create_empty=create_empty,
            last=last,
        )
    )

    try:
        table_list = fetch_data_impl(
            db_config,
            FLUX_QUERY,
            measure,
            hostname,
            field,
            start,
            stop,
            every_min,
            window_min,
            create_empty,
            last,
        )
        data = []
        time = []
        localtime_offset = datetime.timedelta(hours=9)

        if len(table_list) != 0:
            for record in table_list[0].records:
                # NOTE: aggregateWindow(createEmpty: true) と fill(usePrevious: true) の組み合わせ
                # だとタイミングによって，先頭に None が入る
                if record.get_value() is None:
                    logging.debug(
                        "DELETE {datetime}".format(
                            datetime=record.get_time() + localtime_offset
                        )
                    )
                    continue

                data.append(record.get_value())
                time.append(record.get_time() + localtime_offset)

        if create_empty and not last:
            # NOTE: aggregateWindow(createEmpty: true) と timedMovingAverage を使うと，
            # 末尾に余分なデータが入るので取り除く
            every_min = int(every_min)
            window_min = int(window_min)
            if window_min > every_min:
                data = data[: (every_min - window_min)]
                time = time[: (every_min - window_min)]

        logging.debug("data count = {count}".format(count=len(time)))

        return {"value": data, "time": time, "valid": len(time) != 0}
    except:
        logging.warning(traceback.format_exc())

        return {"value": [], "time": [], "valid": False}


def get_equip_on_minutes(
    config,
    measure,
    hostname,
    field,
    threshold,
    start="-30h",
    stop="now()",
    every_min=1,
    window_min=5,
    create_empty=True,
):
    logging.info(
        (
            "Get 'ON' minutes (type: {type}, host: {host}, field: {field}, "
            + "threshold: {threshold}, start: {start}, stop: {stop}, every: {every}min, "
            + "window: {window}min, create_empty: {create_empty})"
        ).format(
            type=measure,
            host=hostname,
            field=field,
            threshold=threshold,
            start=start,
            stop=stop,
            every=every_min,
            window=window_min,
            create_empty=create_empty,
        )
    )

    try:
        table_list = fetch_data_impl(
            config,
            FLUX_QUERY,
            measure,
            hostname,
            field,
            start,
            stop,
            every_min,
            window_min,
            create_empty,
        )

        if len(table_list) == 0:
            return 0

        count = 0

        every_min = int(every_min)
        window_min = int(window_min)
        record_num = len(table_list[0].records)
        for i, record in enumerate(table_list[0].records):
            if create_empty:
                # NOTE: timedMovingAverage を使うと，末尾に余分なデータが入るので取り除く
                if window_min > every_min:
                    if i > record_num - 1 - (window_min - every_min):
                        continue

            # NOTE: aggregateWindow(createEmpty: true) と fill(usePrevious: true) の組み合わせ
            # だとタイミングによって，先頭に None が入る
            if record.get_value() is None:
                continue
            if record.get_value() >= threshold:
                count += 1

        return count * int(every_min)
    except:
        logging.warning(traceback.format_exc())
        return 0


def get_equip_mode_period(
    config,
    measure,
    hostname,
    field,
    threshold_list,
    start="-30h",
    stop="now()",
    every_min=10,
    window_min=10,
    create_empty=True,
):
    logging.info(
        (
            "Get equipment mode period (type: {type}, host: {host}, field: {field}, "
            + "threshold: {threshold}, start: {start}, stop: {stop}, every: {every}min, "
            + "window: {window}min, create_empty: {create_empty})"
        ).format(
            type=measure,
            host=hostname,
            field=field,
            threshold="[{list_str}]".format(
                list_str=",".join(map(lambda v: "{:.1f}".format(v), threshold_list))
            ),
            start=start,
            stop=stop,
            every=every_min,
            window=window_min,
            create_empty=create_empty,
        )
    )

    try:
        table_list = fetch_data_impl(
            config,
            FLUX_QUERY,
            measure,
            hostname,
            field,
            start,
            stop,
            every_min,
            window_min,
            create_empty,
        )

        if len(table_list) == 0:
            return []

        # NOTE: 常時冷却と間欠冷却の期間を求める
        on_range = []
        state = -1
        start_time = None
        prev_time = None
        localtime_offset = datetime.timedelta(hours=9)

        for record in table_list[0].records:
            # NOTE: aggregateWindow(createEmpty: true) と fill(usePrevious: true) の組み合わせ
            # だとタイミングによって，先頭に None が入る
            if record.get_value() is None:
                logging.debug(
                    "DELETE {datetime}".format(
                        datetime=record.get_time() + localtime_offset
                    )
                )
                continue

            is_idle = True
            for i in range(len(threshold_list)):
                if record.get_value() > threshold_list[i]:
                    if state != i:
                        if state != -1:
                            on_range.append(
                                [
                                    start_time + localtime_offset,
                                    prev_time + localtime_offset,
                                    state,
                                ]
                            )
                        state = i
                        start_time = record.get_time()
                    is_idle = False
                    break
            if is_idle and state != -1:
                on_range.append(
                    [
                        start_time + localtime_offset,
                        prev_time + localtime_offset,
                        state,
                    ]
                )
                state = -1
                start_time = record.get_time()

            prev_time = record.get_time()

        if state != -1:
            on_range.append(
                [
                    start_time + localtime_offset,
                    table_list[0].records[-1].get_time() + localtime_offset,
                    state,
                ]
            )
        return on_range
    except:
        logging.warning(traceback.format_exc())
        return []


def get_day_sum(config, measure, hostname, field, offset_day=0):
    try:
        every_min = 1
        window_min = 5
        now = datetime.datetime.now()

        start = "-{offset_day}d{hour}h{minute}m".format(
            offset_day=offset_day, hour=now.hour, minute=now.minute
        )
        stop = "-{offset_day}d".format(offset_day=offset_day)

        table_list = fetch_data_impl(
            config,
            FLUX_SUM_QUERY,
            measure,
            hostname,
            field,
            start,
            stop,
            every_min,
            window_min,
            True,
        )

        value_list = table_list.to_values(columns=["count", "sum"])

        if len(value_list) == 0:
            return 0
        else:
            return value_list[0][1]
    except:
        logging.warning(traceback.format_exc())
        return 0


def dump_data(data):
    for i in range(len(data["time"])):
        logging.info(
            "{time}: {value}".format(time=data["time"][i], value=data["value"][i])
        )


if __name__ == "__main__":
    import logger
    import json

    from config import load_config, get_db_config

    args = docopt(__doc__)

    logger.init("test", logging.DEBUG)

    config = load_config(args["-c"])
    every = args["-e"]
    window = args["-w"]

    now = datetime.datetime.now()
    measure = config["USAGE"]["TARGET"]["TYPE"]
    hostname = config["USAGE"]["TARGET"]["HOST"]
    param = config["USAGE"]["TARGET"]["PARAM"]
    threshold = config["USAGE"]["TARGET"]["THRESHOLD"]["WORK"]
    start = "-" + config["GRAPH"]["PARAM"]["PERIOD"]

    db_config = get_db_config(config)

    dump_data(
        fetch_data(db_config, measure, hostname, param, start, "now()", every, window)
    )

    start = "-{hour}h{minute}m".format(hour=now.hour, minute=now.minute)

    logging.info(
        "Today ON minutes ({start}) = {minutes} min".format(
            start=start,
            minutes=get_equip_on_minutes(
                db_config,
                measure,
                hostname,
                param,
                threshold,
                start,
                "now()",
                every,
                window,
            ),
        )
    )

    measure = config["GRAPH"]["VALVE"]["TYPE"]
    hostname = config["GRAPH"]["VALVE"]["HOST"]
    param = config["GRAPH"]["VALVE"]["PARAM"]
    threshold = [
        # NOTE: 閾値が高いものから並べる
        config["GRAPH"]["VALVE"]["THRESHOLD"]["FULL"],
        config["GRAPH"]["VALVE"]["THRESHOLD"]["INTERM"],
    ]
    start = "-" + config["GRAPH"]["PARAM"]["PERIOD"]

    logging.info(
        "Valve on period = {range_list}".format(
            range_list=json.dumps(
                get_equip_mode_period(
                    db_config, measure, hostname, param, threshold, start, "now()"
                ),
                indent=2,
                default=str,
            )
        )
    )

    logging.info(
        "Amount of cooling water used today = {water:.2f} L".format(
            water=get_day_sum(db_config, measure, hostname, param)
        )
    )
