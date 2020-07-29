# -*- coding: utf-8 -*-
"""
Created on Mon Jul  6 09:20:24 2020

@author: 8000725635
"""

import requests
import time
import random
from requests.adapters import HTTPAdapter
import datetime
import pandas as pd
import json

def get_json_data(base_url,headers):
    s = requests.Session()
    s.mount('http://', HTTPAdapter(max_retries=3))
    s.mount('https://', HTTPAdapter(max_retries=3))
    print(time.strftime('%Y-%m-%d %H:%M:%S'))
 
    try:
        response = requests.get(base_url, timeout=5, headers=headers)
        html = response.text
        # print(html)
        html_cl = html[12:-14]
        false = False
        true = True
        null = None
        html_json = eval(html_cl)
        json_str = json.dumps(html_json)
        results = json.loads(json_str)
        data = results['result']['data']['feed']['list']
    except Exception as e:
        print('get_json_str未收录错误类型，请检查网络通断,错误位置：',e)
        time.sleep(5)
        get_json_data(base_url, headers)
    else:
        return data

text_df=pd.DataFrame(columns=['id','time','content'])
text_id=[]
text_time=[]
text_content=[]

cur_date = datetime.datetime.now().date()

page=0
while True:
    page+=1
    print(page)
    referer_url = "http://finance.sina.com.cn/7x24/?tag=0"
    cookie = "UOR=www.baidu.com,tech.sina.com.cn,; SINAGLOBAL=114.84.181.236_1579684610.152568; UM_distinctid=16fcc8a8b704c8-0a1d2def9ca4c6-33365a06-15f900-16fcc8a8b718f1; lxlrttp=1578733570; gr_user_id=2736e487-ee25-4d52-a1eb-c232ac3d58d6; grwng_uid=d762fe92-912b-4ea8-9a24-127a43143ebf; __gads=ID=d79f786106eb99a1:T=1582016329:S=ALNI_MZoErH_0nNZiM3D4E36pqMrbHHOZA; Apache=114.84.181.236_1582267433.457262; ULV=1582626620968:6:4:1:114.84.181.236_1582267433.457262:1582164462661; ZHIBO-SINA-COM-CN=; SUB=_2AkMpBPEzf8NxqwJRmfoWz2_ga4R2zQzEieKfWADoJRMyHRl-yD92qm05tRB6AoTf3EaJ7Bg2UU4l1CDZXUBCzEuJv3mP; SUBP=0033WrSXqPxfM72-Ws9jqgMF55529P9D9WhqhhGsPWdPjar0R99pFT8s"
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Cookie": cookie,
        "Host": "zhibo.sina.com.cn",
        "Referer": referer_url,
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.117 Safari/537.36"
    }
    base_url = "http://zhibo.sina.com.cn/api/zhibo/feed?callback=jQuery0&page=%s"%page+"&page_size=20&zhibo_id=152&tag_id=0&dire=f&dpc=1&pagesize=20&_=0%20Request%20Method:GET%27"
    data = get_json_data(base_url,headers)
    for i in data:
        temp_id = i['id']
        create_time = i['create_time']
        rich_text = i['rich_text'].replace(' ','')
        rich_text = rich_text.replace('\\','')
        # print(id, create_time, rich_text)
        new_time = datetime.datetime.strptime(create_time, "%Y-%m-%d %H:%M:%S")

        if temp_id not in text_id:
            print(id, create_time, rich_text)
            text_id.append(temp_id)
            text_time.append(new_time)
            text_content.append(rich_text)
#                try:
# 
#                    sql = "insert into  sina_data(id,create_time,rich_text) values(%s,%s,%s)"
#                    cursor.execute(sql, (id, new_time, rich_text))
#                    conn.commit()
#                    cursor.close()
#                except Exception as e:
#                    print(e)
#                    continue
    cur_time = datetime.datetime.now().time()
    end_time = datetime.time(18,5,59,899)
    print(cur_time)
    if cur_time.__ge__(end_time):
        print("保存信息，结束")
        text_df['id']=text_id
        text_df['time']=text_time
        text_df['content']=text_content
        text_df.to_csv('/home/output/'+str(cur_date)+'.csv',sep=';',index=False)
        break
    else:
        print("继续")
        sleep_time=random.randint(100,300)
        print("休眠{}秒".format(sleep_time))
        time.sleep(sleep_time)
        continue



