# -*- coding: utf-8 -*-
"""
Created on Sun Aug 16 18:57:10 2020

@author: A
"""


from kpi_plot import *
import talib as ta
import tushare as ts
import smtplib
from email.mime.text import MIMEText
from email import encoders
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.utils import formataddr
import pandas as pd
import yfinance as yf
from jqdatasdk import *
import time
import numpy as np
import sys
sys.path.append('/home/temp')

auth('13918216955', 'Keepgoing@2020')
# security_pools=['601318.XSHG','600036.XSHG','600115.XSHG','600600.XSHG','000063.XSHE',
#     '002049.XSHE','603517.XSHG','000977.XSHE','002230.XSHE','603000.XSHG',
#     '002714.XSHE','600196.XSHG','002405.XSHE','601021.XSHG']
security_pools = ['601318.XSHG', '600031.XSHG', '600115.XSHG', '600276.XSHG', '600529.XSHG',
                  '600667.XSHG', '601872.XSHG', '000063.XSHE', '000756.XSHE',
                  '000977.XSHE', '002065.XSHE', '002384.XSHE', '300324.XSHE']
today = time.strftime('%Y-%m-%d', time.localtime(time.time()))


def get_industry_concept(security_pools):
    '''
    使用security_pools中的股票查询所属行业名称及代码
    '''
    industry_list = pd.DataFrame(
        columns=['code', 'industry_name', 'industry_code'])
    d = get_industry(security=security_pools, date=today)
    for key, value in d.items():
        temp = dict()
        temp['code'] = key
        temp['industry_name'] = value['sw_l1']['industry_name']
        temp['industry_code'] = value['sw_l1']['industry_code']
        industry_list = industry_list.append(temp, ignore_index=True)
    return industry_list


def get_industry_index(industry_list):
    temp = []
    for key, value in enumerate(industry_list['industry_code']):
        df = finance.run_query(
            query(
                finance.SW1_DAILY_PRICE).filter(
                finance.SW1_DAILY_PRICE.code == value).order_by(
                finance.SW1_DAILY_PRICE.date.desc()).limit(1))
        temp.append(df.loc[0, 'change_pct'])
    industry_list['ind_change'] = temp
    return industry_list


def get_locked_info(industry_list):
    temp = []
    df = get_locked_shares(security_pools, start_date=today, forward_count=100)
    next_df = pd.merge(industry_list, df, how='left', on='code')
    return next_df


def get_main_info(code, days):
    df = get_price(code, count=days, end_date=today, frequency='daily',
                   fields=['open', 'close', 'low', 'high', 'volume', 'money'])
    df['next_rate'] = df['close'].diff()
    return df


def MA_analyze(df):
    SMA_5d = ta.SMA(df['close'].values, 5)
    SMA_10d = ta.SMA(df['close'].values, 10)
    SMA_20d = ta.SMA(df['close'].values, 20)
    close = np.array(df['close'])
    if (close[-2] < SMA_5d[-2]) and (SMA_5d[-1] < close[-1]):
        return '收盘价向上突破5日均线，值得留意'
    elif (SMA_5d[-2] < SMA_10d[-2]) and (SMA_5d[-1] > SMA_10d[-1]):
        return '5日均线向上突破10日均线，值得留意'
    elif (SMA_5d[-2] < SMA_20d[-2]) and (SMA_5d[-1] > SMA_20d[-1]):
        return '5日均线向上突破20日均线，值得留意'
    elif (close[-2] > SMA_5d[-2]) and (SMA_5d[-1] > close[-1]):
        return '收盘价向下突破5日均线，值得留意'
    elif (SMA_5d[-2] > SMA_10d[-2]) and (SMA_5d[-1] < SMA_10d[-1]):
        return '5日均线向下突破10日均线，值得留意'
    elif (SMA_5d[-2] > SMA_20d[-2]) and (SMA_5d[-1] < SMA_20d[-1]):
        return '5日均线向下突破20日均线，值得留意'
    else:
        return ''


