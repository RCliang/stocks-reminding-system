# -*- coding: utf-8 -*-
"""
Created on Mon Jul 27 22:24:59 2020

@author: A
"""


from gensim.test.utils import common_texts, get_tmpfile
from gensim.models import Word2Vec
import pandas as pd
import numpy as np
from pyhanlp import *
from jpype import JString

############训练语料############
with open('D:/nlp_learning/新浪财经语料/2020-07-19.csv','rb') as f:
    data=pd.read_csv(f,sep=';')

######分词#############
import hanlp
import re
tokenizer = hanlp.load('PKU_NAME_MERGED_SIX_MONTHS_CONVSEG')

to_csv_content=[]
r = re.compile("[\s+\.\!\/_,$%^*(+\"\']+|[+——！；「」》:：“”·‘’《，。？、~@#￥%……&*（）()]+")
for item in data['content']:
    print(item)
    sentence = r.sub('',str(item))
    seg_list=tokenizer(sentence)
    to_csv_content.append(seg_list)


target_word=['芯片','紫光','行业','农业','券商','电动车','电池','服务器','军工','白酒','医药',
             '健康','医疗','水泥','上涨','北京']


#############寻找最相似词汇######################
text=data['content'][12]
model = Word2Vec.load("D:/nlp_learning/sinavoacb.model")
r = re.compile("[\s+\.\!\/_,$%^*(+\"\']+|[+——！；「」》:：“”·‘’《，。？、~@#￥%……&*（）()]+")
#########停用词##############
def stopwordslist(filepath):
    stopwords = [line.strip() for line in open(filepath, 'r', encoding='utf-8').readlines()]
    return stopwords
stopwords=stopwordslist('D:/nlp_learning/停用词表/characters-master/stop_words')

score_list=[]
for text in data['content']:
    sentence=list(HanLP.extractSummary(text,2))
    for item in sentence:
        temp = r.sub('',str(item))
        seg_list=tokenizer(temp)
        outstr = []
        for word in seg_list:
            if word not in stopwords:
                if word != '\t':
                    outstr.append(word)
        sim_dict=[]
        for i in target_word:
            temp=[]
            for j in outstr:
                try:
                    res=model.similarity(i, j)
                except:
                    res=0.0
                temp.append(res)
            sim_dict.extend(temp)
        score=len([item for item in sim_dict if item > 0.5])
    score_list.append(score)
    
len([index for score,index in enumerate(score_list) if score >=7])

    
