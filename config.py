# config.py

import os

# --- File Paths ---
# Base directory of the project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Directory containing the source video
SOURCE_DIR = os.path.join(BASE_DIR, 'video_source')

# Directory to store the generated chunks
CHUNKS_DIR = os.path.join(BASE_DIR, 'video_chunks')

# Name of the source video file (Must exist in video_source/)
VIDEO_FILENAME = 'test.mp4'
VIDEO_PATH = os.path.join(SOURCE_DIR, VIDEO_FILENAME)

# --- Streaming Parameters ---
# Size of each chunk in bytes (e.g., 4KB)
# A standard UDP payload is often ~1400 bytes, but your prompt suggested 1-4KB.
CHUNK_SIZE = 4096  

# Target duration of buffer in milliseconds
TARGET_BUFFER_MS = 1000 

# Video Framerate (simulated)
VIDEO_FPS = 24
FRAME_INTERVAL_MS = 1000 / VIDEO_FPS
UDP_PACKET_MAX_SIZE = 4096
SERVER_IP = '127.0.0.1'
SERVER_TCP_PORT = 8000

BUFFER_SIZE = 65536