def MACD_analyze(df):
    DIF, DEA, MACD = ta.MACD(
        np.array(df.close), fastperiod=12, slowperiod=26, signalperiod=9)
    if (DIF[-1] > 0) and (DEA[-1] > 0) and (DIF[-1] > DEA[-1]) and (DIF[-2] < DEA[-2]):
        return 'DIF上穿，考虑买入'
    elif (DIF[-1] < 0) and (DEA[-1] < 0) and (DIF[-1] < DEA[-1]) and (DIF[-2] > DEA[-2]):
        return 'DIF下穿，考虑卖出'
    else:
        return ''


def OBV_analyze(df):
    volsma5 = df.volume.rolling(5).mean()
    volsma10 = df.volume.rolling(10).mean()
    volsma = ((volsma5+volsma10)/2)
    Volsignal = (df['volume'][-1] > volsma)*1
    Volsignal[Volsignal == 0] = -1
    n = 1
    for i in range(1, len(Volsignal)):
        if Volsignal[-i] != Volsignal[-i-1]:
            n = i
            break
    if Volsignal[-1] > 0:
        return "连续%d天成交量大于均值" % n
    else:
        return "连续%d天成交量小于均值" % n


def main_df(security_pools):
    industry_list = pd.DataFrame(
        columns=['code', 'industry_name', 'industry_code'])
    industry_list = get_industry_concept(security_pools)
    industry_list = get_industry_index(industry_list)
    industry_list = get_locked_info(industry_list)
    industry_list.insert(8, 'SMA_strategy', '')
    # industry_list.insert(9,'MACD_strategy','')
    # industry_list.insert(10,'OBV_strategy','')
    industry_list.insert(9, 'next_rate', '')
    for key, value in enumerate(industry_list['code']):
        df = get_main_info(value, 50)
        industry_list.loc[key, 'SMA_strategy'] = MA_analyze(df)
        # industry_list.loc[key,'MACD_strategy']=MACD_analyze(df)
        # industry_list.loc[key,'OBV_strategy']=OBV_analyze(df)
        industry_list.loc[key, 'next_rate'] = df['next_rate'][-1]
    return industry_list


def industry_analyze(industry_list):
    temp = []
    for key, value in enumerate(industry_list['ind_change']):
        if value*industry_list.loc[key, 'next_rate'] < 0:
            temp.append('股票与行业指数相背离')
        else:
            temp.append("")
    return temp


industry_list = main_df(security_pools)
# industry_list['industry_strategy']=industry_analyze(industry_list)
need_cols = ['code', 'industry_name', 'day', 'rate1', 'SMA_strategy']
industry_list = industry_list[need_cols]
industry_list['股名'] = [get_security_info(
    x, date='2020-06-13').display_name for x in industry_list['code']]
industry_list.rename(columns={'day': '解禁日期', 'rate1': '解禁股所占比例'}, inplace=True)
df2 = industry_list.to_html(
    index=False, float_format=lambda x: format(x, ',.2f'))


def create_index_info(index):
    need_cols = ['Open', 'High', 'Low', 'Close', 'rate']
    temp = yf.Ticker(index)
    temp_hist = temp.history()
    temp_hist['rate'] = temp_hist['Close'].pct_change().mul(100).round(2)
    temp_hist = temp_hist[need_cols]
    temp_hist = temp_hist.tail(1)
    temp_hist['name'] = [index]
    return temp_hist


def create_df1(index_list):
    df1 = pd.DataFrame(
        columns=['Open', 'High', 'Low', 'Close', 'rate', 'name'])
    for item in index_list:
        temp_hist = create_index_info(item)
        df1 = pd.concat([df1, temp_hist], axis=0)
    return df1


df1 = create_df1(['DJIA', 'NDAQ', '^SPX'])
df1 = df1.to_html(index=False, float_format=lambda x: format(x, ',.2f'))
########添加指标图##############


def get_pic_list(industry_list, file_path):
    pic_list = []
    for key, value in enumerate(industry_list['code']):
        df = get_main_info(value, 120)
        stock_name = industry_list['股名'][key]
        pic = get_image(df, file_path, stock_name)
        pic.add_header('Content-ID', '<'+str(key)+'>')
        pic_list.append(get_image(df, file_path, stock_name))
    return pic_list

####发邮件模块#######


