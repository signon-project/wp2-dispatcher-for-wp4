# Copyright 2021-2023 FINCONS GROUP AG within the Horizon 2020
# European project SignON under grant agreement no. 101017255.

# Licensed under the Apache License, Version 2.0 (the "License"); 
# you may not use this file except in compliance with the License. 
# You may obtain a copy of the License at 

#     http://www.apache.org/licenses/LICENSE-2.0 

# Unless required by applicable law or agreed to in writing, software 
# distributed under the License is distributed on an "AS IS" BASIS, 
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
# See the License for the specific language governing permissions and 
# limitations under the License.


#!/usr/bin/env python
import pika
import copy
import json
import yaml
import sys, getopt
from time import time, sleep

import os
import requests
from sacrebleu import sentence_bleu

from Utils.helper_T2T import translate_text
from Utils.helper_E2T import translate_embedding
from Utils.helper_T2G import translate_text_to_gloss
from Utils.helper_NLU import use_NLU
from ExceptionHandler.exceptionHandler import handleException

def now():
    return round(time() * 1000)


argv = sys.argv[1:]
configFile = 'config.yml'
opts, args = getopt.getopt(argv,"hc:",["config="])
for opt, arg in opts:
    if opt == '-h':
        print ('pipeline.py -c <config-file-path>')
        sys.exit()
    elif opt in ("-c", "--config"):
        configFile = arg
print('Config file:', configFile)

with open(configFile, 'rb') as f:
    conf = yaml.safe_load(f.read())
print('RabbitMQ host:', conf['rabbitmq']['host'])
print('RabbitMQ WP4 queue:', conf['rabbitmq']['wp4-queue'])
print('RabbitMQ WP5 queue:', conf['rabbitmq']['wp5-queue'])

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=conf['rabbitmq']['host']))
channel = connection.channel()

