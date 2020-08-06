# -*- coding: utf-8 -*-
"""
Created on Mon Jul 27 22:24:59 2020

@author: A
"""


import os
import re
import hanlp
from gensim.test.utils import common_texts, get_tmpfile
from gensim.models import Word2Vec
import pandas as pd
import numpy as np
from pyhanlp import *
from jpype import JString

############训练语料############
with open('D:/nlp_learning/新浪财经语料/2020-07-19.csv', 'rb') as f:
    data = pd.read_csv(f, sep=';')

######分词#############
tokenizer = hanlp.load('PKU_NAME_MERGED_SIX_MONTHS_CONVSEG')

to_csv_content = []
r = re.compile("[\s+\.\!\/_,$%^*(+\"\']+|[+——！；「」》:：“”·‘’《，。？、~@#￥%……&*（）()]+")
for item in data['content']:
    print(item)
    sentence = r.sub('', str(item))
    seg_list = tokenizer(sentence)
    to_csv_content.append(seg_list)


target_word = ['芯片', '紫光', '行业', '农业', '券商', '电动车', '电池', '服务器', '军工', '白酒', '医药',
               '健康', '医疗', '水泥', '上涨', '北京']
target_ner = ['紫光国微', '五粮液', '中兵红箭', '宁德时代', '三一重工', '东方航空', '恒瑞医药',
              '山东药玻', '太极实业', '中船防务', '中国平安', '招商轮船', '中兴通讯', '浪潮信息',
              '东华软件', '东山精密', '旋极信息']

#############寻找最相似词汇######################
text = data['content'][12]
model = Word2Vec.load("D:/nlp_learning/sinavoacb.model")
r = re.compile("[\s+\.\!\/_,$%^*(+\"\']+|[+——！；「」》:：“”·‘’《，。？、~@#￥%……&*（）()]+")
#########停用词##############


def stopwordslist(filepath):
    stopwords = [line.strip() for line in open(
        filepath, 'r', encoding='utf-8').readlines()]
    return stopwords


stopwords = stopwordslist('D:/nlp_learning/停用词表/characters-master/stop_words')

score_list = []
for text in data['content']:
    sentence = list(HanLP.extractSummary(text, 2))
    for item in sentence:
        temp = r.sub('', str(item))
        seg_list = tokenizer(temp)
        outstr = []
        for word in seg_list:
            if word not in stopwords:
                if word != '\t':
                    outstr.append(word)
        sim_dict = []
        for i in target_word:
            temp = []
            for j in outstr:
                try:
                    res = model.similarity(i, j)
                except:
                    res = 0.0
                temp.append(res)
            sim_dict.extend(temp)
        score = len([item for item in sim_dict if item > 0.5])
    score_list.append(score)

len([index for score, index in enumerate(score_list) if score >= 7])

###############命名实体识别################
PerceptronSegmenter = JClass(
    'com.hankcs.hanlp.model.perceptron.PerceptronSegmenter')
AbstractLexicalAnalyzer = JClass(
    'com.hankcs.hanlp.tokenizer.lexical.AbstractLexicalAnalyzer')
PerceptronPOSTagger = JClass(
    'com.hankcs.hanlp.model.perceptron.PerceptronPOSTagger')
Sentence = JClass('com.hankcs.hanlp.corpus.document.sentence.Sentence')
sys.path.append('D:/Github/pyhanlp/tests')
'''
from test_utility import ensure_data
PKU98 = ensure_data("pku98", "http://file.hankcs.com/corpus/pku98.zip")
PKU199801 = os.path.join(PKU98, '199801.txt')
PKU199801_TRAIN = os.path.join(PKU98, '199801-train.txt')
PKU199801_TEST = os.path.join(PKU98, '199801-test.txt')
POS_MODEL = os.path.join(PKU98, 'pos.bin')
NER_MODEL = os.path.join(PKU98, 'ner.bin')
'''
NERTrainer = JClass('com.hankcs.hanlp.model.perceptron.NERTrainer')
PerceptronNERecognizer = JClass(
    'com.hankcs.hanlp.model.perceptron.PerceptronNERecognizer')
trainer = NERTrainer()
model_file = 'D:/anaconda/envs/nlp_env/Lib/site-packages/pyhanlp/static/data/test/pku98/ner.bin'
recognizer = PerceptronNERecognizer(model_file)
analyzer = PerceptronLexicalAnalyzer(
    PerceptronSegmenter(), PerceptronPOSTagger(), recognizer)
print(analyzer.analyze("华北电力公司董事长谭旭光和秘书胡花蕊来到美国纽约现代艺术博物馆参观"))
###########命名体识别在线训练###################
###########example###################
sentence = Sentence.create(
    "与/c 特朗普/nr 通/v 电话/n 讨论/v [太空/s 探索/vn 技术/n 公司/n]/nt")
while not analyzer.analyze(sentence.text()).equals(sentence):
    analyzer.learn(sentence)

wd_dict = {}


class ner_word(object):
    def __init__(self, wd_dict):
        self.wd_dict = wd_dict
        self.need_word = []

    def ner_concern(self, data):
        for text in data['content']:
            for item in analyzer.analyze(text):
                temp = (str(item))
                mid = re.split('/', temp)
                self.wd_dict[mid[0]] = mid[1]

    def get_need_word(self, cx=['nr', 'nt', 'nz']):
        for key, value in self.wd_dict.items():
            if value in cx:
                self.need_word.append(key)
        return self.need_word


test = ner_word(wd_dict)
test.ner_concern(data)
need_word = test.get_need_word(cx=['nt'])
