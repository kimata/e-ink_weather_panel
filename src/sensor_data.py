#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InfluxDB から電子機器の使用時間を取得します．

Usage:
  sensor_data.py [-f CONFIG]  [-e EVERY] [-w WINDOW]

Options:
  -f CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -e EVERY     : 何分ごとのデータを取得するか [default: 1]
  -w WINDOWE   : 算出に使うウィンドウ [default: 5]
"""

from docopt import docopt

import influxdb_client
import datetime
import os
import logging
import traceback

FLUX_QUERY = """
from(bucket: "{bucket}")
|> range(start: -{period})
    |> filter(fn:(r) => r._measurement == "{measure}")
    |> filter(fn: (r) => r.hostname == "{hostname}")
    |> filter(fn: (r) => r["_field"] == "{field}")
    |> aggregateWindow(every: {window}m, fn: mean, createEmpty: {create_empty})
    |> fill(usePrevious: true)
    |> timedMovingAverage(every: {every}m, period: {window}m)
"""

FLUX_SUM_QUERY = """
from(bucket: "{bucket}")
    |> range(start: -{period})
    |> filter(fn:(r) => r._measurement == "{measure}")
    |> filter(fn: (r) => r.hostname == "{hostname}")
    |> filter(fn: (r) => r["_field"] == "{field}")
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
    period,
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
            period=period,
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
    period="30h",
    every_min=1,
    window_min=5,
    create_empty=True,
    last=False,
):
    logging.info(
        (
            "Fetch data (measure: {measure}, host: {host}, field: {field}, "
            + "period: {period}, every: {every}min, window: {window}min, "
            + "create_empty: {create_empty}, last: {last})"
        ).format(
            measure=measure,
            host=hostname,
            field=field,
            period=period,
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
            period,
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
                    logging.info("DELETE")
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

        logging.info("data count = {count}".format(count=len(time)))

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
    period="30h",
    every_min=1,
    window_min=5,
    create_empty=True,
):
    logging.info(
        (
            "Get on minutes (type: {type}, host: {host}, field: {field}, "
            + "threshold: {threshold}, period: {period}, every: {every}min, "
            + "window: {window}min, create_empty: {create_empty})"
        ).format(
            type=measure,
            host=hostname,
            field=field,
            threshold=threshold,
            period=period,
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
            period,
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
    threshold,
    period="30h",
    every_min=1,
    window_min=3,
    create_empty=True,
):
    logging.info(
        (
            "Get equipment mode period (type: {type}, host: {host}, field: {field}, "
            + "threshold: {threshold}, period: {period}, every: {every}min, "
            + "window: {window}min, create_empty: {create_empty})"
        ).format(
            type=measure,
            host=hostname,
            field=field,
            threshold=threshold,
            period=period,
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
            period,
            every_min,
            window_min,
            create_empty,
        )

        if len(table_list) == 0:
            return []

        # NOTE: 常時冷却と間欠冷却の期間を求める
        on_range = []
        state = "IDLE"
        start_time = None
        localtime_offset = datetime.timedelta(hours=9)

        for record in table_list[0].records:
            # NOTE: aggregateWindow(createEmpty: true) と fill(usePrevious: true) の組み合わせ
            # だとタイミングによって，先頭に None が入る
            if record.get_value() is None:
                continue

            if record.get_value() > threshold["FULL"]:
                if state != "FULL":
                    if state == "INTERM":
                        on_range.append(
                            [
                                start_time + localtime_offset,
                                record.get_time() + localtime_offset,
                                False,
                            ]
                        )
                    state = "FULL"
                    start_time = record.get_time()
            elif record.get_value() > threshold["INTERM"]:
                if state != "INTERM":
                    if state == "FULL":
                        on_range.append(
                            [
                                start_time + localtime_offset,
                                record.get_time() + localtime_offset,
                                True,
                            ]
                        )
                    state = "INTERM"
                    start_time = record.get_time()
            else:
                if state != "IDLE":
                    on_range.append(
                        [
                            start_time + localtime_offset,
                            record.get_time() + localtime_offset,
                            state == "FULL",
                        ]
                    )
                state = "IDLE"

        if state != "IDLE":
            on_range.append(
                [
                    start_time + localtime_offset,
                    table_list[0].records[-1].get_time() + localtime_offset,
                    state == "FULL",
                ]
            )

        return on_range
    except:
        logging.warning(traceback.format_exc())
        return []


def get_today_sum(config, measure, hostname, field):
    try:
        now = datetime.datetime.now()

        period = "{hour}h{minute}m".format(hour=now.hour, minute=now.minute)

        table_list = fetch_data_impl(
            config, FLUX_SUM_QUERY, measure, hostname, field, period
        )

        count, total = table_list.to_values(columns=["count", "sum"])[0]

        return total * (((now.hour * 60 + now.minute) * 60.0) / count) / 60
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

    from config import load_config

    args = docopt(__doc__)

    logger.init("test", logging.DEBUG)

    config = load_config(args["-f"])
    every = args["-e"]
    window = args["-w"]

    now = datetime.datetime.now()
    measure = config["USAGE"]["TARGET"]["TYPE"]
    hostname = config["USAGE"]["TARGET"]["HOST"]
    field = config["USAGE"]["TARGET"]["FIELD"]
    threshold = config["USAGE"]["TARGET"]["THRESHOLD"]["WORK"]
    period = config["GRAPH"]["FIELD"]["PERIOD"]

    db_config = {
        "token": config["INFLUXDB"]["TOKEN"],
        "bucket": config["INFLUXDB"]["BUCKET"],
        "url": config["INFLUXDB"]["URL"],
        "org": config["INFLUXDB"]["ORG"],
    }

    dump_data(
        fetch_data(config["INFLUXDB"], measure, hostname, field, period, every, window)
    )

    period = "{hour}h{minute}m".format(hour=now.hour, minute=now.minute)

    logging.info(
        "Today ON minutes ({period}) = {minutes} min".format(
            period=period,
            minutes=get_equip_on_minutes(
                config["INFLUXDB"],
                measure,
                hostname,
                field,
                threshold,
                period,
                every,
                window,
            ),
        )
    )

    measure = config["GRAPH"]["VALVE"]["TYPE"]
    hostname = config["GRAPH"]["VALVE"]["HOST"]
    field = config["GRAPH"]["VALVE"]["FIELD"]
    threshold = config["GRAPH"]["VALVE"]["THRESHOLD"]
    period = config["GRAPH"]["FIELD"]["PERIOD"]

    logging.info(
        "Valve on period = {range_list}".format(
            range_list=json.dumps(
                get_equip_mode_period(
                    config["INFLUXDB"], measure, hostname, field, threshold, period
                ),
                indent=2,
                default=str,
            )
        )
    )

    # logging.info(
    #     "Amount of cooling water used today = {water:0f} L".format(
    #         water=get_today_sum(config["INFLUXDB"], measure, hostname, field)
    #     )
    # )
