# gRPC Chat Application

An educational online chat application demonstrating the integration of gRPC, FastAPI, WebSockets, and raw HTML.

## Quick Start

```bash
# Terminal 1: Start gRPC server
make grpc

# Terminal 2: Start FastAPI server  
make web

# Open http://localhost:8000 in your browser
```

## Architecture

This application demonstrates a microservices architecture:

1. **gRPC Server** (`src/grpc_server.py`): Handles message storage and distribution
2. **FastAPI Server** (`src/fastapi_server.py`): Bridges WebSocket connections to gRPC
3. **HTML Frontend** (`static/index.html`): Pure HTML/CSS/JavaScript interface

## How It Works

1. Users connect via WebSocket through the FastAPI server
2. FastAPI translates WebSocket messages to gRPC calls
3. gRPC server manages message history and streaming
4. Messages are broadcast to all connected clients via gRPC streaming

## Commands

```bash
make proto  # Generate Python code from proto files
make grpc   # Start gRPC server (port 50051)
make web    # Start FastAPI server (port 8000)
make clean  # Remove generated proto files
```

## Educational Concepts Demonstrated

- **gRPC**: Protocol buffer definitions, unary and streaming RPCs
- **FastAPI**: WebSocket handling, async programming
- **WebSockets**: Real-time bidirectional communication
- **Microservices**: Service separation and communication patterns
- **Threading**: Concurrent message handling in Python

## Project Structure

```
learn-grpc/
├── protos/
│   └── chat.proto          # gRPC service definitions
├── src/
│   ├── chat_pb2.py        # Generated protobuf code
│   ├── chat_pb2_grpc.py   # Generated gRPC code
│   ├── grpc_server.py     # gRPC server implementation
│   └── fastapi_server.py  # FastAPI WebSocket bridge
├── static/
│   └── index.html         # Frontend interface
├── TUTORIAL.md            # Step-by-step learning guide
└── CLAUDE.md              # Project context for Claude AI
```

## Learn More

Check out [TUTORIAL.md](TUTORIAL.md) for a comprehensive step-by-step guide explaining all the concepts from scratch.