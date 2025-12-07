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


# --- Network & Buffer Parameters ---

# IP address of the server
SERVER_IP = '127.0.0.1'

# The port on the server that listens for RELIABLE UDP control commands (PLAY/STOP).
# This replaces the old SERVER_TCP_PORT.
SERVER_CONTROL_PORT = 50000

# Buffer size for receiving/sending data packets (general socket buffer)
BUFFER_SIZE = 65536 

# Maximum size for a single UDP packet (payload limit for video data)
UDP_PACKET_MAX_SIZE = 4096


# --- Streaming & Chunker Parameters ---

# Size of each chunk in bytes (e.g., 4KB)
CHUNK_SIZE = 4096  

# Target duration of buffer in milliseconds
TARGET_BUFFER_MS = 1000 

# Video Framerate (simulated)
VIDEO_FPS = 24
FRAME_INTERVAL_MS = 1000 / VIDEO_FPS