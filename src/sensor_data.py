#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import influxdb_client

import os
import datetime
import logging
import traceback

FLUX_QUERY = """
from(bucket: "{bucket}")
    |> range(start: -{period})
    |> filter(fn:(r) => r._measurement == "sensor.{sensor_type}")
    |> filter(fn: (r) => r.hostname == "{hostname}")
    |> filter(fn: (r) => r["_field"] == "{param}")
    |> aggregateWindow(every: 3m, fn: mean, createEmpty: false)
    |> exponentialMovingAverage(n: 3)
"""


def fetch_data(config, sensor_type, hostname, param, period="60h"):
    token = os.environ.get("INFLUXDB_TOKEN", config["TOKEN"])
    query = FLUX_QUERY.format(
        bucket=config["BUCKET"],
        sensor_type=sensor_type,
        hostname=hostname,
        param=param,
        period=period,
    )
    try:
        client = influxdb_client.InfluxDBClient(
            url=config["URL"], token=token, org=config["ORG"]
        )

        query_api = client.query_api()

        table_list = query_api.query(query=query)

        data = []
        time = []
        localtime_offset = datetime.timedelta(hours=9)

        if len(table_list) != 0:
            for record in table_list[0].records:
                data.append(record.get_value())
                time.append(record.get_time() + localtime_offset)

        return {"value": data, "time": time, "valid": len(time) != 0}
    except:
        logging.error(traceback.format_exc())
        logging.error("Flux query = {query}".format(query=query))
        return {"value": [], "time": [], "valid": False}
