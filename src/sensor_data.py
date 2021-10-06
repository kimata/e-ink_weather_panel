#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from influxdb import InfluxDBClient
import datetime
import dateutil.parser

INFLUXDB_QUERY = """
SELECT mean("{param}") FROM "sensor.{sensor_type}" WHERE ("hostname" = \'{hostname}\') AND time >= now() - {period} GROUP BY time(3m) fill(previous) ORDER by time asc
"""


def fetch_data(config, sensor_type, hostname, param, period='60h'):
    client = InfluxDBClient(
        host=config['ADDR'], port=config['PORT'], database=config['DB']
    )
    result = client.query(INFLUXDB_QUERY.format(
        sensor_type=sensor_type, hostname=hostname, param=param, period=period)
    )

    data = list(map(lambda x: x['mean'], result.get_points()))

    localtime_offset = datetime.timedelta(hours=9)
    time = list(map(lambda x: dateutil.parser.parse(x['time'])+localtime_offset, result.get_points()))

    return {
        'value': data,
        'time': time,
        'valid': len(time) != 0
    }
