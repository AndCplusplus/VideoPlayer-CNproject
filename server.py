"""
Video Streaming Server - UDP Only
Listens for reliable UDP control commands (PLAY/STOP) and streams video data
(unreliable UDP) back to the client.

This server now uses the VideoChunker to read and send real video data chunks.
"""

import socket
import threading
import struct
import time
import zlib
import os
import math

# Imports necessary network constants and video path/framerate
from config import SERVER_IP, SERVER_CONTROL_PORT, BUFFER_SIZE, VIDEO_PATH, VIDEO_FPS, SOURCE_DIR, CHUNK_SIZE
# Import the custom chunker class
from video_chunker import VideoChunker

# Protocol Constants (Must match client)
CMD_PLAY = 1
CMD_STOP = 2
END_OF_STREAM_FRAME_ID = 0xFFFFFFFF
CONTROL_PACKET_HEADER_SIZE = 9  # Type (B), SeqNum (I), PayloadLen (I)

# --- Utility: Video Streamer ---

class Streamer(threading.Thread):
    """
    Reads frames using VideoChunker and sends them via UDP.
    """
    def __init__(self, sock, client_addr, video_path):
        super().__init__()
        self.sock = sock
        self.client_addr = client_addr
        self._stop_event = threading.Event()
        self.video_path = video_path
        
        # Generate a unique connection ID based on client address
        # Using hash of client address to create a unique conn_id
        self.conn_id = hash(f"{client_addr[0]}:{client_addr[1]}") & 0xFFFFFFFF
        
        # Use the real FPS from config
        self.frame_rate = VIDEO_FPS
        self.frame_interval = 1.0 / self.frame_rate
        
        # Initialize the chunker for the specified video path
        try:
            self.chunker = VideoChunker(video_path)
            print(f"[STREAMER] Chunker initialized for video: {video_path}")
        except FileNotFoundError as e:
            print(f"[STREAMER] Error: {e}")
            self.chunker = None
            self.stop()
        
        print(f"[STREAMER] New streamer created for {client_addr} (conn_id: {self.conn_id}) at {self.frame_rate} FPS")

    def stop(self):
        """Signals the streamer thread to stop and closes the chunker."""
        print(f"[STREAMER] Stopping stream to {self.client_addr}")
        self._stop_event.set()
        if self.chunker:
            self.chunker.close()
            self.chunker = None

    def send_end_of_stream_marker(self):
        """Sends a special marker to the client to signal the end of the video."""
        print("[STREAMER] Sending End of Stream marker.")
        # End-of-stream marker uses special frame_id and zero values for other fields
        # Format: conn_id (I), frame_id (I), pts_ms (f), len (I), checksum (I)
        packet = struct.pack('!IIfII', self.conn_id, END_OF_STREAM_FRAME_ID, 0.0, 0, 0)
        self.sock.sendto(packet, self.client_addr)

    def run(self):
        if not self.chunker:
            print("[STREAMER] Cannot run, chunker failed to initialize.")
            self.send_end_of_stream_marker()
            return
            
        print(f"[STREAMER] Streaming started for {self.client_addr}...")
        
        while not self._stop_event.is_set():
            start_time = time.time()
            
            # 1. Get the next chunk from the file
            data_chunk, pts_ms, is_last = self.chunker.next_frame()

            if not data_chunk:
                print("[STREAMER] Chunker returned no data (EOF reached).")
                self.stop() # Stop the streaming thread
                break

            # 2. Compress the chunk data
            try:
                compressed_data = zlib.compress(data_chunk)
            except zlib.error as e:
                print(f"[STREAMER] Compression error: {e}. Dropping chunk.")
                continue

            # 3. Prepare and send the packet
            frame_id = self.chunker.frame_id - 1 # frame_id is incremented *after* reading
            # pts_ms is already provided by the chunker
            data_len = len(compressed_data)
            
            # Calculate checksum of the compressed data
            checksum = zlib.adler32(compressed_data) & 0xFFFFFFFF
            
            # Frame Data Packet Format: conn_id (I), frame_id (I), pts_ms (f), len (I), checksum (I), CompressedData (variable)
            # Header: 20 bytes total
            header = struct.pack('!IIfII', self.conn_id, frame_id, pts_ms, data_len, checksum)
            packet = header + compressed_data
            
            # Send the packet (Unreliable UDP)
            try:
                self.sock.sendto(packet, self.client_addr)
                if frame_id % 100 == 0:
                    print(f"[STREAMER] Sent frame {frame_id} (Size: {len(packet)} bytes) to {self.client_addr}")
            except Exception as e:
                print(f"[STREAMER] Error sending frame: {e}")
            
            # 4. Check if this was the last chunk from the file
            if is_last:
                print("[STREAMER] Reached end of file content.")
                self.stop()
                break

            # 5. Maintain frame rate timing
            time_spent = time.time() - start_time
            sleep_time = self.frame_interval - time_spent
            if sleep_time > 0:
                time.sleep(sleep_time)

        # Send the end of stream marker before exiting
        self.send_end_of_stream_marker()
        print("[STREAMER] Thread finished.")


