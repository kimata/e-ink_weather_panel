#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib
import os
from influxdb import InfluxDBClient
import datetime
import dateutil.parser
import io
import matplotlib
import pprint
import PIL.Image

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
from matplotlib.font_manager import FontProperties

INFLUXDB_ADDR = '192.168.0.10'
INFLUXDB_PORT = 8086
INFLUXDB_DB = 'sensor'

INFLUXDB_QUERY = """
SELECT mean("{param}") FROM "sensor.{sensor_type}" WHERE ("hostname" = \'{hostname}\') AND time >= now() - 60h GROUP BY time(3m) fill(previous) ORDER by time asc
"""

IMAGE_DPI = 100.0

def fetch_data(sensor_type, hostname, param):
    client = InfluxDBClient(
        host=INFLUXDB_ADDR, port=INFLUXDB_PORT, database=INFLUXDB_DB
    )
    result = client.query(INFLUXDB_QUERY.format(
        sensor_type=sensor_type, hostname=hostname, param=param)
    )

    data = list(map(lambda x: x['mean'], result.get_points()))

    localtime_offset = datetime.timedelta(hours=9)
    time = list(map(lambda x: dateutil.parser.parse(x['time'])+localtime_offset, result.get_points()))

    return {
        'value': data,
        'time': time,
        'valid': len(time) != 0
    }


def get_plot_font(config, font_type, size):
    return FontProperties(
        fname=str(
            pathlib.Path(
                os.path.dirname(__file__),
                config['PATH'], config['MAP'][font_type]
            )
        ),
        size=size
    )


def get_face_map(font_config):
    return {
        'title': get_plot_font(font_config, 'JP_BOLD', 30),
        'value': get_plot_font(font_config, 'EN_COND_BOLD', 60),
        'value_small': get_plot_font(font_config, 'EN_COND_BOLD', 40),
        'value_unit': get_plot_font(font_config, 'JP_REGULAR', 18),
        'axis': get_plot_font(font_config, 'EN_COND', 16),
    }


def plot_item(ax, title, unit, data, ylabel, ylim, fmt, small, face_map):
    x = data['time']
    y = data['value']

    if title is not None:
        ax.set_title(title, fontproperties=face_map['title'], color='#333333')
    ax.set_ylim(ylim)
    ax.set_xlim([x[0], x[-1] + datetime.timedelta(hours=3)])

    ax.plot(x, y, '.', color='#AAAAAA',
            marker='o', markevery=[len(y)-1],
            markersize=5, markerfacecolor='#cccccc', markeredgewidth=3, markeredgecolor='#666666',
            linewidth=3.0, linestyle='solid')

    if not data['valid']:
        text = '?'
    else:
        text = fmt.format(next((item for item in reversed(y) if item), None))

    if small:
        font = face_map['value_small']
    else:
        font = face_map['value']

    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%-d'))
    for label in ax.get_xticklabels():
        label.set_fontproperties(face_map['axis'])

    ax.set_ylabel(unit)

    ax.grid(axis='x', color='#000000', alpha=0.1,
            linestyle='-', linewidth=1)

    ax.text(0.90-len(unit)*0.1, 0.05, text,
            transform=ax.transAxes, horizontalalignment='right',
            color='#000000', alpha=0.8,
            fontproperties=font)

    ax.text(0.96, 0.05, unit,
            transform=ax.transAxes, horizontalalignment='right',
            color='#000000', alpha=0.8,
            fontproperties=face_map['value_unit'])
    
    ax.label_outer()


def create_sensor_graph(config, font_config):
    face_map = get_face_map(font_config)
    
    room_list = config['ROOM_LIST']
    width = config['WIDTH']
    height = config['HEIGHT']

    plt.style.use('grayscale')

    fig = plt.figure(facecolor="azure", edgecolor="coral", linewidth=2)

    fig.set_size_inches(width/IMAGE_DPI, height/IMAGE_DPI)

    cache = None
    for row, param in enumerate(config['PARAM_LIST']):
        for col in range(0, len(room_list)):
            data = fetch_data(
                room_list[col]['TYPE'],
                room_list[col]['HOST'],
                param['NAME'],
            )

            if not data['valid']:
                data = cache
            elif cache is None:
                cache = {
                    'time': data['time'],
                    'value': [-100.0 for x in range(len(data['time']))],
                    'valid': False,
                }

            ax = fig.add_subplot(3, len(room_list), 1 + len(room_list)*row + col)

            if row == 0:
                title = room_list[col]['LABEL']
            else:
                title = None

            plot_item(
                ax,
                title, param['UNIT'], data,
                param['UNIT'], param['RANGE'], param['FORMAT'],
                param['SIZE_SMALL'],
                face_map
            )

    fig.tight_layout()
    plt.subplots_adjust(hspace=0.1, wspace=0)
        
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=IMAGE_DPI)

    return PIL.Image.open(buf)
