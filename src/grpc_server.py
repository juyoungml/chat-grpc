import grpc
from concurrent import futures
import time
from datetime import datetime
import threading
from collections import deque

import chat_pb2
import chat_pb2_grpc


class ChatServiceServicer(chat_pb2_grpc.ChatServiceServicer):
    def __init__(self):
        self.messages = deque(maxlen=100)
        self.active_streams = []
        self.lock = threading.Lock()
    
    def SendMessage(self, request, context):
        timestamp = datetime.now().isoformat()
        
        message = chat_pb2.ChatMessage(
            username=request.username,
            message=request.message,
            timestamp=timestamp
        )
        
        with self.lock:
            self.messages.append(message)
            
            for stream in self.active_streams[:]:
                try:
                    stream.put(message)
                except:
                    self.active_streams.remove(stream)
        
        return chat_pb2.ChatResponse(
            success=True,
            message="Message sent successfully"
        )
    
    def StreamMessages(self, request, context):
        message_queue = MessageQueue()
        
        with self.lock:
            self.active_streams.append(message_queue)
            
            for msg in self.messages:
                yield msg
        
        try:
            while context.is_active():
                message = message_queue.get(timeout=1)
                if message:
                    yield message
        except:
            pass
        finally:
            with self.lock:
                if message_queue in self.active_streams:
                    self.active_streams.remove(message_queue)


class MessageQueue:
    def __init__(self):
        self.queue = deque()
        self.lock = threading.Lock()
        self.event = threading.Event()
    
    def put(self, item):
        with self.lock:
            self.queue.append(item)
            self.event.set()
    
    def get(self, timeout=None):
        if self.event.wait(timeout):
            with self.lock:
                if self.queue:
                    item = self.queue.popleft()
                    if not self.queue:
                        self.event.clear()
                    return item
        return None


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_pb2_grpc.add_ChatServiceServicer_to_server(
        ChatServiceServicer(), server
    )
    server.add_insecure_port('[::]:50051')
    server.start()
    print("gRPC server started on port 50051", flush=True)
    
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    serve()