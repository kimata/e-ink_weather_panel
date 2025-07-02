#!/usr/bin/env python3


def generate_chart_javascript():
    """Chart.js用のJavaScriptコードを生成する"""
    return """
        function generateHourlyCharts() {
            // 画像生成パネル 時間別パフォーマンス
            const drawPanelCtx = document.getElementById('drawPanelHourlyChart');
            if (drawPanelCtx && hourlyData.draw_panel) {
                new Chart(drawPanelCtx, {
                    type: 'line',
                    data: {
                        labels: hourlyData.draw_panel.map(d => d.hour + '時'),
                        datasets: [{
                            label: '平均処理時間（秒）',
                            data: hourlyData.draw_panel.map(d => d.avg_elapsed_time),
                            borderColor: 'rgb(75, 192, 192)',
                            backgroundColor: 'rgba(75, 192, 192, 0.2)',
                            tension: 0.1,
                            yAxisID: 'y',
                            borderWidth: 3,
                            pointRadius: 4,
                            pointHoverRadius: 6
                        }, {
                            label: '最小処理時間（秒）',
                            data: hourlyData.draw_panel.map(d => d.min_elapsed_time),
                            borderColor: 'rgb(34, 197, 94)',
                            backgroundColor: 'rgba(34, 197, 94, 0.1)',
                            tension: 0.1,
                            yAxisID: 'y',
                            borderDash: [8, 4],
                            borderWidth: 2,
                            pointRadius: 3,
                            pointHoverRadius: 5
                        }, {
                            label: '最大処理時間（秒）',
                            data: hourlyData.draw_panel.map(d => d.max_elapsed_time),
                            borderColor: 'rgb(239, 68, 68)',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            tension: 0.1,
                            yAxisID: 'y',
                            borderDash: [4, 4],
                            borderWidth: 2,
                            pointRadius: 3,
                            pointHoverRadius: 5
                        }, {
                            label: 'エラー率（%）',
                            data: hourlyData.draw_panel.map(d => d.error_rate || 0),
                            borderColor: 'rgb(255, 99, 132)',
                            backgroundColor: 'rgba(255, 99, 132, 0.2)',
                            tension: 0.1,
                            yAxisID: 'y1'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: 'index',
                            intersect: false
                        },
                        plugins: {
                            legend: {
                                position: 'top',
                                labels: {
                                    usePointStyle: true,
                                    padding: 8,
                                    font: {
                                        size: 12
                                    }
                                }
                            },
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: 'white',
                                bodyColor: 'white',
                                borderColor: 'rgba(255, 255, 255, 0.3)',
                                borderWidth: 1,
                                callbacks: {
                                    title: function(context) {
                                        return '時刻: ' + context[0].label;
                                    },
                                    label: function(context) {
                                        let label = context.dataset.label || '';
                                        if (label) {
                                            label += ': ';
                                        }
                                        if (context.parsed.y !== null) {
                                            if (context.dataset.yAxisID === 'y1') {
                                                label += context.parsed.y.toFixed(1) + '%';
                                            } else {
                                                label += context.parsed.y.toFixed(2) + '秒';
                                            }
                                        }
                                        return label;
                                    },
                                    afterBody: function(context) {
                                        if (context.length > 0) {
                                            const dataIndex = context[0].dataIndex;
                                            const hourData = hourlyData.draw_panel[dataIndex];
                                            if (hourData) {
                                                return '実行回数: ' + (hourData.count || 0) + '回';
                                            }
                                        }
                                        return '';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                display: true,
                                grid: {
                                    color: 'rgba(0, 0, 0, 0.1)',
                                    display: true
                                },
                                title: {
                                    display: true,
                                    text: '時間',
                                    font: {
                                        size: 14,
                                        weight: 'bold'
                                    }
                                }
                            },
                            y: {
                                type: 'linear',
                                display: true,
                                position: 'left',
                                title: {
                                    display: true,
                                    text: '処理時間（秒）',
                                    font: {
                                        size: 14,
                                        weight: 'bold'
                                    }
                                },
                                grid: {
                                    color: 'rgba(75, 192, 192, 0.2)'
                                }
                            },
                            y1: {
                                type: 'linear',
                                display: true,
                                position: 'right',
                                title: {
                                    display: true,
                                    text: 'エラー率（%）',
                                    font: {
                                        size: 14,
                                        weight: 'bold'
                                    }
                                },
                                grid: {
                                    drawOnChartArea: false,
                                    color: 'rgba(255, 99, 132, 0.2)'
                                }
                            }
                        }
                    }
                });
            }

            // 表示実行 時間別パフォーマンス
            const displayImageCtx = document.getElementById('displayImageHourlyChart');
            if (displayImageCtx && hourlyData.display_image) {
                new Chart(displayImageCtx, {
                    type: 'line',
                    data: {
                        labels: hourlyData.display_image.map(d => d.hour + '時'),
                        datasets: [{
                            label: '平均処理時間（秒）',
                            data: hourlyData.display_image.map(d => d.avg_elapsed_time),
                            borderColor: 'rgb(54, 162, 235)',
                            backgroundColor: 'rgba(54, 162, 235, 0.2)',
                            tension: 0.1,
                            yAxisID: 'y',
                            borderWidth: 3,
                            pointRadius: 4,
                            pointHoverRadius: 6
                        }, {
                            label: '最小処理時間（秒）',
                            data: hourlyData.display_image.map(d => d.min_elapsed_time),
                            borderColor: 'rgb(34, 197, 94)',
                            backgroundColor: 'rgba(34, 197, 94, 0.1)',
                            tension: 0.1,
                            yAxisID: 'y',
                            borderDash: [8, 4],
                            borderWidth: 2,
                            pointRadius: 3,
                            pointHoverRadius: 5
                        }, {
                            label: '最大処理時間（秒）',
                            data: hourlyData.display_image.map(d => d.max_elapsed_time),
                            borderColor: 'rgb(239, 68, 68)',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            tension: 0.1,
                            yAxisID: 'y',
                            borderDash: [4, 4],
                            borderWidth: 2,
                            pointRadius: 3,
                            pointHoverRadius: 5
                        }, {
                            label: 'エラー率（%）',
                            data: hourlyData.display_image.map(d => d.error_rate || 0),
                            borderColor: 'rgb(255, 99, 132)',
                            backgroundColor: 'rgba(255, 99, 132, 0.2)',
                            tension: 0.1,
                            yAxisID: 'y1'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: 'white',
                                bodyColor: 'white',
                                borderColor: 'rgba(255, 255, 255, 0.3)',
                                borderWidth: 1,
                                callbacks: {
                                    title: function(context) {
                                        return '時刻: ' + context[0].label;
                                    },
                                    label: function(context) {
                                        let label = context.dataset.label || '';
                                        if (label) {
                                            label += ': ';
                                        }
                                        if (context.parsed.y !== null) {
                                            if (context.dataset.yAxisID === 'y1') {
                                                label += context.parsed.y.toFixed(1) + '%';
                                            } else {
                                                label += context.parsed.y.toFixed(2) + '秒';
                                            }
                                        }
                                        return label;
                                    },
                                    afterBody: function(context) {
                                        if (context.length > 0) {
                                            const dataIndex = context[0].dataIndex;
                                            const hourData = hourlyData.display_image[dataIndex];
                                            if (hourData) {
                                                return '実行回数: ' + (hourData.count || 0) + '回';
                                            }
                                        }
                                        return '';
                                    }
                                }
                            }
                        },
                        scales: {
                            y: {
                                type: 'linear',
                                display: true,
                                position: 'left',
                                title: { display: true, text: '処理時間（秒）' }
                            },
                            y1: {
                                type: 'linear',
                                display: true,
                                position: 'right',
                                title: { display: true, text: 'エラー率（%）' },
                                grid: { drawOnChartArea: false }
                            }
                        }
                    }
                });
            }
        }

        function generateDiffSecCharts() {
            // 表示タイミング 時間別パフォーマンス
            const diffSecCtx = document.getElementById('diffSecHourlyChart');
            if (diffSecCtx && hourlyData.diff_sec) {
                new Chart(diffSecCtx, {
                    type: 'line',
                    data: {
                        labels: hourlyData.diff_sec.map(d => d.hour + '時'),
                        datasets: [{
                            label: '平均タイミング差（秒）',
                            data: hourlyData.diff_sec.map(d => d.avg_diff_sec),
                            borderColor: 'rgb(255, 159, 64)',
                            backgroundColor: 'rgba(255, 159, 64, 0.2)',
                            tension: 0.1,
                            borderWidth: 3,
                            pointRadius: 4,
                            pointHoverRadius: 6
                        }, {
                            label: '最小タイミング差（秒）',
                            data: hourlyData.diff_sec.map(d => d.min_diff_sec),
                            borderColor: 'rgb(34, 197, 94)',
                            backgroundColor: 'rgba(34, 197, 94, 0.1)',
                            tension: 0.1,
                            borderDash: [8, 4],
                            borderWidth: 2,
                            pointRadius: 3,
                            pointHoverRadius: 5
                        }, {
                            label: '最大タイミング差（秒）',
                            data: hourlyData.diff_sec.map(d => d.max_diff_sec),
                            borderColor: 'rgb(239, 68, 68)',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            tension: 0.1,
                            borderDash: [4, 4],
                            borderWidth: 2,
                            pointRadius: 3,
                            pointHoverRadius: 5
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: 'index',
                            intersect: false
                        },
                        plugins: {
                            legend: {
                                position: 'top',
                                labels: {
                                    usePointStyle: true,
                                    padding: 8,
                                    font: {
                                        size: 12
                                    }
                                }
                            },
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: 'white',
                                bodyColor: 'white',
                                borderColor: 'rgba(255, 255, 255, 0.3)',
                                borderWidth: 1,
                                callbacks: {
                                    title: function(context) {
                                        return '時刻: ' + context[0].label;
                                    },
                                    label: function(context) {
                                        let label = context.dataset.label || '';
                                        if (label) {
                                            label += ': ';
                                        }
                                        if (context.parsed.y !== null) {
                                            label += context.parsed.y.toFixed(1) + '秒';
                                        }
                                        return label;
                                    },
                                    afterBody: function(context) {
                                        if (context.length > 0) {
                                            const dataIndex = context[0].dataIndex;
                                            const hourData = hourlyData.diff_sec[dataIndex];
                                            if (hourData) {
                                                return '実行回数: ' + (hourData.count || 0) + '回';
                                            }
                                        }
                                        return '';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                display: true,
                                grid: {
                                    color: 'rgba(0, 0, 0, 0.1)',
                                    display: true
                                },
                                title: {
                                    display: true,
                                    text: '時間',
                                    font: {
                                        size: 14,
                                        weight: 'bold'
                                    }
                                }
                            },
                            y: {
                                type: 'linear',
                                display: true,
                                position: 'left',
                                title: {
                                    display: true,
                                    text: 'タイミング差（秒）',
                                    font: {
                                        size: 14,
                                        weight: 'bold'
                                    }
                                },
                                grid: {
                                    color: 'rgba(255, 159, 64, 0.2)'
                                }
                            }
                        }
                    }
                });
            }

            // 表示タイミング 箱ひげ図
            const diffSecBoxplotCtx = document.getElementById('diffSecBoxplotChart');
            if (diffSecBoxplotCtx && hourlyData.diff_sec_boxplot) {
                const boxplotData = [];
                for (let hour = 0; hour < 24; hour++) {
                    if (hourlyData.diff_sec_boxplot[hour]) {
                        boxplotData.push({
                            x: hour + '時',
                            y: hourlyData.diff_sec_boxplot[hour]
                        });
                    }
                }

                new Chart(diffSecBoxplotCtx, {
                    type: 'boxplot',
                    data: {
                        labels: boxplotData.map(d => d.x),
                        datasets: [{
                            label: 'タイミング差分布（秒）',
                            data: boxplotData.map(d => d.y),
                            backgroundColor: 'rgba(255, 159, 64, 0.6)',
                            borderColor: 'rgb(255, 159, 64)',
                            borderWidth: 2,
                            outlierColor: 'rgb(239, 68, 68)',
                            medianColor: 'rgb(255, 193, 7)'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'top'
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: 'white',
                                bodyColor: 'white',
                                callbacks: {
                                    title: function(context) {
                                        return '時刻: ' + context[0].label;
                                    },
                                    label: function(context) {
                                        const stats = context.parsed;
                                        return [
                                            '最小値: ' + stats.min.toFixed(1) + '秒',
                                            '第1四分位: ' + stats.q1.toFixed(1) + '秒',
                                            '中央値: ' + stats.median.toFixed(1) + '秒',
                                            '第3四分位: ' + stats.q3.toFixed(1) + '秒',
                                            '最大値: ' + stats.max.toFixed(1) + '秒'
                                        ];
                                    },
                                    afterBody: function(context) {
                                        if (context.length > 0) {
                                            const outliers = context[0].parsed.outliers || [];
                                            if (outliers.length > 0) {
                                                return '外れ値: ' + outliers.length + '個';
                                            }
                                        }
                                        return '';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '時間',
                                    font: {
                                        size: 14,
                                        weight: 'bold'
                                    }
                                }
                            },
                            y: {
                                display: true,
                                title: {
                                    display: true,
                                    text: 'タイミング差（秒）',
                                    font: {
                                        size: 14,
                                        weight: 'bold'
                                    }
                                }
                            }
                        }
                    }
                });
            }
        }

        function generateBoxplotCharts() {
            // 画像生成処理 箱ひげ図
            const drawPanelBoxplotCtx = document.getElementById('drawPanelBoxplotChart');
            if (drawPanelBoxplotCtx && hourlyData.draw_panel_boxplot) {
                const boxplotData = [];
                for (let hour = 0; hour < 24; hour++) {
                    if (hourlyData.draw_panel_boxplot[hour]) {
                        boxplotData.push({
                            x: hour + '時',
                            y: hourlyData.draw_panel_boxplot[hour]
                        });
                    }
                }

                new Chart(drawPanelBoxplotCtx, {
                    type: 'boxplot',
                    data: {
                        labels: boxplotData.map(d => d.x),
                        datasets: [{
                            label: '処理時間分布（秒）',
                            data: boxplotData.map(d => d.y),
                            backgroundColor: 'rgba(75, 192, 192, 0.6)',
                            borderColor: 'rgb(75, 192, 192)',
                            borderWidth: 2,
                            outlierColor: 'rgb(239, 68, 68)',
                            medianColor: 'rgb(255, 193, 7)'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'top'
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: 'white',
                                bodyColor: 'white',
                                callbacks: {
                                    title: function(context) {
                                        return '時刻: ' + context[0].label;
                                    },
                                    label: function(context) {
                                        const stats = context.parsed;
                                        return [
                                            '最小値: ' + stats.min.toFixed(2) + '秒',
                                            '第1四分位: ' + stats.q1.toFixed(2) + '秒',
                                            '中央値: ' + stats.median.toFixed(2) + '秒',
                                            '第3四分位: ' + stats.q3.toFixed(2) + '秒',
                                            '最大値: ' + stats.max.toFixed(2) + '秒'
                                        ];
                                    },
                                    afterBody: function(context) {
                                        if (context.length > 0) {
                                            const outliers = context[0].parsed.outliers || [];
                                            if (outliers.length > 0) {
                                                return '外れ値: ' + outliers.length + '個';
                                            }
                                        }
                                        return '';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '時間',
                                    font: {
                                        size: 14,
                                        weight: 'bold'
                                    }
                                }
                            },
                            y: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '処理時間（秒）',
                                    font: {
                                        size: 14,
                                        weight: 'bold'
                                    }
                                }
                            }
                        }
                    }
                });
            }

            // 表示実行処理 箱ひげ図
            const displayImageBoxplotCtx = document.getElementById('displayImageBoxplotChart');
            if (displayImageBoxplotCtx && hourlyData.display_image_boxplot) {
                const boxplotData = [];
                for (let hour = 0; hour < 24; hour++) {
                    if (hourlyData.display_image_boxplot[hour]) {
                        boxplotData.push({
                            x: hour + '時',
                            y: hourlyData.display_image_boxplot[hour]
                        });
                    }
                }

                new Chart(displayImageBoxplotCtx, {
                    type: 'boxplot',
                    data: {
                        labels: boxplotData.map(d => d.x),
                        datasets: [{
                            label: '処理時間分布（秒）',
                            data: boxplotData.map(d => d.y),
                            backgroundColor: 'rgba(54, 162, 235, 0.6)',
                            borderColor: 'rgb(54, 162, 235)',
                            borderWidth: 2,
                            outlierColor: 'rgb(239, 68, 68)',
                            medianColor: 'rgb(255, 193, 7)'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'top'
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: 'white',
                                bodyColor: 'white',
                                callbacks: {
                                    title: function(context) {
                                        return '時刻: ' + context[0].label;
                                    },
                                    label: function(context) {
                                        const stats = context.parsed;
                                        return [
                                            '最小値: ' + stats.min.toFixed(2) + '秒',
                                            '第1四分位: ' + stats.q1.toFixed(2) + '秒',
                                            '中央値: ' + stats.median.toFixed(2) + '秒',
                                            '第3四分位: ' + stats.q3.toFixed(2) + '秒',
                                            '最大値: ' + stats.max.toFixed(2) + '秒'
                                        ];
                                    },
                                    afterBody: function(context) {
                                        if (context.length > 0) {
                                            const outliers = context[0].parsed.outliers || [];
                                            if (outliers.length > 0) {
                                                return '外れ値: ' + outliers.length + '個';
                                            }
                                        }
                                        return '';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '時間',
                                    font: {
                                        size: 14,
                                        weight: 'bold'
                                    }
                                }
                            },
                            y: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '処理時間（秒）',
                                    font: {
                                        size: 14,
                                        weight: 'bold'
                                    }
                                }
                            }
                        }
                    }
                });
            }
        }

        function generateTrendsCharts() {
            // 画像生成パネル 推移（箱ヒゲ図）
            const drawPanelTrendsCtx = document.getElementById('drawPanelTrendsChart');
            if (drawPanelTrendsCtx && trendsData.draw_panel_boxplot) {
                const boxplotData = trendsData.draw_panel_boxplot.map(d => ({
                    x: d.date,
                    y: d.elapsed_times
                }));

                new Chart(drawPanelTrendsCtx, {
                    type: 'boxplot',
                    data: {
                        labels: boxplotData.map(d => d.x),
                        datasets: [{
                            label: '処理時間分布（秒）',
                            data: boxplotData.map(d => d.y),
                            backgroundColor: 'rgba(75, 192, 192, 0.6)',
                            borderColor: 'rgb(75, 192, 192)',
                            borderWidth: 2,
                            outlierColor: 'rgb(239, 68, 68)',
                            medianColor: 'rgb(255, 193, 7)'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: false
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: 'white',
                                bodyColor: 'white',
                                callbacks: {
                                    title: function(context) {
                                        return '日付: ' + context[0].label;
                                    },
                                    label: function(context) {
                                        const stats = context.parsed;
                                        return [
                                            '最小値: ' + stats.min.toFixed(2) + '秒',
                                            '第1四分位: ' + stats.q1.toFixed(2) + '秒',
                                            '中央値: ' + stats.median.toFixed(2) + '秒',
                                            '第3四分位: ' + stats.q3.toFixed(2) + '秒',
                                            '最大値: ' + stats.max.toFixed(2) + '秒'
                                        ];
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '日付',
                                    font: {
                                        size: 12,
                                        weight: 'bold'
                                    }
                                },
                                ticks: {
                                    maxRotation: 45,
                                    minRotation: 45
                                }
                            },
                            y: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '時間（秒）',
                                    font: {
                                        size: 12,
                                        weight: 'bold'
                                    }
                                }
                            }
                        }
                    }
                });
            }

            // 表示実行 推移（箱ヒゲ図）
            const displayImageTrendsCtx = document.getElementById('displayImageTrendsChart');
            if (displayImageTrendsCtx && trendsData.display_image_boxplot) {
                const boxplotData = trendsData.display_image_boxplot.map(d => ({
                    x: d.date,
                    y: d.elapsed_times
                }));

                new Chart(displayImageTrendsCtx, {
                    type: 'boxplot',
                    data: {
                        labels: boxplotData.map(d => d.x),
                        datasets: [{
                            label: '処理時間分布（秒）',
                            data: boxplotData.map(d => d.y),
                            backgroundColor: 'rgba(54, 162, 235, 0.6)',
                            borderColor: 'rgb(54, 162, 235)',
                            borderWidth: 2,
                            outlierColor: 'rgb(239, 68, 68)',
                            medianColor: 'rgb(255, 193, 7)'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: false
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: 'white',
                                bodyColor: 'white',
                                callbacks: {
                                    title: function(context) {
                                        return '日付: ' + context[0].label;
                                    },
                                    label: function(context) {
                                        const stats = context.parsed;
                                        return [
                                            '最小値: ' + stats.min.toFixed(2) + '秒',
                                            '第1四分位: ' + stats.q1.toFixed(2) + '秒',
                                            '中央値: ' + stats.median.toFixed(2) + '秒',
                                            '第3四分位: ' + stats.q3.toFixed(2) + '秒',
                                            '最大値: ' + stats.max.toFixed(2) + '秒'
                                        ];
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '日付',
                                    font: {
                                        size: 12,
                                        weight: 'bold'
                                    }
                                },
                                ticks: {
                                    maxRotation: 45,
                                    minRotation: 45
                                }
                            },
                            y: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '時間（秒）',
                                    font: {
                                        size: 12,
                                        weight: 'bold'
                                    }
                                }
                            }
                        }
                    }
                });
            }

            // 表示タイミング 推移（箱ヒゲ図）
            const diffSecTrendsCtx = document.getElementById('diffSecTrendsChart');
            if (diffSecTrendsCtx && trendsData.diff_sec_boxplot) {
                const boxplotData = trendsData.diff_sec_boxplot.map(d => ({
                    x: d.date,
                    y: d.diff_secs
                }));

                new Chart(diffSecTrendsCtx, {
                    type: 'boxplot',
                    data: {
                        labels: boxplotData.map(d => d.x),
                        datasets: [{
                            label: 'タイミング差分布（秒）',
                            data: boxplotData.map(d => d.y),
                            backgroundColor: 'rgba(255, 159, 64, 0.6)',
                            borderColor: 'rgb(255, 159, 64)',
                            borderWidth: 2,
                            outlierColor: 'rgb(239, 68, 68)',
                            medianColor: 'rgb(255, 193, 7)'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: false
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: 'white',
                                bodyColor: 'white',
                                callbacks: {
                                    title: function(context) {
                                        return '日付: ' + context[0].label;
                                    },
                                    label: function(context) {
                                        const stats = context.parsed;
                                        return [
                                            '最小値: ' + stats.min.toFixed(1) + '秒',
                                            '第1四分位: ' + stats.q1.toFixed(1) + '秒',
                                            '中央値: ' + stats.median.toFixed(1) + '秒',
                                            '第3四分位: ' + stats.q3.toFixed(1) + '秒',
                                            '最大値: ' + stats.max.toFixed(1) + '秒'
                                        ];
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '日付',
                                    font: {
                                        size: 12,
                                        weight: 'bold'
                                    }
                                },
                                ticks: {
                                    maxRotation: 45,
                                    minRotation: 45
                                }
                            },
                            y: {
                                display: true,
                                title: {
                                    display: true,
                                    text: 'タイミング差（秒）',
                                    font: {
                                        size: 12,
                                        weight: 'bold'
                                    }
                                }
                            }
                        }
                    }
                });
            }
        }

        function generatePanelTrendsCharts() {
            // パネル別処理時間のヒストグラム
            const container = document.getElementById('panelTrendsContainer');
            if (!container || !panelTrendsData) return;

            // ヒストグラムのビン数
            const binCount = 20;  // ビン数を20に設定

            // パネルごとにヒストグラムを生成
            let index = 0;
            for (const panelName in panelTrendsData) {
                const data = panelTrendsData[panelName];

                // パネルごとの最小値と最大値を取得
                const panelMin = Math.min(...data);
                const panelMax = Math.max(...data);
                const binWidth = (panelMax - panelMin) / binCount;

                // ヒストグラムデータを作成
                const histogram = new Array(binCount).fill(0);
                const binLabels = [];

                // ビンのラベルを作成
                for (let i = 0; i < binCount; i++) {
                    const binStart = panelMin + i * binWidth;
                    const binEnd = panelMin + (i + 1) * binWidth;
                    binLabels.push(`${binStart.toFixed(1)}-${binEnd.toFixed(1)}`);
                }

                // データをビンに分類
                for (const value of data) {
                    let binIndex = Math.floor((value - panelMin) / binWidth);
                    // 最大値の場合は最後のビンに入れる
                    if (binIndex >= binCount) binIndex = binCount - 1;
                    if (binIndex >= 0) histogram[binIndex]++;
                }

                // ヒストグラムデータを割合（パーセンテージ）に変換
                const totalCount = data.length;
                const histogramPercent = histogram.map(count => (count / totalCount) * 100);

                // Y軸の最大値を動的に設定（見やすくするため）
                const maxPercent = Math.max(...histogramPercent);
                let yAxisMax;
                if (maxPercent <= 10) {
                    yAxisMax = Math.ceil(maxPercent / 2) * 2; // 2%単位で切り上げ
                } else if (maxPercent <= 25) {
                    yAxisMax = Math.ceil(maxPercent / 5) * 5; // 5%単位で切り上げ
                } else if (maxPercent <= 50) {
                    yAxisMax = Math.ceil(maxPercent / 10) * 10; // 10%単位で切り上げ
                } else {
                    yAxisMax = Math.ceil(maxPercent / 20) * 20; // 20%単位で切り上げ
                }

                // カラムを作成
                const columnDiv = document.createElement('div');
                columnDiv.className = 'column is-half';

                // カードを作成
                const cardDiv = document.createElement('div');
                cardDiv.className = 'card metrics-card';

                // カードヘッダー
                const headerDiv = document.createElement('div');
                headerDiv.className = 'card-header';
                const headerTitle = document.createElement('p');
                headerTitle.className = 'card-header-title';
                headerTitle.textContent = panelName + ' パネル';
                headerDiv.appendChild(headerTitle);

                // カードコンテンツ
                const contentDiv = document.createElement('div');
                contentDiv.className = 'card-content';
                const chartContainer = document.createElement('div');
                chartContainer.className = 'chart-container';
                chartContainer.style.height = '350px';

                // キャンバス
                const canvas = document.createElement('canvas');
                canvas.id = 'panelChart' + index;
                chartContainer.appendChild(canvas);
                contentDiv.appendChild(chartContainer);

                // 構造を組み立て
                cardDiv.appendChild(headerDiv);
                cardDiv.appendChild(contentDiv);
                columnDiv.appendChild(cardDiv);
                container.appendChild(columnDiv);

                // チャートを作成
                new Chart(canvas, {
                    type: 'bar',
                    data: {
                        labels: binLabels,
                        datasets: [{
                            label: '割合',
                            data: histogramPercent,
                            backgroundColor: getBoxplotColor(index),
                            borderColor: getBorderColor(index),
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: false
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: 'white',
                                bodyColor: 'white',
                                callbacks: {
                                    title: function(context) {
                                        return panelName + ' パネル - ' + context[0].label + '秒';
                                    },
                                    label: function(context) {
                                        const percentage = context.parsed.y.toFixed(1);
                                        const count = histogram[context.dataIndex];
                                        return `割合: ${percentage}% (${count}件)`;
                                    },
                                    afterBody: function() {
                                        return '総データ数: ' + data.length + '件';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                title: {
                                    display: true,
                                    text: '処理時間（秒）',
                                    font: {
                                        size: 12,
                                        weight: 'bold'
                                    }
                                },
                                ticks: {
                                    maxRotation: 45,
                                    minRotation: 45
                                }
                            },
                            y: {
                                beginAtZero: true,
                                max: yAxisMax,
                                title: {
                                    display: true,
                                    text: '割合（%）',
                                    font: {
                                        size: 12,
                                        weight: 'bold'
                                    }
                                },
                                grid: {
                                    color: 'rgba(0, 0, 0, 0.1)'
                                }
                            }
                        }
                    }
                });

                index++;
            }
        }

        function getBoxplotColor(index) {
            const colors = [
                'rgba(75, 192, 192, 0.6)',
                'rgba(54, 162, 235, 0.6)',
                'rgba(255, 99, 132, 0.6)',
                'rgba(255, 205, 86, 0.6)',
                'rgba(153, 102, 255, 0.6)',
                'rgba(255, 159, 64, 0.6)',
                'rgba(46, 204, 113, 0.6)',
                'rgba(52, 152, 219, 0.6)'
            ];
            return colors[index % colors.length];
        }

        function getBorderColor(index) {
            const colors = [
                'rgb(75, 192, 192)',
                'rgb(54, 162, 235)',
                'rgb(255, 99, 132)',
                'rgb(255, 205, 86)',
                'rgb(153, 102, 255)',
                'rgb(255, 159, 64)',
                'rgb(46, 204, 113)',
                'rgb(52, 152, 219)'
            ];
            return colors[index % colors.length];
        }

        function generatePanelTimeSeriesChart() {
            // パネル別処理時間推移の時系列グラフ
            const panelTimeSeriesCtx = document.getElementById('panelTimeSeriesChart');
            if (!panelTimeSeriesCtx || !panelTrendsData) return;

            // パネル名を取得し、データセットを準備
            const panelNames = Object.keys(panelTrendsData);
            const datasets = [];

            panelNames.forEach((panelName, index) => {
                const data = panelTrendsData[panelName];
                if (!data || data.length === 0) return;

                // 時系列データを作成（日付とデータのペア）
                const timeSeriesData = data.map((value, i) => ({
                    x: i,
                    y: value
                }));

                datasets.push({
                    label: panelName + ' パネル',
                    data: timeSeriesData,
                    borderColor: getBorderColor(index),
                    backgroundColor: getBoxplotColor(index),
                    tension: 0.1,
                    borderWidth: 2,
                    pointRadius: 1,
                    pointHoverRadius: 4,
                    fill: false
                });
            });

            new Chart(panelTimeSeriesCtx, {
                type: 'line',
                data: {
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: {
                                usePointStyle: true,
                                padding: 8,
                                font: {
                                    size: 12
                                }
                            }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: 'white',
                            bodyColor: 'white',
                            borderColor: 'rgba(255, 255, 255, 0.3)',
                            borderWidth: 1,
                            callbacks: {
                                title: function(context) {
                                    return 'データポイント: ' + (context[0].dataIndex + 1);
                                },
                                label: function(context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed.y !== null) {
                                        label += context.parsed.y.toFixed(2) + '秒';
                                    }
                                    return label;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            type: 'linear',
                            display: true,
                            title: {
                                display: true,
                                text: 'データポイント（時系列順）',
                                font: {
                                    size: 14,
                                    weight: 'bold'
                                }
                            },
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)',
                                display: true
                            }
                        },
                        y: {
                            type: 'linear',
                            display: true,
                            title: {
                                display: true,
                                text: '処理時間（秒）',
                                font: {
                                    size: 14,
                                    weight: 'bold'
                                }
                            },
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        }
                    }
                }
            });
        }
    """
