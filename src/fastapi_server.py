from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import grpc
import asyncio
from typing import Dict, Set
import json

# Add src directory to Python path so we can import generated protobuf files
import sys
sys.path.append('./src')
import chat_pb2
import chat_pb2_grpc

# Create FastAPI application instance
app = FastAPI()


class ConnectionManager:
    """
    Manages WebSocket connections and gRPC communication.
    
    This class is the "bridge" between:
    - WebSocket connections from browsers (can't use gRPC directly)
    - gRPC connection to the chat server (handles actual chat logic)
    
    Think of it as a translator at the UN:
    - Browsers speak "WebSocket language"
    - gRPC server speaks "Protocol Buffer language"
    - This manager translates between them
    """
    
    def __init__(self):
        # Dictionary mapping username -> WebSocket connection
        # Keeps track of who's connected via WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        
        # gRPC connection to the chat server (lazy initialized)
        self.grpc_channel = None  # The connection to gRPC server
        self.grpc_stub = None     # The client stub for making RPC calls
    
    async def connect(self, websocket: WebSocket, username: str):
        """
        Accept a new WebSocket connection and register the user.
        
        This is called when someone clicks "Join Chat" in the browser.
        
        Args:
            websocket: The WebSocket connection from the browser
            username: The username chosen by the user
        """
        # Accept the WebSocket connection (complete the handshake)
        await websocket.accept()
        
        # Store the connection so we can send messages to this user later
        self.active_connections[username] = websocket
        
        # Initialize gRPC connection if this is the first user
        # (lazy initialization - only connect when needed)
        if not self.grpc_channel:
            # Create channel to gRPC server at localhost:50051
            self.grpc_channel = grpc.insecure_channel('localhost:50051')
            # Create stub (client) for making RPC calls
            self.grpc_stub = chat_pb2_grpc.ChatServiceStub(self.grpc_channel)
    
    def disconnect(self, username: str):
        """
        Remove a user's WebSocket connection when they disconnect.
        
        Called when:
        - User closes their browser tab
        - Connection is lost
        - User manually disconnects
        
        Args:
            username: The username to disconnect
        """
        if username in self.active_connections:
            del self.active_connections[username]
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """
        Send a message to a specific user.
        
        Used for sending error messages or personal notifications.
        
        Args:
            message: The message to send (as JSON string)
            websocket: The specific WebSocket connection to send to
        """
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        """
        Send a message to all connected users.
        
        Used for system messages like "User left the chat".
        
        Args:
            message: The message to broadcast (as JSON string)
        """
        disconnected = []
        # Try to send to each connected user
        for username, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except:
                # If sending fails, mark for disconnection
                disconnected.append(username)
        
        # Clean up disconnected users
        for username in disconnected:
            self.disconnect(username)


# Create a global connection manager instance
# This single instance manages all WebSocket connections
manager = ConnectionManager()


@app.get("/")
async def get():
    """
    Serve the HTML chat interface.
    
    This endpoint returns the main chat UI when users visit http://localhost:8000
    It's a simple static file server for our HTML page.
    """
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    """
    WebSocket endpoint for chat connections.
    
    This is the main handler for each user's chat session.
    It:
    1. Accepts the WebSocket connection
    2. Starts streaming messages from gRPC to this user
    3. Receives messages from this user and sends to gRPC
    4. Handles disconnections gracefully
    
    Args:
        websocket: The WebSocket connection from the browser
        username: The username from the URL path (e.g., /ws/alice)
    """
    # Accept and register this WebSocket connection
    await manager.connect(websocket, username)
    
    # Start a background task to stream messages from gRPC to this user
    # This runs concurrently with the main message-receiving loop below
    stream_task = asyncio.create_task(stream_messages(username, websocket))
    
    try:
        # Main loop: receive messages from browser and forward to gRPC
        while True:
            # Wait for a message from the browser (blocking)
            data = await websocket.receive_text()
            
            # Parse the JSON message from browser
            # Expected format: {"message": "Hello everyone!"}
            message_data = json.loads(data)
            
            # Create a gRPC ChatMessage protobuf object
            request = chat_pb2.ChatMessage(
                username=username,
                message=message_data['message'],
                timestamp=""  # Server will add timestamp
            )
            
            # Send the message to gRPC server using unary RPC
            response = manager.grpc_stub.SendMessage(request)
            
            # Check if the message was successfully sent
            if not response.success:
                # Send error back to this user only
                await manager.send_personal_message(
                    json.dumps({"error": response.message}),
                    websocket
                )
    
    except WebSocketDisconnect:
        # User disconnected normally (closed browser tab, etc.)
        manager.disconnect(username)
        
        # Cancel the streaming task
        stream_task.cancel()
        
        # Notify other users that this user left
        await manager.broadcast(json.dumps({
            "username": "System",
            "message": f"{username} left the chat",
            "timestamp": ""
        }))
    except Exception as e:
        # Unexpected error occurred
        print(f"Error: {e}")
        manager.disconnect(username)
        stream_task.cancel()


async def stream_messages(username: str, websocket: WebSocket):
    """
    Stream messages from gRPC server to a WebSocket client.
    
    This function runs as a background task for each connected user.
    It continuously receives messages from the gRPC stream and forwards
    them to the user's WebSocket connection.
    
    CRITICAL: This handles the async/sync mismatch between:
    - gRPC's synchronous/blocking streaming
    - FastAPI's asynchronous WebSocket handling
    
    Args:
        username: The username to stream messages for
        websocket: The WebSocket connection to send messages to
    """
    try:
        # Create a StreamRequest to start receiving messages
        request = chat_pb2.StreamRequest(username=username)
        
        # Get the current event loop (needed for run_in_executor)
        loop = asyncio.get_event_loop()
        
        # Small delay to ensure WebSocket connection is fully established
        await asyncio.sleep(0.1)
        
        # IMPORTANT: Handle the blocking gRPC stream in a thread pool
        # This prevents the gRPC blocking calls from freezing the async event loop
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Start the gRPC streaming RPC
            # This returns an iterator that blocks when waiting for messages
            stream_iter = manager.grpc_stub.StreamMessages(request)
            
            while True:
                try:
                    # Run the blocking next() call in a separate thread
                    # This is THE KEY FIX that prevents the WebSocket from hanging
                    # 
                    # What's happening here:
                    # 1. next(stream_iter) is a BLOCKING call that waits for gRPC messages
                    # 2. run_in_executor runs it in a thread pool thread
                    # 3. await future waits for the result WITHOUT blocking the event loop
                    future = loop.run_in_executor(
                        executor, 
                        lambda: next(stream_iter, None)  # None is returned when stream ends
                    )
                    message = await future
                    
                    # Check if stream has ended
                    if message is None:
                        break
                    
                    # Convert protobuf message to JSON and send via WebSocket
                    await websocket.send_text(json.dumps({
                        "username": message.username,
                        "message": message.message,
                        "timestamp": message.timestamp
                    }))
                    
                except StopIteration:
                    # gRPC stream ended normally
                    break
                except Exception as e:
                    # Error processing the stream
                    print(f"Stream processing error: {e}")
                    break
                    
    except Exception as e:
        # Error setting up the stream
        print(f"Stream error: {e}")


if __name__ == "__main__":
    """
    Run the FastAPI server directly if this file is executed.
    
    This is mainly for development/testing. In production, you'd typically
    run with: uvicorn src.fastapi_server:app --host 0.0.0.0 --port 8000
    """
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)