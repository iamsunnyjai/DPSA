import time
import pyaudio
from core.interact import Interact
from core.recorder import Recorder
from core.dpsa_core import FeiFei
from scheduler.thread_manager import MyThread
from utils import util, config_util
from core.wsa_server import MyServer
from scheduler.thread_manager import MyThread

feiFei: FeiFei = None
recorderListener: Recorder = None

__running = False

#record mic input and send aliyun
class RecorderListener(Recorder):

    def __init__(self, device, fei):
        self.__device = device
        self.__RATE = 16000
        self.__FORMAT = pyaudio.paInt16
        self.__running = False

        super().__init__(fei)

    def on_speaking(self, text):
        if len(text) > 1:
            interact = Interact("mic", 1, {'user': '', 'msg': text})
            util.printInfo(3, "Voice", '{}'.format(interact.data["msg"]), time.time())
            feiFei.on_interact(interact)
            time.sleep(2)

    def get_stream(self):
        self.paudio = pyaudio.PyAudio()
        device_id,devInfo = self.__findInternalRecordingDevice(self.paudio)
        if device_id < 0:
            return
        channels = int(devInfo['maxInputChannels'])
        if channels == 0:
            util.log(1, 'Check devices!')
            return
        self.stream = self.paudio.open(input_device_index=device_id, rate=self.__RATE, format=self.__FORMAT, channels=channels, input=True)
        self.__running = True
        MyThread(target=self.__pyaudio_clear).start()
        return self.stream

    def __pyaudio_clear(self):
        while self.__running:
            time.sleep(30)
            

    def __findInternalRecordingDevice(self, p):
        for i in range(p.get_device_count()):
            devInfo = p.get_device_info_by_index(i)
            if devInfo['name'].find(self.__device) >= 0 and devInfo['hostApi'] == 0:
                config_util.config['source']['record']['channels'] = devInfo['maxInputChannels']
                config_util.save_config(config_util.config)
                return i, devInfo
        util.log(1, '[!] No input devices!')
        return -1, None
    
    def stop(self):
        super().stop()
        self.__running = False
        try:
            self.stream.stop_stream()
            self.stream.close()
            self.paudio.terminate()
        except Exception as e:
                print(e)
                util.log(1, "Check devices!")
                    
        


#test for remote input, failed to implement
class DeviceInputListener(Recorder):
    def __init__(self, fei):
        super().__init__(fei)
        self.__running = True
        self.ngrok = None
        self.streamCache = None
        self.thread = MyThread(target=self.run)
        self.thread.start()  

    def run(self):
        self.streamCache = stream_util.StreamCache(1024*1024*20)
        if config_util.key_ngrok_cc_id and config_util.key_ngrok_cc_id is not None and config_util.key_ngrok_cc_id.strip() != "":
            MyThread(target=self.start_ngrok, args=[config_util.key_ngrok_cc_id]).start()
        addr = None
        while self.__running:
            try:
                
                data = b""
                while feiFei.deviceConnect:
                    data = feiFei.deviceConnect.recv(1024)
                    self.streamCache.write(data)
                    time.sleep(0.005)
                self.streamCache.clear()
         
            except Exception as err:
                pass
            time.sleep(1)

    def on_speaking(self, text):
        global feiFei

        if len(text) > 1:
            interact = Interact("mic", 1, {'user': '', 'msg': text})
            util.printInfo(3, "Voice", '{}'.format(interact.data["msg"]), time.time())
            feiFei.on_interact(interact)
            time.sleep(2)

    def get_stream(self):
        while not feiFei.deviceConnect:
            time.sleep(1)
            pass
        return self.streamCache

    def stop(self):
        super().stop()
        self.__running = False
        if config_util.key_ngrok_cc_id and config_util.key_ngrok_cc_id is not None and config_util.key_ngrok_cc_id.strip() != "":
            self.ngrok.stop()

def console_listener():
    global feiFei
    while __running:
        text = input()
        args = text.split(' ')

        if len(args) == 0 or len(args[0]) == 0:
            continue

        if args[0] == 'help':
            util.log(1, 'in <msg> \tconsole interaction')
            util.log(1, 'restart \trestart service')
            util.log(1, 'stop \t\tstop service')

        elif args[0] == 'stop':
            stop()
            break

        elif args[0] == 'restart':
            stop()
            time.sleep(0.1)
            start()

        elif args[0] == 'in':
            if len(args) == 1:
                util.log(1, 'wrong input！')
            msg = text[3:len(text)]
            util.printInfo(3, "console", '{}: {}'.format('console', msg))
            feiFei.last_quest_time = time.time()
            interact = Interact("console", 1, {'user': '', 'msg': msg})
            thr = MyThread(target=feiFei.on_interact, args=[interact])
            thr.start()
            thr.join()

        else:
            util.log(1, 'Unknow instruction.')

#Stop service
def stop():
    global feiFei
    global recorderListener
    global __running
    global deviceInputListener

    util.log(1, 'Stopping services...')
    __running = False
    if recorderListener is not None:
        util.log(1, 'Turning off recording services...')
        recorderListener.stop()
    if deviceInputListener is not None:
        util.log(1, 'Turning off remote voice input output services...')
        deviceInputListener.stop()
    util.log(1, 'Turning off core services...')
    feiFei.stop()
    util.log(1, 'Services turned off！')


def start():
    global feiFei
    global recorderListener
    global __running
    global deviceInputListener

    util.log(1, 'Starting services...')
    __running = True

    util.log(1, 'Load Config...')
    config_util.load_config()

    util.log(1, 'Starting core services...')
    feiFei = FeiFei()
    feiFei.start()

    record = config_util.config['source']['record']

    if record['enabled']:
        util.log(1, 'Starting recording services...')
        recorderListener = RecorderListener(record['device'], feiFei) 
        recorderListener.start()

    
    util.log(1,'Starting remote input devices...')
    deviceInputListener = DeviceInputListener(feiFei)
    deviceInputListener.start()

    util.log(1, 'Register instruction...')
    MyThread(target=console_listener).start()

    util.log(1, 'Done!')
    util.log(1, 'get help.')

    

if __name__ == '__main__':
    ws_server: MyServer = None
    feiFei: FeiFei = None
    recorderListener: Recorder = None
    start()
