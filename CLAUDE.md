# Project Context for Claude

## Project Overview
This is an educational chat application demonstrating gRPC and WebSocket integration. The project uses:
- Python with `uv` for dependency management
- gRPC for backend message handling
- FastAPI for WebSocket-to-gRPC bridging
- Raw HTML/CSS/JS for the frontend

## Project Structure
```
learn-grpc/
├── protos/              # Protocol Buffer definitions
│   └── chat.proto       # Chat service and message definitions
├── src/                 # Source code
│   ├── chat_pb2.py     # Generated from proto (DO NOT EDIT)
│   ├── chat_pb2_grpc.py # Generated from proto (DO NOT EDIT)
│   ├── grpc_server.py   # gRPC server implementation
│   └── fastapi_server.py # FastAPI WebSocket bridge
├── static/              # Frontend files
│   └── index.html       # Chat UI
├── Makefile            # Build commands
├── README.md           # Project overview
└── TUTORIAL.md         # Step-by-step educational guide
```

## Key Commands
- `make proto` - Regenerate Python files from proto definitions
- `make grpc` - Start gRPC server (port 50051)
- `make web` - Start FastAPI server (port 8000)
- `make run` - Start both servers
- `make clean` - Remove generated files

## Development Workflow
1. Always use `uv` for package management (`uv add`, `uv run`)
2. Modify proto files → run `make proto` to regenerate
3. Test with `make grpc` in one terminal, `make web` in another
4. Access application at http://localhost:8000

## Architecture Notes
- **gRPC Server**: Handles message storage and streaming to clients
- **FastAPI Server**: Bridges WebSocket connections from browsers to gRPC
- **Message Flow**: Browser ↔ WebSocket ↔ FastAPI ↔ gRPC ↔ gRPC Server
- Uses threading for concurrent connections
- Messages stored in memory (deque with max 100 messages)

## Important Files
- `protos/chat.proto`: Defines the service contract - modify this to add features
- `src/grpc_server.py`: Core chat logic - modify for persistence, auth, etc.
- `src/fastapi_server.py`: WebSocket handling - modify for additional endpoints
- `static/index.html`: UI - kept simple and educational with no frameworks

## Common Tasks
- **Add new message field**: Update proto → `make proto` → update Python code
- **Add authentication**: Extend proto with auth messages, update servers
- **Add persistence**: Replace in-memory deque in grpc_server.py
- **Scale horizontally**: Run multiple FastAPI instances, single gRPC server

## Testing
Open multiple browser tabs/windows at http://localhost:8000 with different usernames to test chat functionality.

## Dependencies (managed by uv)
- grpcio, grpcio-tools: gRPC framework
- fastapi, uvicorn: Web framework and server
- websockets: WebSocket support

## Notes for Future Development
- Consider adding message persistence (SQLite/PostgreSQL)
- Could add user authentication/sessions
- Room/channel support would require proto changes
- File sharing could use gRPC streaming
- Consider adding reconnection logic for dropped connections