def on_request(ch, method, props, body):
    my_json = body.decode('utf8')
    data = json.loads(my_json)

    data['IntermediateRepresentation'] = {}

    if not conf['debug']['multi-processing']:
        try:
            if ((data['App']['sourceMode'] == 'TEXT' or data['App']['sourceMode'] == 'AUDIO') and (data['App']['translationMode'] == 'TEXT' or data['App']['translationMode'] == 'AUDIO')):
                data['IntermediateRepresentation']['translationText'] = translate_text(data, conf)

            if ((data['App']['sourceMode'] == 'TEXT' or data['App']['sourceMode'] == 'AUDIO') and data['App']['translationMode'] == 'AVATAR'):
                if data['App']['sourceLanguage'] == 'ENG':
                    if data['App']['sourceMode'] == 'TEXT':
                        to_translate = data['App']['sourceText']
                    else:
                        to_translate = data['SourceLanguageProcessing']['ASRText']
                    data['IntermediateRepresentation']['glosses'] = translate_text_to_gloss(to_translate, conf, data['App']['translationLanguage'])
                else:
                    tmp_data = copy.deepcopy(data)
                    tmp_data['App']['translationLanguage'] = 'ENG'
                    data['IntermediateRepresentation']['englishTranslation'] = translate_text(tmp_data, conf)
                    data['IntermediateRepresentation']['glosses'] = translate_text_to_gloss(data['IntermediateRepresentation']['englishTranslation'], conf, data['App']['translationLanguage'])

            if (data['App']['sourceMode'] == 'VIDEO' and (data['App']['translationMode'] == 'TEXT' or data['App']['translationMode'] == 'AUDIO')):
                if data['App']['translationLanguage'] == 'DUT':
                    text_from_embeddings = translate_embedding(data, conf)
                    data_nlu = copy.deepcopy(data)
                    data_nlu['App']['sourceText'] = text_from_embeddings[0]
                    data_nlu['App']['SourceLanguage'] = 'DUT'
                    data['IntermediateRepresentation']['textFromEmbeddings'] = text_from_embeddings[0]
                    data['IntermediateRepresentation']['translationText'] = text_from_embeddings[0]
                else:
                    tmp_data = copy.deepcopy(data)
                    tmp_data['App']['translationLanguage'] = 'DUT'
                    text_from_embeddings = translate_embedding(tmp_data, conf)
                    data_nlu = copy.deepcopy(data)
                    data_nlu['App']['sourceText'] = text_from_embeddings[0]
                    data_nlu['App']['SourceLanguage'] = 'DUT'
                    data['IntermediateRepresentation']['textFromEmbeddings'] = text_from_embeddings[0]
                    tmp_data = copy.deepcopy(data)
                    tmp_data['App']['sourceText'] = data['IntermediateRepresentation']['textFromEmbeddings']
                    tmp_data['App']['sourceMode'] = 'TEXT'
                    tmp_data['App']['sourceLanguage'] = 'DUT'
                    tmp_data['App']['translationMode'] = 'TEXT'
                    data['IntermediateRepresentation']['translationText'] = translate_text(tmp_data, conf)

            #   video to avatar
            if data['App']['sourceMode'] == 'VIDEO' and data['App']['translationMode'] == 'AVATAR':
                tmp_data = copy.deepcopy(data)
                tmp_data['App']['translationLanguage'] = 'DUT'
                text_from_embeddings = translate_embedding(tmp_data, conf)
                data_nlu = copy.deepcopy(data)
                data_nlu['App']['sourceText'] = text_from_embeddings[0]
                data_nlu['App']['SourceLanguage'] = 'DUT'
                data['IntermediateRepresentation']['textFromEmbeddings'] = text_from_embeddings[0]
                tmp_data = copy.deepcopy(data)
                tmp_data['App']['sourceText'] = data['IntermediateRepresentation']['textFromEmbeddings']
                tmp_data['App']['sourceMode'] = 'TEXT'
                tmp_data['App']['sourceLanguage'] = 'DUT'
                tmp_data['App']['translationLanguage'] = 'ENG'
                tmp_data['App']['translationMode'] = 'TEXT'
                data['IntermediateRepresentation']['englishTranslation'] = translate_text(tmp_data, conf)
                data['IntermediateRepresentation']['glosses'] = translate_text_to_gloss(data['IntermediateRepresentation']['englishTranslation'], conf, data['App']['translationLanguage'])
        except (requests.exceptions.ReadTimeout, requests.exceptions.Timeout, requests.exceptions.ConnectTimeout) as e:
            e_type = "T2T-Timeout"
            e_title = "T2T Component Timeout Connection"
            e_status = 500
            e_detail = "The Connection with the translation Component caused a Timeout"
            handleException(e, ch, data['RabbitMQ']['replyTo'], data['RabbitMQ']['correlationID'], e_type, e_title, e_status, e_detail)
        except Exception as e:
            e_type = "T2T-Error"
            e_title = "There has been an Error with the T2T Component"
            e_status = 500
            e_detail = "Something with the translation has not worked correctly"
            handleException(e, ch, data['RabbitMQ']['replyTo'], data['RabbitMQ']['correlationID'], e_type, e_title, e_status, e_detail)
            return

    else:
        print("Pipeline Instance " + str(os.getpid()) + " [x] Received request for " + data['App']['sourceText'])
        workSec = len(data['App']['sourceText'])
        sleep(workSec)
        print("Pipeline Instance " + str(os.getpid()) + " [.] Returned " + str(workSec))
        translationText = " Waiting Time: " + str(workSec)
        print(translationText)

    data['IntermediateRepresentation']['T3WP4'] = now()
    response_string = json.dumps(data)

    ch.basic_publish(exchange='',
                          routing_key=conf['rabbitmq']['wp5-queue'],
                          properties=pika.BasicProperties(correlation_id = props.correlation_id),
                          body=response_string)
    print(" [x] Message Sent to WP5")

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue=conf['rabbitmq']['wp4-queue'], on_message_callback=on_request, auto_ack=True)
print(" [x] Awaiting WP3 Message")
channel.start_consuming()
