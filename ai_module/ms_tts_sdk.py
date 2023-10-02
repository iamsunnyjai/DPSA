import time

import azure.cognitiveservices.speech as speechsdk
import asyncio
import sys
from core import tts_voice
from core.tts_voice import EnumVoice
from utils import util, config_util
from utils import config_util as cfg
import pygame
import edge_tts




class Speech:
    def __init__(self):
        self.ms_tts = False
        if config_util.key_ms_tts_key and config_util.key_ms_tts_key is not None and config_util.key_ms_tts_key.strip() != "":
            self.__speech_config = speechsdk.SpeechConfig(subscription=cfg.key_ms_tts_key, region=cfg.key_ms_tts_region)
            self.__speech_config.speech_recognition_language = "en-US"
            self.__speech_config.speech_synthesis_voice_name = "en-US-JaneNeural"
            self.__speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)
            self.__synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.__speech_config, audio_config=None)
            self.ms_tts = True
        self.__connection = None
        self.__history_data = []


    def __get_history(self, voice_name, style, text):
        for data in self.__history_data:
            if data[0] == voice_name and data[1] == style and data[2] == text:
                return data[3]
        return None

    def connect(self):
        if self.ms_tts:
            self.__connection = speechsdk.Connection.from_speech_synthesizer(self.__synthesizer)
            self.__connection.open(True)
        util.log(1, "TTS connected！")

    def close(self):
        if self.__connection is not None:
            self.__connection.close()

    #gen mp3
    async def get_edge_tts(self,text,voice,file_url) -> None:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(file_url)

    """
    tts
    :param text: text
    :param style: style
    :returns: path
    """

    def to_sample(self, text, style):
        if self.ms_tts:
            voice_type = tts_voice.get_voice_of(config_util.config["attribute"]["voice"])
            voice_name = EnumVoice.JENNY.value["voiceName"]
            if voice_type is not None:
                voice_name = voice_type.value["voiceName"]
            history = self.__get_history(voice_name, style, text)
            if history is not None:
                return history
            ssml = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">' \
                   '<voice name="{}">' \
                   '<mstts:express-as style="{}" styledegree="{}">' \
                   '{}' \
                   '</mstts:express-as>' \
                   '</voice>' \
                   '</speak>'.format(voice_name, style, 1.8, text)
            result = self.__synthesizer.speak_ssml(ssml)
            audio_data_stream = speechsdk.AudioDataStream(result)

            file_url = './samples/sample-' + str(int(time.time() * 1000)) + '.mp3'
            audio_data_stream.save_to_wav_file(file_url)
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                self.__history_data.append((voice_name, style, text, file_url))
                return file_url
            else:
                util.log(1, "[x] TTS failed！")
                util.log(1, "[x] Reason: " + str(result.reason))
                return None
        else:
            voice_type = tts_voice.get_voice_of(config_util.config["attribute"]["voice"])
            voice_name = EnumVoice.JENNY.value["voiceName"]
            if voice_type is not None:
                voice_name = voice_type.value["voiceName"]
            history = self.__get_history(voice_name, style, text)
            if history is not None:
                return history
            ssml = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="zh-CN">' \
                   '<voice name="{}">' \
                   '<mstts:express-as style="{}" styledegree="{}">' \
                   '{}' \
                   '</mstts:express-as>' \
                   '</voice>' \
                   '</speak>'.format(voice_name, style, 1.8, text)
            try:
                file_url = './samples/sample-' + str(int(time.time() * 1000)) + '.mp3'
                asyncio.new_event_loop().run_until_complete(self.get_edge_tts(text,voice_name,file_url))
                self.__history_data.append((voice_name, style, text, file_url))
            except Exception as e :
                util.log(1, "[x] TTS failed！")
                util.log(1, "[x] Reason: " + str(str(e)))
                file_url = None
            return file_url


if __name__ == '__main__':
    cfg.load_config()
    sp = Speech()
    sp.connect()
    text = """This is a test audio"""
    s = sp.to_sample(text, "cheerful")

    print(s)
    sp.close()