def get_html_msg(df_html1, df_html2, table_title, pic_list):
    # 表格格式
    head = \
        """
        <head>
            <meta charset="utf-8">
            <STYLE TYPE="text/css" MEDIA=screen>

                table.dataframe {
                    border-collapse:collapse;
                    border: 2px solid #a19da2;
                    /*默认居中auto显示整个表格*/
                    margin: left
                }

                table.dataframe thead {
                    border: 2px solid #91c6e1;
                    background: #f1f1f1;
                    padding: 10px 10px 10px 10px;
                    color: #333333;
                }

                table.dataframe tbody {
                    border: 2px solid #91c6e1;
                    padding: 10px 10px 10px 10px;
                }

                table.dataframe tr {
                }

                table.dataframe th {
                    vertical-align: top;
                    font-size: 14px;
                    padding: 10px 10px 10px 10px;
                    color: #105de3;
                    font-family: arial;
                    text-align: center;
                }

                table.dataframe td{
                    text-align: left;
                    padding: 10px 10px 10px 10px;
                }

                body {
                    font-family: 宋体；
                }

                h1 {
                    color: #5db446
                    }

                div.header h2 {
                    color: #0002e3;
                    font-family: 黑体;
                }

                div.content h2 {
                    text-align: center;
                    font-size: 28px;
                    text-shadow: 2px 2px 1px #de4040;
                    color: #fff;
                    font-weight: bold;
                    background-color: #008eb7;
                    line-height: 1.5;
                    margin: 20px 0;
                    box-shadow: 10px 10px 5pxx #888888;
                    border-radius: 5px;
                }

                h3 {
                    font-size: 22px;
                    background-color: rgba(0,2,227,0.71);
                    text-shadow: 2px 2px 1px #de4040;
                    color: rgba(239,241,234,0.99);
                    line-height; 1.5;
                }

                h4 {
                    color: #e10092;
                    font-family: 楷体
                    font-size: 20px;
                    text-align: center;
                }

                td img {
                    /*width: 60px;*/
                    max-width: 300px;
                    max-height: 300px;
                }

            </style>

        </head>
        """

    # 构造正文表格
    body = \
        """
         <body>
         <div align="center" class="header">
            <!--标题部分的信息-->
            <p align="left">{table_title}</p>
         </div>
         <p>Hi!<br>
             外盘信息：<br>
         </p> 
         <div class="content">
            {df_html1}
         </div>
         <p>Hi!<br>
             关注股信息：<br>
         </p> 
         <div class="content">
            {df_html2}
        </div>
        <br>
        """.format(df_html1=df_html1, df_html2=df_html2, table_title=table_title)

    for i in range(len(pic_list)):
        if index % 2 == 0:
            body += '<img src="cid:' + str(i) + '"><br>'
        else:
            body += '<img src="cid:' + str(i) + '">'

    html_msg = "<html>" + head + body + "</body></html>"
    return html_msg


# 添加正文
def attach_text(msg, html_msg):
    content_html = MIMEText(html_msg, "html", "utf-8")
    msg.attach(content_html)
# 添加图片


def attach_pic(msg, pic_list):
    for item in pic_list:
        msg.attach(item)
# 建立主发送模块
# imap:lhvkywherkqxbiei


def mail(df_html1, df_html2, table_title):
    sender = '406933095@qq.com'  # 发件人
    receivers = 'betterdl041@163.com,10539519@qq.com'  # 多个收件人
    smtp_server = 'smtp.qq.com'
    smtp_port = 465
    qqCode = '*********'
    subject = '每日股票提醒'  # 标题
    msg = MIMEMultipart('mixed')
    msg['From'] = sender
    msg['To'] = receivers
    msg['Subject'] = subject
    file_path = '/home/temp/pic1.jpg'
    pic_list = get_pic_list(industry_list, file_path)
    html_msg = get_html_msg(df_html1, df_html2, table_title, pic_list)
    attach_text(msg, html_msg)
    attach_pic(msg, pic_list)
    smtp = smtplib.SMTP_SSL(smtp_server, smtp_port)
    # 我们用set_debuglevel(1)就可以打印出和SMTP服务器交互的所有信息。
    # smtp.set_debuglevel(1)
    smtp.login(sender, qqCode)
    smtp.sendmail(sender, receivers.split(','), msg.as_string())
    smtp.quit()


mail(df1, df2, '信息')
