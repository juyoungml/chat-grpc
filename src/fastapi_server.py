from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import grpc
import asyncio
from typing import Dict, Set
import json

import sys
sys.path.append('./src')
import chat_pb2
import chat_pb2_grpc


app = FastAPI()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.grpc_channel = None
        self.grpc_stub = None
    
    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections[username] = websocket
        
        if not self.grpc_channel:
            self.grpc_channel = grpc.insecure_channel('localhost:50051')
            self.grpc_stub = chat_pb2_grpc.ChatServiceStub(self.grpc_channel)
    
    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        disconnected = []
        for username, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except:
                disconnected.append(username)
        
        for username in disconnected:
            self.disconnect(username)


manager = ConnectionManager()


@app.get("/")
async def get():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(websocket, username)
    
    stream_task = asyncio.create_task(stream_messages(username, websocket))
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            request = chat_pb2.ChatMessage(
                username=username,
                message=message_data['message'],
                timestamp=""
            )
            
            response = manager.grpc_stub.SendMessage(request)
            
            if not response.success:
                await manager.send_personal_message(
                    json.dumps({"error": response.message}),
                    websocket
                )
    
    except WebSocketDisconnect:
        manager.disconnect(username)
        stream_task.cancel()
        await manager.broadcast(json.dumps({
            "username": "System",
            "message": f"{username} left the chat",
            "timestamp": ""
        }))
    except Exception as e:
        print(f"Error: {e}")
        manager.disconnect(username)
        stream_task.cancel()


async def stream_messages(username: str, websocket: WebSocket):
    try:
        request = chat_pb2.StreamRequest(username=username)
        
        # Run the gRPC streaming in a thread to avoid blocking the asyncio event loop
        loop = asyncio.get_event_loop()
        
        def stream_generator():
            try:
                for message in manager.grpc_stub.StreamMessages(request):
                    yield message
            except Exception as e:
                print(f"gRPC stream error: {e}")
        
        # Process messages from gRPC stream
        await asyncio.sleep(0.1)  # Small delay to ensure connection is ready
        
        # Create a thread-safe way to handle the blocking gRPC stream
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            stream_iter = manager.grpc_stub.StreamMessages(request)
            while True:
                try:
                    # Get next message from gRPC stream in a thread
                    future = loop.run_in_executor(executor, lambda: next(stream_iter, None))
                    message = await future
                    
                    if message is None:
                        break
                        
                    await websocket.send_text(json.dumps({
                        "username": message.username,
                        "message": message.message,
                        "timestamp": message.timestamp
                    }))
                except StopIteration:
                    break
                except Exception as e:
                    print(f"Stream processing error: {e}")
                    break
                    
    except Exception as e:
        print(f"Stream error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)