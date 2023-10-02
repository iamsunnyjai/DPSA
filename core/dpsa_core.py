import difflib
import imp
import math
import os
import random
import time
import wave
import socket
import json 

import eyed3
from openpyxl import load_workbook
import logging


import numpy as np
import dpsa_booter
from ai_module import xf_ltp
from ai_module.ms_tts_sdk import Speech
from core import wsa_server, tts_voice
from core.interact import Interact
from core.tts_voice import EnumVoice
from scheduler.thread_manager import MyThread
from utils import util, storer, config_util
from core import qa_service

import pygame
from utils import config_util as cfg
from core.content_db import Content_Db
from datetime import datetime

from ai_module import nlp_gpt

import platform
if platform.system() == "Windows":
    import sys
    sys.path.append("test/ovr_lipsync")
    from test_olipsync import LipSyncGenerator
    
modules = { 
    "nlp_gpt": nlp_gpt,
}


def determine_nlp_strategy(sendto,msg):
    text = ''
    textlist = []
    try:
        util.log(1, 'nlp...')
        tm = time.time()
        cfg.load_config()
        if sendto == 2:
            text = nlp_chatgpt.question(msg)
        else:
            module_name = "nlp_" + cfg.key_chat_module
            selected_module = modules.get(module_name)
            if selected_module is None:
                raise RuntimeError('keys are not set！')   
            if cfg.key_chat_module == 'rasa':
                textlist = selected_module.question(msg)
                text = textlist[0]['text'] 
            else:
                text = selected_module.question(msg)  
            util.log(1, 'nlp done. time: {} ms'.format(math.floor((time.time() - tm) * 1000)))
            if text == 'I do not understand' or text == '':
                util.log(1, '[!] Nlp error！')
                text = 'I do not understand'  
    except BaseException as e:
        print(e)
        util.log(1, 'Nlp error！')
        text = 'I do not understand'   

    return text,textlist
    
def send_for_answer(msg,sendto):
        contentdb = Content_Db()
        contentdb.add_content('member','send',msg)
        textlist = []
        text = None
        
        keyword = qa_service.question('Persona',msg)
        if keyword is not None:
            text = config_util.config["attribute"][keyword]

        if text is None:
            answer = qa_service.question('qa',msg)
            if answer is not None:
                text = answer       
            else:
                text,textlist = determine_nlp_strategy(sendto,msg)
                
        contentdb.add_content('dpsa','send',text)
        wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"dpsa","content":text}})
        if len(textlist) > 1:
            i = 1
            while i < len(textlist):
                  contentdb.add_content('dpsa','send',textlist[i]['text'])
                  wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"dpsa","content":textlist[i]['text']}})
                  i+= 1
        return text


