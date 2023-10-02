from enum import Enum


class EnumVoice(Enum):
    JANE = {
        "name": "Jane",
        "voiceName": "en-US-JaneNeural",
        "styleList": {
            "angry": "angry",
            "lyrical": "lyrical",
            "calm": "gentle",
            "assistant": "affectionate",
            "cheerful": "cheerful"
        }
    }
    JENNY = {
        "name": "Jenny",
        "voiceName": "en-US-JennyNeural",
        "styleList": {
            "angry": "angry",
            "lyrical": "disgruntled",
            "calm": "calm",
            "assistant": "assistant",
            "cheerful": "cheerful"
        }
    }


def get_voice_list():
    return [EnumVoice.JENNY, EnumVoice.JANE]


def get_voice_of(name):
    for voice in get_voice_list():
        if voice.name == name:
            return voice
    return None
