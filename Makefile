.PHONY: proto grpc web run clean

proto:
	uv run python -m grpc_tools.protoc -I./protos --python_out=./src --grpc_python_out=./src ./protos/chat.proto

grpc:
	uv run python src/grpc_server.py

web:
	uv run uvicorn src.fastapi_server:app --reload --host 0.0.0.0 --port 8000

run:
	@echo "Starting gRPC and FastAPI servers..."
	@echo "Run 'make grpc' in one terminal and 'make web' in another"
	@echo "Or use two separate terminals:"
	@echo "  Terminal 1: make grpc"
	@echo "  Terminal 2: make web"

clean:
	rm -f src/chat_pb2.py src/chat_pb2_grpc.py