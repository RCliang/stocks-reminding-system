import talib as ta
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from email.mime.image import MIMEImage
import numpy as np


def get_image(df, pic_path, stock_name):
    plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
    plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号
    plt.figure(figsize=(10, 2), dpi=100, facecolor="white")
    gs = gridspec.GridSpec(3, 1, left=0.08, bottom=0.15, right=0.99,
                           top=0.96, wspace=None, hspace=0, height_ratios=[1, 1, 1])

    graph_VOL = plt.subplot(gs[0, :])
    graph_MACD = plt.subplot(gs[1, :])
    graph_KDJ = plt.subplot(gs[2, :])

    ##########成交量###########
    graph_VOL.bar(np.arange(0, len(df.index)), df.volume, color=[
                  'g' if df.open[x] > df.close[x] else 'r' for x in range(0, len(df.index))])
    graph_VOL.set_ylabel(u"成交量")
    graph_VOL.set_xlim(0, len(df.index))  # 设置一下x轴的范围
    graph_VOL.set_xticks(range(0, len(df.index), 15))  # X轴刻度设定 每15天标一个日期
    #########macd#############
    macd_dif, macd_dea, macd_bar = ta.MACD(
        df['close'].values, fastperiod=12, slowperiod=26, signalperiod=9)
    graph_MACD.plot(np.arange(0, len(df.index)), macd_dif,
                    'red', label='macd dif')  # dif
    graph_MACD.plot(np.arange(0, len(df.index)), macd_dea,
                    'blue', label='macd dea')  # dea

    bar_red = np.where(macd_bar > .0, 2 * macd_bar, 0)  # 绘制BAR>0 柱状图
    bar_green = np.where(macd_bar < .0, 2 * macd_bar, 0)  # 绘制BAR<0 柱状图
    graph_MACD.bar(np.arange(0, len(df.index)), bar_red, facecolor='red')
    graph_MACD.bar(np.arange(0, len(df.index)), bar_green, facecolor='green')

    graph_MACD.legend(loc='best', shadow=True, fontsize='10')
    graph_MACD.set_ylabel(u"MACD")
    graph_MACD.set_xlim(0, len(df.index))  # 设置一下x轴的范围
    graph_MACD.set_xticks(range(0, len(df.index), 15))  # X轴刻度设定 每15天标一个日期
    #########KDJ#############
    df['K'], df['D'] = ta.STOCH(df.high.values, df.low.values, df.close.values,
                                fastk_period=9, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
    df['J'] = 3 * df['K'] - 2 * df['D']

    graph_KDJ.plot(np.arange(0, len(df.index)),
                   df['K'], 'blue', label='K')  # K
    graph_KDJ.plot(np.arange(0, len(df.index)), df['D'], 'g--', label='D')  # D
    graph_KDJ.plot(np.arange(0, len(df.index)), df['J'], 'r-', label='J')  # J
    graph_KDJ.legend(loc='best', shadow=True, fontsize='10')

    graph_KDJ.set_ylabel(u"KDJ")
    graph_KDJ.set_xlabel("日期")
    graph_KDJ.set_xlim(0, len(df.index))  # 设置一下x轴的范围
    graph_KDJ.set_xticks(range(0, len(df.index), 15))  # X轴刻度设定 每15天标一个日期
    graph_KDJ.set_xticklabels([str(df.index[idx])[:10]
                               for idx in graph_KDJ.get_xticks()])  # 标签设置为日期

    for label in graph_VOL.xaxis.get_ticklabels():
        label.set_visible(False)

    for label in graph_MACD.xaxis.get_ticklabels():
        label.set_visible(False)

    for label in graph_KDJ.xaxis.get_ticklabels():
        label.set_rotation(45)
        label.set_fontsize(10)
    plt.suptitle(stock_name, fontsize=16)
    plt.savefig(pic_path)
    plt.savefig(pic_path)
    with open(pic_path, 'rb') as f:
        pic = MIMEImage(f.read())
    return pic
