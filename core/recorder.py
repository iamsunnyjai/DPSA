import audioop
import math
import time
from abc import abstractmethod

from ai_module.ali_nls import ALiNls
from core import wsa_server
from scheduler.thread_manager import MyThread
from utils import util
from utils import config_util as cfg
import numpy as np
_ATTACK = 0.2
_RELEASE = 0.75


class Recorder:

    def __init__(self, dpsa):
        self.__dpsa = dpsa

        

        self.__running = True
        self.__processing = False
        self.__history_level = []
        self.__history_data = []
        self.__dynamic_threshold = 0.5

        self.__MAX_LEVEL = 25000
        self.__MAX_BLOCK = 100
        
        self.ASRMode = cfg.ASR_mode
        self.__aLiNls = self.asrclient()


    def asrclient(self):
        if self.ASRMode == "ali":
            asrcli = ALiNls()
        elif self.ASRMode == "funasr":
            asrcli = FunASR()
        return asrcli

    

    def __get_history_average(self, number):
        total = 0
        num = 0
        for i in range(len(self.__history_level) - 1, -1, -1):
            level = self.__history_level[i]
            total += level
            num += 1
            if num >= number:
                break
        return total / num

    def __get_history_percentage(self, number):
        return (self.__get_history_average(number) / self.__MAX_LEVEL) * 1.05 + 0.02

    def __print_level(self, level):
        text = ""
        per = level / self.__MAX_LEVEL
        if per > 1:
            per = 1
        bs = int(per * self.__MAX_BLOCK)
        for i in range(bs):
            text += "#"
        for i in range(self.__MAX_BLOCK - bs):
            text += "-"
        print(text + " [" + str(int(per * 100)) + "%]")

    def __on_msg(self):
        if "stop" in self.finalResults:
            util.log(1,"Stop!")

    def __waitingResult(self, iat:asrclient):
        if self.__dpsa.playing:
            return
        self.processing = True
        t = time.time()
        tm = time.time()
        # 等待结果返回
        while not iat.done and time.time() - t < 1:
            time.sleep(0.01)
        text = iat.finalResults
        util.log(1, "stt done！ time: {} ms".format(math.floor((time.time() - tm) * 1000)))
        if len(text) > 0:
            self.on_speaking(text)
            self.processing = False
        else:
            util.log(1, "[!] No content detected！")
            self.processing = False
            self.dynamic_threshold = self.__get_history_percentage(30)
            wsa_server.get_web_instance().add_cmd({"panelMsg": ""})
            if not cfg.config["interact"]["playSound"]:
                content = {'Topic': 'Unreal', 'Data': {'Key': 'log', 'Value': ""}}
                wsa_server.get_instance().add_cmd(content)

   
    def __record(self):
        try:
            stream = self.get_stream()
        except Exception as e:
                print(e)
                util.log(1, "Check device and reboot!")
                return
        isSpeaking = False
        last_mute_time = time.time()
        last_speaking_time = time.time()
        data = None
        while self.__running:
            try:
                data = stream.read(1024, exception_on_overflow=False)
            except Exception as e:
                data = None
                print(e)
                util.log(1, "Check device and reboot!")
                return

            if data is None:
                continue

            if  cfg.config['source']['record']['enabled']:
                if len(cfg.config['source']['record'])<3:
                    channels = 1
                else:
                    channels = int(cfg.config['source']['record']['channels'])

                data = np.frombuffer(data, dtype=np.int16)
                data = np.reshape(data, (-1, channels))  # reshaping the array to split the channels
                mono = data[:, 0]  # taking the first channel
                data = mono.tobytes()  

            level = audioop.rms(data, 2)
            if len(self.__history_data) >= 5:
                self.__history_data.pop(0)
            if len(self.__history_level) >= 500:
                self.__history_level.pop(0)
            self.__history_data.append(data)
            self.__history_level.append(level)

            percentage = level / self.__MAX_LEVEL
            history_percentage = self.__get_history_percentage(30)

            if history_percentage > self.__dynamic_threshold:
                self.__dynamic_threshold += (history_percentage - self.__dynamic_threshold) * 0.0025
            elif history_percentage < self.__dynamic_threshold:
                self.__dynamic_threshold += (history_percentage - self.__dynamic_threshold) * 1

            soon = False
            if percentage > self.__dynamic_threshold and not self.__dpsa.speaking:
                last_speaking_time = time.time()
                if not self.__processing and not isSpeaking and time.time() - last_mute_time > _ATTACK:
                    soon = True  #
                    isSpeaking = True  #user is speaking
                    util.log(3, "listening...")
                    self.__aLiNls = self.asrclient()
                    try:
                        self.__aLiNls.start()
                    except Exception as e:
                        print(e)
                    for buf in self.__history_data:
                        self.__aLiNls.send(buf)
            else:
                last_mute_time = time.time()
                if isSpeaking:
                    if time.time() - last_speaking_time > _RELEASE:
                        isSpeaking = False
                        self.__aLiNls.end()
                        util.log(1, "stt...")
                        self.__dpsa.last_quest_time = time.time()
                        self.__waitingResult(self.__aLiNls)
            if not soon and isSpeaking:
                self.__aLiNls.send(data)
     

    def set_processing(self, processing):
        self.__processing = processing

    def start(self):
        MyThread(target=self.__record).start()

    def stop(self):
        self.__running = False
        self.__aLiNls.end()

    @abstractmethod
    def on_speaking(self, text):
        pass

    @abstractmethod
    def get_stream(self):
        pass
