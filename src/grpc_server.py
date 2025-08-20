import grpc
from concurrent import futures
import time
from datetime import datetime
import threading
from collections import deque

# Import generated protobuf classes
# These are created from chat.proto by the protoc compiler
import chat_pb2
import chat_pb2_grpc


class ChatServiceServicer(chat_pb2_grpc.ChatServiceServicer):
    """
    The main gRPC service implementation.
    This class handles all chat-related RPC calls from clients.
    
    Think of this as the "chat room manager" that:
    1. Receives messages from users
    2. Stores message history
    3. Broadcasts messages to all connected clients
    """
    
    def __init__(self):
        # Store last 100 messages in memory (simple message history)
        # deque with maxlen automatically removes oldest messages when full
        self.messages = deque(maxlen=100)
        
        # Keep track of all active client streams (who's listening for messages)
        # Each connected client gets their own MessageQueue in this list
        self.active_streams = []
        
        # Thread lock to prevent race conditions when multiple clients
        # connect/disconnect/send messages simultaneously
        self.lock = threading.Lock()
    
    def SendMessage(self, request, context):
        """
        Unary RPC: Handles a single message from a client.
        
        This is called when a user sends a chat message.
        It's like the "post office" - receive one message, deliver to everyone.
        
        Args:
            request: ChatMessage containing username, message, and timestamp
            context: gRPC context (connection info, metadata, etc.)
        
        Returns:
            ChatResponse indicating success/failure
        """
        # Add timestamp to the message (server-side timestamp for consistency)
        timestamp = datetime.now().isoformat()
        
        # Create a new ChatMessage protobuf object with all details
        message = chat_pb2.ChatMessage(
            username=request.username,
            message=request.message,
            timestamp=timestamp
        )
        
        # Thread-safe operations (multiple clients might send messages simultaneously)
        with self.lock:
            # Add to message history
            self.messages.append(message)
            
            # Broadcast to all connected clients
            # Using [:] creates a copy of the list to safely iterate
            # (in case a stream gets removed during iteration)
            for stream in self.active_streams[:]:
                try:
                    # Put message in each client's queue
                    stream.put(message)
                except:
                    # If client disconnected, remove from active streams
                    self.active_streams.remove(stream)
        
        # Return success response to the sender
        return chat_pb2.ChatResponse(
            success=True,
            message="Message sent successfully"
        )
    
    def StreamMessages(self, request, context):
        """
        Server Streaming RPC: Continuously sends messages to a client.
        
        This is the "radio broadcast" - once a client connects, they:
        1. Get all recent message history
        2. Continue receiving new messages in real-time
        
        Args:
            request: StreamRequest containing the username
            context: gRPC context (stays active for the entire stream)
        
        Yields:
            ChatMessage objects as they arrive
        """
        # Create a personal message queue for this client
        # Each client gets their own queue to prevent message loss
        message_queue = MessageQueue()
        
        # Register this client as an active listener
        with self.lock:
            self.active_streams.append(message_queue)
            
            # First, send all existing messages (catch up on history)
            # This ensures new users see recent conversation
            for msg in self.messages:
                yield msg
        
        # Now keep the stream alive and send new messages as they arrive
        try:
            # Keep streaming while the client is connected
            while context.is_active():
                # Wait for new messages (timeout prevents infinite blocking)
                message = message_queue.get(timeout=1)
                if message:
                    # Send the message to this specific client
                    yield message
        except:
            # Client disconnected or error occurred
            pass
        finally:
            # Clean up: remove this client from active streams
            with self.lock:
                if message_queue in self.active_streams:
                    self.active_streams.remove(message_queue)


class MessageQueue:
    """
    Thread-safe message queue for each connected client.
    
    This is like a personal mailbox for each client:
    - New messages get "put" into the mailbox
    - The client "gets" messages from their mailbox
    - Uses threading primitives to handle concurrent access safely
    """
    
    def __init__(self):
        # Queue to store messages for this specific client
        self.queue = deque()
        
        # Lock ensures thread-safe access to the queue
        # (multiple threads might add/remove messages simultaneously)
        self.lock = threading.Lock()
        
        # Event signals when new messages are available
        # (allows efficient waiting instead of constant polling)
        self.event = threading.Event()
    
    def put(self, item):
        """
        Add a new message to this client's queue.
        
        Called by SendMessage when broadcasting to all clients.
        Thread-safe: can be called by multiple threads simultaneously.
        
        Args:
            item: ChatMessage to add to the queue
        """
        with self.lock:
            # Add message to the queue
            self.queue.append(item)
            # Signal that a message is available (wake up waiting threads)
            self.event.set()
    
    def get(self, timeout=None):
        """
        Retrieve the next message from the queue.
        
        Called by StreamMessages to get messages for the client.
        Blocks until a message is available or timeout occurs.
        
        Args:
            timeout: Maximum seconds to wait for a message
        
        Returns:
            ChatMessage if available, None if timeout
        """
        # Wait for the event signal (new message available)
        if self.event.wait(timeout):
            with self.lock:
                if self.queue:
                    # Get the oldest message (FIFO - first in, first out)
                    item = self.queue.popleft()
                    
                    # If queue is now empty, clear the event
                    # (next get() will wait for new messages)
                    if not self.queue:
                        self.event.clear()
                    return item
        return None


def serve():
    """
    Start and run the gRPC server.
    
    This function:
    1. Creates a gRPC server with a thread pool
    2. Registers our ChatService implementation
    3. Binds to a port and starts listening
    4. Keeps the server running until interrupted
    """
    # Create gRPC server with a thread pool executor
    # max_workers=10 means up to 10 concurrent RPC calls can be handled
    # Each client connection gets its own thread from this pool
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Register our ChatServiceServicer with the server
    # This tells gRPC which class handles ChatService RPCs
    chat_pb2_grpc.add_ChatServiceServicer_to_server(
        ChatServiceServicer(), server
    )
    
    # Bind to port 50051 on all network interfaces
    # '[::]:50051' means IPv6 any address (also handles IPv4)
    # 'insecure' means no TLS/SSL (fine for development)
    server.add_insecure_port('[::]:50051')
    
    # Start the server (begins accepting connections)
    server.start()
    
    # Print confirmation with flush=True to ensure it's displayed immediately
    # (Python might buffer output otherwise)
    print("gRPC server started on port 50051", flush=True)
    
    # Keep the server running
    try:
        # Sleep for a day at a time (arbitrary long duration)
        # This keeps the main thread alive while the server handles requests
        while True:
            time.sleep(86400)  # 86400 seconds = 24 hours
    except KeyboardInterrupt:
        # Gracefully shutdown when Ctrl+C is pressed
        # The 0 parameter means stop immediately (no grace period)
        server.stop(0)


if __name__ == '__main__':
    # Only run the server if this file is executed directly
    # (not imported as a module)
    serve()