import socket
import threading
import struct
import time
import sys
import zlib  # For CRC32 checksum

from config import SERVER_IP, SERVER_TCP_PORT, CHUNK_SIZE, SOURCE_DIR, FRAME_INTERVAL_MS, BUFFER_SIZE
from video_chunker import VideoChunker

# Protocol Constants
CMD_PLAY = 1
CMD_STOP = 2

# End of stream marker (max 32-bit unsigned integer)
END_OF_STREAM_FRAME_ID = 0xFFFFFFFF


class VideoServer:
    def __init__(self):
        # TCP Socket for Control Connection
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.bind((SERVER_IP, SERVER_TCP_PORT))
        
        # UDP Socket for Data Streaming (Fire and Forget)
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        print(f"Server listening on TCP {SERVER_IP}:{SERVER_TCP_PORT}")

    def start(self):
        self.tcp_sock.listen(5)
        try:
            while True:
                client_sock, addr = self.tcp_sock.accept()
                print(f"New connection from {addr}")
                
                # Create a dedicated thread for this client
                client_thread = threading.Thread(
                    target=self.handle_client, 
                    args=(client_sock, addr)
                )
                client_thread.daemon = True # Kills thread if server closes
                client_thread.start()
        except KeyboardInterrupt:
            print("\nServer shutting down...")
        finally:
            self.tcp_sock.close()
            self.udp_sock.close()

    def handle_client(self, conn, addr):
        """
        Handles the TCP control channel for a single client.
        Waits for PLAY or STOP commands.
        """
        is_streaming = False
        client_udp_port = None
        video_filename = None
        
        try:
            while True:
                # 1. Receive the Fixed Header (9 Bytes based on your design)
                # Format: ! = Network Endian
                # B = Command Type (1 byte)
                # I = Sequence Number (4 bytes)
                # I = Payload Length (4 bytes)
                header_data = conn.recv(9)
                if not header_data:
                    break # Client closed connection

                cmd_type, seq_num, payload_len = struct.unpack('!BII', header_data)
                
                # 2. Receive the Variable Payload (if any)
                payload_data = b""
                if payload_len > 0:
                    payload_data = conn.recv(payload_len)

                # 3. Process Command
                if cmd_type == CMD_PLAY:
                    # Parse payload for arguments: e.g., "video.mp4 9000"
                    payload_str = payload_data.decode('utf-8')
                    try:
                        video_filename, port_str = payload_str.split()
                        client_udp_port = int(port_str)
                        
                        print(f"[{addr}] Request PLAY: {video_filename} to UDP port {client_udp_port}")
                        
                        # Start streaming in a separate method (or thread)
                        is_streaming = True
                        self.stream_video(addr[0], client_udp_port, video_filename, lambda: is_streaming)
                        
                    except ValueError:
                        print(f"[{addr}] Malformed PLAY payload: {payload_str}")

                elif cmd_type == CMD_STOP:
                    print(f"[{addr}] Request STOP")
                    is_streaming = False # This flag stops the stream_video loop
                    break

        except Exception as e:
            print(f"[{addr}] Error: {e}")
        finally:
            conn.close()
            print(f"[{addr}] Connection closed")

    def stream_video(self, client_ip, client_port, filename, check_active_callback):
        """
        Reads video chunks and sends them via UDP.
        check_active_callback: A function that returns False if we should stop.
        """
        print(f"Starting UDP stream to {client_ip}:{client_port}...")
        
        chunker = VideoChunker(SOURCE_DIR + "/" + filename)

        frame_id = 0
        conn_id = 101 # Unique ID for this client session
        
        while check_active_callback():
            chunk_data, pts_ms, is_last = chunker.next_frame()

            if chunk_data is None:
                print("End of stream reached.")
                # Send end-of-stream signal to client
                self._send_end_of_stream(client_ip, client_port, conn_id)
                break

            # Calculate Checksum (CRC32)
            checksum = zlib.crc32(chunk_data) & 0xffffffff
            data_len = len(chunk_data)

            # Pack UDP Header
            # Format: ! = Network Endian
            # I = conn_id (4 bytes)
            # I = frame_id (4 bytes)
            # I = pts_ms (4 bytes)
            # I = len (4 bytes)
            # I = checksum (4 bytes)
            udp_header = struct.pack('!IIIII', 
                                      int(conn_id), 
                                      int(chunker.frame_id), 
                                      int(pts_ms),
                                      int(data_len), 
                                      int(checksum))            
            # Send Packet (Header + Data)
            packet = udp_header + chunk_data
            self.udp_sock.sendto(packet, (client_ip, client_port))

            time.sleep(FRAME_INTERVAL_MS / 1000.0)
            
            # Check if this was the last frame
            if is_last:
                print("Last frame sent. Sending end-of-stream signal...")
                self._send_end_of_stream(client_ip, client_port, conn_id)
                break

        chunker.close()
        print(f"UDP stream to {client_ip}:{client_port} closed")
    
    def _send_end_of_stream(self, client_ip, client_port, conn_id):
        """
        Send an end-of-stream signal to the client.
        Uses frame_id = 0xFFFFFFFF as the marker.
        """
        # Create empty payload for end-of-stream marker
        eos_payload = b"END_OF_STREAM"
        checksum = zlib.crc32(eos_payload) & 0xffffffff
        data_len = len(eos_payload)
        
        # Pack UDP Header with special frame_id
        udp_header = struct.pack('!IIIII',
                                  int(conn_id),
                                  END_OF_STREAM_FRAME_ID,  # Special frame_id for end-of-stream
                                  0,  # pts_ms (not used for EOS)
                                  int(data_len),
                                  int(checksum))
        
        # Send end-of-stream packet
        packet = udp_header + eos_payload
        self.udp_sock.sendto(packet, (client_ip, client_port))
        print(f"Sent end-of-stream signal to {client_ip}:{client_port}")

if __name__ == "__main__":
    server = VideoServer()
    server.start()