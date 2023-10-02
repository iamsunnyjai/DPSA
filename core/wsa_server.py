from asyncio import AbstractEventLoop

import websockets
import asyncio
import json
from abc import abstractmethod
from websockets.legacy.server import Serve

from scheduler.thread_manager import MyThread
from utils import util


class MyServer:
    def __init__(self, host='0.0.0.0', port=10000):
        self.__host = host  # ip
        self.__port = port  # port
        self.__listCmd = []  # msg list
        self.__server: Serve = None
        self.__event_loop: AbstractEventLoop = None
        self.__running = True
        self.__pending = None
        self.isConnect = False

    def __del__(self):
        self.stop_server()

    # receive
    async def __consumer_handler(self, websocket, path):
        async for message in websocket:
            await asyncio.sleep(0.01)
            await self.__consumer(message)
            
            
    # send
    async def __producer_handler(self, websocket, path):
        while self.__running:
            await asyncio.sleep(0.01)
            message = await self.__producer()
            if message:
                await websocket.send(message)
    
    async def __handler(self, websocket, path):
        self.isConnect = True
        util.log(1,"websocket connected:{}".format(self.__port))
        self.on_connect_handler()
        consumer_task = asyncio.ensure_future(self.__consumer_handler(websocket, path))#接收
        producer_task = asyncio.ensure_future(self.__producer_handler(websocket, path))#发送
        done, self.__pending = await asyncio.wait([consumer_task, producer_task], return_when=asyncio.FIRST_COMPLETED, )
        for task in self.__pending:
            task.cancel()
            self.isConnect = False
            util.log(1,"websocket disconnected:{}".format(self.__port))
            self.on_close_handler()
                
    async def __consumer(self, message):
        self.on_revice_handler(message)
    
    async def __producer(self):
        if len(self.__listCmd) > 0:
            message = self.on_send_handler(self.__listCmd.pop(0))
            return message
        else:
            return None


    @abstractmethod
    def on_revice_handler(self, message):
        pass

    @abstractmethod
    def on_connect_handler(self):
        pass
    
    @abstractmethod
    def on_send_handler(self, message):
        return message

    @abstractmethod
    def on_close_handler(self):
        pass

    #create server
    def __connect(self):
        self.__event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.__event_loop)
        self.__isExecute = True
        if self.__server:
            util.log(1, 'server already exist')
            return
        self.__server = websockets.serve(self.__handler, self.__host, self.__port)
        asyncio.get_event_loop().run_until_complete(self.__server)
        asyncio.get_event_loop().run_forever()

    #add cmd
    def add_cmd(self, content):
        if not self.__running:
            return
        jsonObj = json.dumps(content)
        self.__listCmd.append(jsonObj)

    # Start
    def start_server(self):
        MyThread(target=self.__connect).start()

    # Stop
    def stop_server(self):
        self.__running = False
        self.isConnect = False
        if self.__server is None:
            return
        self.__server.ws_server.close()
        self.__server = None
        try:
            all_tasks = asyncio.all_tasks(self.__event_loop)
            for task in all_tasks:
                while not task.cancel():
                    util.log(1, "Can not turn off！")
            self.__event_loop.stop()
            self.__event_loop.close()
        except BaseException as e:
            util.log(1, "Error: {}".format(e))



#ui server
class WebServer(MyServer):
    def __init__(self, host='0.0.0.0', port=10000):
        super().__init__(host, port)

    def on_revice_handler(self, message):
        pass
    
    def on_connect_handler(self):
        self.add_cmd({"panelMsg": "Waiting"})

    def on_send_handler(self, message):
        return message

    def on_close_handler(self):
        pass

#DH server
class HumanServer(MyServer):
    def __init__(self, host='0.0.0.0', port=10000):
        super().__init__(host, port)

    def on_revice_handler(self, message):
        pass
    
    def on_connect_handler(self):
        web_server_instance = get_web_instance()  
        web_server_instance.add_cmd({"is_connect": True}) 
        

    def on_send_handler(self, message):
        if not self.isConnect:
            return None
        return message

    def on_close_handler(self):
        web_server_instance = get_web_instance()  
        web_server_instance.add_cmd({"is_connect": False}) 

        

#test
class TestServer(MyServer):
    def __init__(self, host='0.0.0.0', port=10000):
        super().__init__(host, port)

    def on_revice_handler(self, message):
        print(message)
    
    def on_connect_handler(self):
        print("connected")
    
    def on_send_handler(self, message):
        return message
    
    def on_close_handler(self):
        pass

__instance: MyServer = None
__web_instance: MyServer = None


def new_instance(host='0.0.0.0', port=10000) -> MyServer:
    global __instance
    if __instance is None:
        __instance = HumanServer(host, port)
    return __instance


def new_web_instance(host='0.0.0.0', port=10000) -> MyServer:
    global __web_instance
    if __web_instance is None:
        __web_instance = WebServer(host, port)
    return __web_instance


def get_instance() -> MyServer:
    return __instance


def get_web_instance() -> MyServer:
    return __web_instance

if __name__ == '__main__':
    testServer = TestServer(host='0.0.0.0', port=10000)
    testServer.start_server()