# --- Main Server ---

class VideoServer:
    """Handles the reliable UDP control channel and manages the streaming thread."""
    def __init__(self, host=SERVER_IP, port=SERVER_CONTROL_PORT):
        self.host = host
        self.port = port
        self.udp_sock = None
        self.stream_thread = None
        self.current_client_addr = None
        self.is_running = False
        self.has_active_stream = False  # Track if stream exists (even if thread finished)

    def setup_socket(self):
        """Binds the single UDP socket for control and data transmission."""
        try:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.bind((self.host, self.port))
            self.udp_sock.settimeout(0.5)
            print(f"[SERVER] UDP Control/Data socket bound to {self.host}:{self.port}")
            self.is_running = True
            return True
        except Exception as e:
            print(f"[SERVER] Failed to bind socket: {e}")
            return False

    def send_control_ack(self, client_addr, ack_seq, total_chunks=None):
        """
        Sends an acknowledgment back to the client for a reliable control packet.
        For PLAY commands, includes total_chunks metadata.
        ACK Format: Type (B), AckedSeq (I), [TotalChunks (I) if provided]
        """
        ack_type = 10 # Custom ACK type
        if total_chunks is not None:
            # Extended ACK with metadata for PLAY commands
            ack_packet = struct.pack('!BII', ack_type, ack_seq, total_chunks)
        else:
            # Standard ACK for STOP and other commands
            ack_packet = struct.pack('!BI', ack_type, ack_seq)
        try:
            self.udp_sock.sendto(ack_packet, client_addr)
            if total_chunks is not None:
                print(f"[ACK] Sent ACK for Seq: {ack_seq} with total_chunks={total_chunks} to {client_addr}")
            else:
                print(f"[ACK] Sent ACK for Seq: {ack_seq} to {client_addr}")
        except Exception as e:
            print(f"[ACK] Failed to send ACK: {e}")

    def handle_control_command(self, packet, client_addr):
        """
        Processes a reliable control command (PLAY/STOP) and sends an ACK.
        
        Packet Format: Type (B), SeqNum (I), PayloadLen (I), Payload (variable)
        """
        # Initialize total_chunks to None for all command types
        total_chunks = None
        
        try:
            # Unpack control header
            cmd_type, seq_num, payload_len = struct.unpack('!BII', packet[:CONTROL_PACKET_HEADER_SIZE])
            payload = packet[CONTROL_PACKET_HEADER_SIZE:]

            # Decode payload for logging (e.g., "test.mp4 9000")
            decoded_payload = payload.decode('utf-8', errors='ignore')
            print(f"[CTRL] Received command {cmd_type} (Seq: {seq_num}) from {client_addr}. Payload: {decoded_payload}")

            if cmd_type == CMD_PLAY:
                if self.has_active_stream and (self.stream_thread and self.stream_thread.is_alive()):
                    print("[CTRL] Stream already active. Ignoring PLAY.")
                    total_chunks = None  # No new stream, so no total_chunks
                else:
                    # Clean up any previous stream thread if it exists
                    if self.stream_thread:
                        if self.stream_thread.is_alive():
                            self.stream_thread.stop()
                            self.stream_thread.join(timeout=0.5)
                        self.stream_thread = None
                    
                    # Parse payload: "video_filename client_udp_port"
                    parts = decoded_payload.split()
                    video_filename = parts[0]
                    client_data_port = int(parts[1]) 
                    
                    # Construct full path to video file in video_source directory
                    video_path = os.path.join(SOURCE_DIR, video_filename)
                    
                    # Validate that the video file exists
                    if not os.path.exists(video_path):
                        print(f"[CTRL] Error: Video file not found: {video_path}")
                        # ACK will be sent at end of function without total_chunks
                        total_chunks = None
                    else:
                        # Calculate total chunks from file size
                        try:
                            file_size = os.path.getsize(video_path)
                            total_chunks = math.ceil(file_size / CHUNK_SIZE)
                        except Exception as e:
                            print(f"[CTRL] Warning: Could not calculate total chunks: {e}")
                            total_chunks = None
                        
                        self.current_client_addr = (client_addr[0], client_data_port)
                        
                        # Start the streamer thread with the requested video file
                        self.stream_thread = Streamer(self.udp_sock, self.current_client_addr, video_path)
                        self.stream_thread.start()
                        self.has_active_stream = True
                        print(f"[CTRL] Starting stream: {video_path} to {self.current_client_addr}")

            elif cmd_type == CMD_STOP:
                total_chunks = None  # No metadata for STOP
                if self.has_active_stream:
                    if self.stream_thread and self.stream_thread.is_alive():
                        self.stream_thread.stop()
                        self.stream_thread.join(timeout=2.0)
                    self.stream_thread = None
                    self.current_client_addr = None
                    self.has_active_stream = False
                    print("[CTRL] Stopped active stream.")
                else:
                    print("[CTRL] Received STOP, but no stream was active.")
            
            # Send ACK for the command to fulfill the reliable protocol
            # Include total_chunks for PLAY commands
            if cmd_type == CMD_PLAY:
                self.send_control_ack(client_addr, seq_num, total_chunks)
            else:
                self.send_control_ack(client_addr, seq_num)

        except struct.error as e:
            print(f"[CTRL] Error unpacking control header: {e}. Packet size: {len(packet)}")
        except Exception as e:
            print(f"[CTRL] Unhandled error during command handling: {e}")


    def start_listener(self):
        """Main loop to listen for control packets."""
        print("[SERVER] Listener thread started. Awaiting commands...")
        while self.is_running:
            try:
                # Receive any packet
                packet, client_addr = self.udp_sock.recvfrom(BUFFER_SIZE)
                
                # Assume any packet larger than the control header is a control command
                if len(packet) >= CONTROL_PACKET_HEADER_SIZE:
                    self.handle_control_command(packet, client_addr)
                else:
                    # This might be an unexpected stray packet, or a corrupted control packet
                    print(f"[SERVER] Received small unexpected packet from {client_addr}. Dropping.")

            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    print(f"[SERVER] Listener error: {e}")
                break
        
        print("[SERVER] Listener finished.")

    def shutdown(self):
        """Stops streaming and closes the socket."""
        self.is_running = False
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.stop()
            self.stream_thread.join(timeout=2.0)
        self.has_active_stream = False
        
        if self.udp_sock:
            self.udp_sock.close()
            print("[SERVER] Socket closed.")

def main():
    server = VideoServer()
    if not server.setup_socket():
        return

    listener_thread = threading.Thread(target=server.start_listener, daemon=True)
    listener_thread.start()

    try:
        # Keep the main thread alive until user interrupts
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.shutdown()
        
    print("Server application closed.")

if __name__ == '__main__':
    main()