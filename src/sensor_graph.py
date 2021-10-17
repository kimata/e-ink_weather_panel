#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib
import os
import datetime
import io
import matplotlib
import pprint
import PIL.Image

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.offsetbox import (AnnotationBbox, OffsetImage)
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
from matplotlib.font_manager import FontProperties

from sensor_data import fetch_data

IMAGE_DPI = 100.0
EMPTY_VALUE = -100.0

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


def plot_item(ax, title, unit, data, ylabel, ylim, fmt, scale, small, face_map):
    x = data['time']
    y = data['value']

    if not data['valid']:
        text = '?'
    else:
        text = fmt.format(next((item for item in reversed(y) if item is not None), None))

    if (scale == 'log'):
        # NOTE: エラーが出ないように値を補正
        y = [1 if (i is None or i<1) else i for i in y]

    if title is not None:
        ax.set_title(title, fontproperties=face_map['title'], color='#333333')

    ax.set_ylim(ylim)
    ax.set_xlim([x[0], x[-1] + datetime.timedelta(hours=3)])
    ax.set_yscale(scale)

    ax.plot(x, y, '.', color='#AAAAAA',
            marker='o', markevery=[len(y)-1],
            markersize=5, markerfacecolor='#cccccc', markeredgewidth=3, markeredgecolor='#666666',
            linewidth=3.0, linestyle='solid')

    if small:
        font = face_map['value_small']
    else:
        font = face_map['value']

    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%-d'))
    for label in ax.get_xticklabels():
        label.set_fontproperties(face_map['axis'])

    ax.set_ylabel(unit)
    ax.set_yscale(scale)

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

def draw_light_icon(config, ax, y):
    lux = next((item for item in reversed(y) if item is not None), None)

    now = datetime.datetime.now()
    # NOTE: 昼間はアイコンを描画しない
    if (now.hour > 7) and (now.hour < 18):
        return

    if (lux == EMPTY_VALUE):
        return
    elif (lux < 10):
        icon_file =config['LIGHT']['OFF']
    else:
        icon_file =config['LIGHT']['ON']

    img = plt.imread(str(pathlib.Path(os.path.dirname(__file__), icon_file)))

    imagebox = OffsetImage(img, zoom=0.25)
    imagebox.image.axes = ax

    ab = AnnotationBbox(
        offsetbox=imagebox,
        box_alignment=(0, 1),
        xycoords='axes fraction',
        xy=(0, 1),
        frameon=False,
    )
    ax.add_artist(ab)


def sensor_data(config, host_specify_list, param, period='60h'):
    for host_specify in host_specify_list:
        data = fetch_data(config, host_specify['TYPE'], host_specify['NAME'], param, period)
        if data['valid']:
            return data
    return data


def create_sensor_graph(db_config, config, font_config):
    face_map = get_face_map(font_config)
    
    room_list = config['ROOM_LIST']
    width = config['WIDTH']
    height = config['HEIGHT']

    plt.style.use('grayscale')

    fig = plt.figure(facecolor="azure", edgecolor="coral", linewidth=2)

    fig.set_size_inches(width/IMAGE_DPI, height/IMAGE_DPI)

    cache = None
    range_map = {}
    for row, param in enumerate(config['PARAM_LIST']):
        param_min = float('inf')
        param_max = -float('inf')

        for col in range(0, len(room_list)):
            data = sensor_data(
                db_config,
                room_list[col]['HOST'],
                param['NAME'],
            )
            if cache is None:
                cache = {
                    'time': data['time'],
                    'value': [EMPTY_VALUE for x in range(len(data['time']))],
                    'valid': False,
                }
            if len(data['value']) == 0:
                continue

            min_val = min([item for item in data['value'] if item is not None])
            max_val = max([item for item in data['value'] if item is not None])
            if (min_val < param_min):
                param_min = min_val
            if (max_val > param_max):
                param_max = max_val

        range_map[param['NAME']] = [param_min, param_max]

    for row, param in enumerate(config['PARAM_LIST']):
        for col in range(0, len(room_list)):
            data = sensor_data(
                db_config,
                room_list[col]['HOST'],
                param['NAME'],
            )
            if not data['valid']:
                data = cache

            ax = fig.add_subplot(len(config['PARAM_LIST']),
                                 len(room_list), 1 + len(room_list)*row + col)

            if row == 0:
                title = room_list[col]['LABEL']
            else:
                title = None

            if (param['RANGE'] == 'auto'):
                graph_range = range_map[param['NAME']]
            else:
                graph_range = param['RANGE']

            plot_item(
                ax,
                title, param['UNIT'], data,
                param['UNIT'], graph_range, param['FORMAT'],
                param['SCALE'], param['SIZE_SMALL'],
                face_map
            )

            if (param['NAME'] == 'lux'):
                draw_light_icon(config['ICON'], ax, data['value'])

    fig.tight_layout()
    plt.subplots_adjust(hspace=0.1, wspace=0)
        
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=IMAGE_DPI)

    return PIL.Image.open(buf)