class FeiFei:
    def __init__(self):
        pygame.mixer.init()
        self.q_msg = 'whats your name？'
        self.a_msg = 'hi,im Digital Police Station Assistant'
        self.mood = 0.0  
        self.old_mood = 0.0
        self.connect = False
        self.item_index = 0
        self.deviceSocket = None
        self.deviceConnect = None

        self.deviceSocketThread = MyThread(target=self.__accept_audio_device_output_connect)
        self.deviceSocketThread.start()

        self.X = np.array([1, 0, 0, 0, 0, 0, 0, 0]).reshape(1, -1)  
        self.W = np.array([0.0, 0.6, 0.1, 0.7, 0.3, 0.0, 0.0, 0.0]).reshape(-1, 1) 

        self.wsParam = None
        self.wss = None
        self.sp = Speech()
        self.speaking = False
        self.last_interact_time = time.time()
        self.last_speak_data = ''
        self.interactive = []
        self.sleep = False
        self.__running = True
        self.sp.connect()  
        self.last_quest_time = time.time()
        self.playing = False
        self.muting = False


    def __play_song(self):
        self.playing = True
        song_player.play()
        self.playing = False
        wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
        if not cfg.config["interact"]["playSound"]: 
            content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
            wsa_server.get_instance().add_cmd(content)

    
    def __get_answer(self, interleaver, text):
        if interleaver == "mic":
            keyword = qa_service.question('command',text)
            if keyword is not None:
                if keyword == "playSong":
                    MyThread(target=self.__play_song).start()
                    wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                    if not cfg.config["interact"]["playSound"]: 
                        content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
                        wsa_server.get_instance().add_cmd(content)
                elif keyword == "stop":
                    dpsa_booter.stop()
                    wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                    if not cfg.config["interact"]["playSound"]: 
                        content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
                        wsa_server.get_instance().add_cmd(content)
                    wsa_server.get_web_instance().add_cmd({"liveState": 0})
                elif keyword == "mute":
                    self.muting = True
                    self.speaking = True
                    self.a_msg = "好的"
                    MyThread(target=self.__say, args=['interact']).start()
                    time.sleep(0.5)
                    wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                    if not cfg.config["interact"]["playSound"]: 
                        content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
                        wsa_server.get_instance().add_cmd(content)
                elif keyword == "unmute":
                    self.muting = False
                    return None
                elif keyword == "changeVoice":
                    voice = tts_voice.get_voice_of(config_util.config["attribute"]["voice"])
                    for v in tts_voice.get_voice_list():
                        if v != voice:
                            config_util.config["attribute"]["voice"] = v.name
                            break
                    config_util.save_config(config_util.config)
                    wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
                    if not cfg.config["interact"]["playSound"]:
                        content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
                        wsa_server.get_instance().add_cmd(content)
                return "NO_ANSWER"
        
        
        keyword = qa_service.question('Persona',text)
        if keyword is not None:
            return config_util.config["attribute"][keyword]
        answer = None
      
        answer = qa_service.question('qa',text)
        if answer is not None:

            return answer

    def __auto_speak(self):
        while self.__running:
            time.sleep(0.8)
            if self.speaking or self.sleep:
                continue

            try:
                if len(self.interactive) > 0:
                    interact: Interact = self.interactive.pop()
                    index = interact.interact_type
                    if index == 1:
                        self.q_msg = interact.data["msg"]
                        if not config_util.config["interact"]["playSound"]: 
                            content = {'Topic': 'Unreal', 'Data': {'Key': 'question', 'Value': self.q_msg}}
                            wsa_server.get_instance().add_cmd(content)

                        answer = self.__get_answer(interact.interleaver, self.q_msg)
                        if(self.muting): 
                            wsa_server.get_web_instance().add_cmd({"panelMsg": "muted"})
                            if not cfg.config["interact"]["playSound"]: 
                                content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': "muted"}}
                                wsa_server.get_instance().add_cmd(content)
                            continue

                        contentdb = Content_Db()    
                        contentdb.add_content('member','speak',self.q_msg)
                        wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"member","content":self.q_msg}})
                     

                        text = ''
                        textlist = []
                        self.speaking = True
                        if answer is None:
                            wsa_server.get_web_instance().add_cmd({"panelMsg": "Thinking..."})
                            if not cfg.config["interact"]["playSound"]: 
                                content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': "Thinking..."}}
                                wsa_server.get_instance().add_cmd(content)
                            text,textlist = determine_nlp_strategy(1,self.q_msg)
                        elif answer != 'NO_ANSWER': 
                            text = answer
                        self.a_msg = text
                        contentdb.add_content('dpsa','speak',self.a_msg)
                        wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"dpsa","content":self.a_msg}})
                        if len(textlist) > 1:
                            i = 1
                            while i < len(textlist):
                                contentdb.add_content('dpsa','speak',textlist[i]['text'])
                                wsa_server.get_web_instance().add_cmd({"panelReply": {"type":"dpsa","content":textlist[i]['text']}})
                                i+= 1
                    wsa_server.get_web_instance().add_cmd({"panelMsg": self.a_msg})
                    if not cfg.config["interact"]["playSound"]: 
                        content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': self.a_msg}}
                        wsa_server.get_instance().add_cmd(content)
                    self.last_speak_data = self.a_msg               
                    MyThread(target=self.__say, args=['interact']).start()

            except BaseException as e:
                print(e)

    def on_interact(self, interact: Interact):
        self.interactive.append(interact)
        MyThread(target=self.__update_mood, args=[interact.interact_type]).start()
        MyThread(target=storer.storage_live_interact, args=[interact]).start()

    # 发送情绪
    def __send_mood(self):
         while self.__running:
            time.sleep(3)
            if not self.sleep and not config_util.config["interact"]["playSound"] and wsa_server.get_instance().isConnect:
                content = {'Topic': 'Unreal', 'Data': {'Key': 'mood', 'Value': self.mood}}
                if not self.connect:
                      wsa_server.get_instance().add_cmd(content)
                      self.connect = True
                else:
                    if  self.old_mood != self.mood:
                        wsa_server.get_instance().add_cmd(content)
                        self.old_mood = self.mood
                 
            else:
                  self.connect = False

    # 更新情绪
    def __update_mood(self, typeIndex):
        perception = config_util.config["interact"]["perception"]
        if typeIndex == 1:
            try:
                result = xf_ltp.get_sentiment(self.q_msg)
                chat_perception = perception["chat"]
                if result == 2:
                    self.mood = self.mood + (chat_perception / 200.0)
                elif result == 0:
                    self.mood = self.mood - (chat_perception / 100.0)
            except BaseException as e:
                print("[System] Emotion update error！")
                print(e)

        elif typeIndex == 2:
            self.mood = self.mood + (perception["join"] / 100.0)

        elif typeIndex == 3:
            self.mood = self.mood + (perception["gift"] / 100.0)

        elif typeIndex == 4:
            self.mood = self.mood + (perception["follow"] / 100.0)

        if self.mood >= 1:
            self.mood = 1
        if self.mood <= -1:
            self.mood = -1

    def __get_mood_voice(self):
        voice = tts_voice.get_voice_of(config_util.config["attribute"]["voice"])
        if voice is None:
            voice = EnumVoice.JENNY
        styleList = voice.value["styleList"]
        sayType = styleList["calm"]
        if -1 <= self.mood < -0.5:
            sayType = styleList["angry"]
        if -0.5 <= self.mood < -0.1:
            sayType = styleList["lyrical"]
        if -0.1 <= self.mood < 0.1:
            sayType = styleList["calm"]
        if 0.1 <= self.mood < 0.5:
            sayType = styleList["assistant"]
        if 0.5 <= self.mood <= 1:
            sayType = styleList["cheerful"]
        return sayType

    # 合成声音
    def __say(self, styleType):
        try:
            if len(self.a_msg) < 1:
                self.speaking = False
            else:
                util.printInfo(1, 'DPOA', '({}) {}'.format(self.__get_mood_voice(), self.a_msg))
                if not config_util.config["interact"]["playSound"]: 
                    content = {'Topic': 'Unreal', 'Data': {'Key': 'text', 'Value': self.a_msg}}
                    wsa_server.get_instance().add_cmd(content)
                MyThread(target=storer.storage_live_interact, args=[Interact('dpsa', 0, {'user': 'dpsa', 'msg': self.a_msg})]).start()
                util.log(1, 'tts...')
                tm = time.time()
                
                result = self.sp.to_sample(self.a_msg, self.__get_mood_voice())
                util.log(1, 'tts. time: {} ms file:{}'.format(math.floor((time.time() - tm) * 1000), result))
                if result is not None:            
                    MyThread(target=self.__send_or_play_audio, args=[result, styleType]).start()
                    return result
        except BaseException as e:
            print(e)
        self.speaking = False
        return None

    def __play_sound(self, file_url):
        util.log(1, 'Playing audio file...')
        util.log(1, 'Process time：{} ms'.format(math.floor((time.time() - self.last_quest_time) * 1000)))
        pygame.mixer.music.load(file_url)
        pygame.mixer.music.play()


    def __send_or_play_audio(self, file_url, say_type):
        try:
            try:
                logging.getLogger('eyed3').setLevel(logging.ERROR)
                audio_length = eyed3.load(file_url).info.time_secs 
            except Exception as e:
                audio_length = 3

            if config_util.config["interact"]["playSound"]: 
                self.__play_sound(file_url)
            else:
                
                content = {'Topic': 'Unreal', 'Data': {'Key': 'audio', 'Value': os.path.abspath(file_url), 'Text': self.a_msg, 'Time': audio_length, 'Type': say_type}}
                if platform.system() == "Windows":
                    try:
                        lip_sync_generator = LipSyncGenerator()
                        viseme_list = lip_sync_generator.generate_visemes(os.path.abspath(file_url))
                        consolidated_visemes = lip_sync_generator.consolidate_visemes(viseme_list)
                        content["Data"]["Lips"] = consolidated_visemes
                    except e:
                        util.log(1, "Lipsync failed")
                wsa_server.get_instance().add_cmd(content)

                
                if self.deviceConnect is not None:
                    try:
                        self.deviceConnect.send(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08')
                        wavfile = open(os.path.abspath(file_url),'rb')
                        data = wavfile.read(1024)
                        total = 0
                        while data:
                            total += len(data)
                            self.deviceConnect.send(data)
                            data = wavfile.read(1024)
                            time.sleep(0.001)
                        self.deviceConnect.send(b'\x08\x07\x06\x05\x04\x03\x02\x01\x00')
                        util.log(1, "remote input done：{}".format(total))
                    except socket.error as serr:
                        util.log(1,"remote input disconnected：{}".format(serr))
                    
            time.sleep(audio_length + 0.5)
            wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
            if not cfg.config["interact"]["playSound"]: 
                content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
                wsa_server.get_instance().add_cmd(content)
            if config_util.config["interact"]["playSound"]:
                util.log(1, 'End playing！')
            self.speaking = False
        except Exception as e:
            print(e)

    def __device_socket_keep_alive(self):
        while True:
            if self.deviceConnect is not None:
                try:
                    self.deviceConnect.send(b'\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8')#发送心跳包
                except Exception as serr:
                    util.log(1,"remote input disconnected：{}".format(serr))
                    self.deviceConnect = None
            time.sleep(1)

    def __accept_audio_device_output_connect(self):
        self.deviceSocket = socket.socket(socket.AF_INET,socket.SOCK_STREAM) 
        self.deviceSocket.bind(("0.0.0.0",10001))   
        self.deviceSocket.listen(1)
        addr = None        
        try:
            while True:
                self.deviceConnect,addr=self.deviceSocket.accept()   
                MyThread(target=self.__device_socket_keep_alive).start() 
                util.log(1,"remote input connected：{}".format(addr))
                while self.deviceConnect: 
                    time.sleep(1)
        except Exception as err:
            pass

    def set_sleep(self, sleep):
        self.sleep = sleep

    def start(self):
        MyThread(target=self.__send_mood).start()
        MyThread(target=self.__auto_speak).start()

    def stop(self):
        self.__running = False
        self.speaking = False
        self.playing = False
        self.sp.close()
        wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
        if not cfg.config["interact"]["playSound"]: 
            content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
            wsa_server.get_instance().add_cmd(content)
        if self.deviceConnect is not None:
            self.deviceConnect.close()
            self.deviceConnect = None
        if self.deviceSocket is not None:
            self.deviceSocket.close()

