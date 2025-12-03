"""
Video Streaming Client - Headless Player
Implements hybrid TCP (Control) + UDP (Data) protocol for video streaming.
"""

import socket
import threading
import struct
import time
import queue
import zlib
from config import SERVER_IP, SERVER_TCP_PORT, BUFFER_SIZE

# Protocol Constants
CMD_PLAY = 1
CMD_STOP = 2

# End of stream marker (max 32-bit unsigned integer)
END_OF_STREAM_FRAME_ID = 0xFFFFFFFF

# Pre-buffering threshold
PREBUFFER_FRAMES = 10


class Metrics:
    """Tracks playback metrics for the video stream."""
    
    def __init__(self):
        self.total_frames_played = 0
        self.total_frames_dropped = 0
        self.total_stalls = 0
        self.max_delay = 0.0
        self.stall_durations = []
        self.frame_delays = []
        self.lock = threading.Lock()
    
    def record_frame_played(self, delay_ms=0.0):
        """Record a successfully played frame."""
        with self.lock:
            self.total_frames_played += 1
            if delay_ms > 0:
                self.frame_delays.append(delay_ms)
                self.max_delay = max(self.max_delay, delay_ms)
    
    def record_frame_dropped(self):
        """Record a dropped frame (sequence gap detected)."""
        with self.lock:
            self.total_frames_dropped += 1
    
    def record_stall(self, duration_ms=0.0):
        """Record a playback stall."""
        with self.lock:
            self.total_stalls += 1
            if duration_ms > 0:
                self.stall_durations.append(duration_ms)
    
    def get_summary(self):
        """Get a formatted summary of all metrics."""
        with self.lock:
            avg_delay = sum(self.frame_delays) / len(self.frame_delays) if self.frame_delays else 0.0
            avg_stall = sum(self.stall_durations) / len(self.stall_durations) if self.stall_durations else 0.0
            
            # Calculate 95th percentile delay
            sorted_delays = sorted(self.frame_delays)
            p95_delay = sorted_delays[int(len(sorted_delays) * 0.95)] if sorted_delays else 0.0
            
            return {
                'total_frames_played': self.total_frames_played,
                'total_frames_dropped': self.total_frames_dropped,
                'total_stalls': self.total_stalls,
                'max_delay_ms': self.max_delay,
                'avg_delay_ms': avg_delay,
                'p95_delay_ms': p95_delay,
                'avg_stall_duration_ms': avg_stall
            }


class VideoClient:
    """Main client class for video streaming."""
    
    def __init__(self):
        self.tcp_sock = None
        self.udp_sock = None
        self.frame_queue = queue.PriorityQueue()  # Priority queue ordered by frame_id
        self.metrics = Metrics()
        
        # Control flags
        self.is_playing = False
        self.is_receiving = False
        self.stream_ended = False  # Flag to indicate stream has ended
        self.expected_frame_id = 0
        self.seq_num = 0
        
        # Threads
        self.udp_thread = None
        self.player_thread = None
    
    def connect_tcp(self):
        """Establish TCP connection to server."""
        try:
            self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_sock.connect((SERVER_IP, SERVER_TCP_PORT))
            print(f"Connected to server at {SERVER_IP}:{SERVER_TCP_PORT}")
            return True
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            return False
    
    def send_tcp_command(self, cmd_type, payload=b""):
        """
        Send a TCP control command to the server.
        
        Packet structure: struct.pack('!BII', cmd_type, seq_num, payload_len)
        """
        try:
            payload_len = len(payload)
            header = struct.pack('!BII', cmd_type, self.seq_num, payload_len)
            packet = header + payload
            self.tcp_sock.sendall(packet)
            self.seq_num += 1
            return True
        except Exception as e:
            print(f"Error sending TCP command: {e}")
            return False
    
    def play_video(self, video_filename, udp_port):
        """
        Send PLAY command and start UDP receiver and player threads.
        
        Payload format: "<video_filename> <udp_port>"
        """
        if self.is_playing:
            print("Already playing a video. Send STOP first.")
            return False
        
        # Send PLAY command
        payload = f"{video_filename} {udp_port}".encode('utf-8')
        if not self.send_tcp_command(CMD_PLAY, payload):
            return False
        
        print(f"Sent PLAY command for {video_filename} on UDP port {udp_port}")
        
        # Setup UDP socket
        try:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.bind(('', udp_port))
            self.udp_sock.settimeout(1.0)  # 1 second timeout for graceful shutdown
            print(f"UDP socket bound to port {udp_port}")
        except Exception as e:
            print(f"Failed to bind UDP socket: {e}")
            return False
        
        # Reset state
        self.is_playing = True
        self.is_receiving = True
        self.stream_ended = False
        self.expected_frame_id = 0
        
        # Clear the queue
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
        
        # Start UDP receiver thread (producer)
        self.udp_thread = threading.Thread(target=self.udp_receiver, daemon=True)
        self.udp_thread.start()
        
        # Start player thread (consumer)
        self.player_thread = threading.Thread(target=self.video_player, daemon=True)
        self.player_thread.start()
        
        return True
    
    def stop_video(self):
        """Send STOP command and stop all threads."""
        if not self.is_playing:
            print("No video is currently playing.")
            return False
        
        # Send STOP command
        if not self.send_tcp_command(CMD_STOP):
            return False
        
        print("Sent STOP command")
        
        # Stop receiving
        self.is_receiving = False
        self.is_playing = False
        
        # Wait for threads to finish (with timeout)
        if self.udp_thread and self.udp_thread.is_alive():
            self.udp_thread.join(timeout=2.0)
        
        if self.player_thread and self.player_thread.is_alive():
            self.player_thread.join(timeout=2.0)
        
        # Close UDP socket
        if self.udp_sock:
            self.udp_sock.close()
            self.udp_sock = None
        
        return True
    
    def udp_receiver(self):
        """
        UDP Receiver Thread (Producer)
        Receives UDP packets, verifies checksums, and pushes valid frames to queue.
        """
        print("UDP receiver thread started")
        
        while self.is_receiving:
            try:
                # Receive packet
                data, addr = self.udp_sock.recvfrom(BUFFER_SIZE)
                
                if len(data) < 20:
                    print(f"Received packet too small: {len(data)} bytes")
                    continue
                
                # Parse header (20 bytes)
                # Format: struct.unpack('!IIIII', header)
                # Fields: conn_id, frame_id, pts_ms, payload_len, checksum
                header = data[:20]
                conn_id, frame_id, pts_ms, payload_len, checksum = struct.unpack('!IIIII', header)
                
                # Extract payload
                if len(data) < 20 + payload_len:
                    print(f"Packet incomplete: expected {20 + payload_len} bytes, got {len(data)}")
                    continue
                
                payload = data[20:20 + payload_len]
                
                # Check for end-of-stream signal
                if frame_id == END_OF_STREAM_FRAME_ID:
                    print("Received end-of-stream signal from server")
                    self.stream_ended = True
                    # Push a special marker to the queue so player thread can detect it
                    self.frame_queue.put((END_OF_STREAM_FRAME_ID, {
                        'frame_id': END_OF_STREAM_FRAME_ID,
                        'pts_ms': pts_ms,
                        'payload': payload,
                        'conn_id': conn_id,
                        'is_eos': True
                    }))
                    break  # Exit receiver loop
                
                # Verify checksum (CRC32)
                calculated_checksum = zlib.crc32(payload) & 0xffffffff
                if calculated_checksum != checksum:
                    print(f"Checksum mismatch for frame {frame_id}: expected {checksum}, got {calculated_checksum}")
                    continue
                
                # Push frame to priority queue (ordered by frame_id)
                # PriorityQueue uses tuple (priority, item), lower priority = higher precedence
                self.frame_queue.put((frame_id, {
                    'frame_id': frame_id,
                    'pts_ms': pts_ms,
                    'payload': payload,
                    'conn_id': conn_id,
                    'is_eos': False
                }))
                
            except socket.timeout:
                # Timeout is expected when checking is_receiving flag
                continue
            except Exception as e:
                if self.is_receiving:
                    print(f"Error in UDP receiver: {e}")
                break
        
        print("UDP receiver thread stopped")
    
    def video_player(self):
        """
        Video Player Thread (Consumer)
        Pops frames from queue and simulates playback timing using PTS.
        """
        print("Video player thread started")
        
        # Pre-buffering: wait until we have PREBUFFER_FRAMES frames
        print(f"Pre-buffering: waiting for {PREBUFFER_FRAMES} frames...")
        prebuffer_start = time.time()
        while self.frame_queue.qsize() < PREBUFFER_FRAMES and self.is_playing:
            time.sleep(0.1)
            if time.time() - prebuffer_start > 10.0:  # Timeout after 10 seconds
                print("Pre-buffering timeout")
                break
        
        if not self.is_playing:
            print("Playback cancelled during pre-buffering")
            return
        
        prebuffer_duration = (time.time() - prebuffer_start) * 1000
        print(f"Pre-buffering complete after {prebuffer_duration:.2f}ms. Starting playback...")
        
        # Start time for playback timing
        playback_start_time = time.time()
        last_pts_ms = None
        
        # Main playback loop
        while self.is_playing:
            try:
                # Try to get frame from queue (with timeout)
                try:
                    priority, frame_data = self.frame_queue.get(timeout=1.0)
                except queue.Empty:
                    # Queue is empty - check if stream has ended
                    if self.stream_ended:
                        print("Stream ended. All frames played.")
                        self.is_playing = False
                        # Display metrics when video ends naturally
                        self.print_metrics()
                        break
                    # Queue is empty but stream hasn't ended - this is a stall
                    if self.is_playing:
                        print("STALL: Queue empty, waiting for frames...")
                        self.metrics.record_stall(1000.0)  # Approximate 1 second stall
                    continue
                
                frame_id = frame_data['frame_id']
                pts_ms = frame_data['pts_ms']
                
                # Check for end-of-stream marker
                if frame_id == END_OF_STREAM_FRAME_ID or frame_data.get('is_eos', False):
                    print("End-of-stream marker received. Finishing playback...")
                    # Process any remaining frames in queue before exiting
                    # Wait a bit for any late-arriving frames
                    time.sleep(0.5)
                    # Process any remaining valid frames
                    while not self.frame_queue.empty():
                        try:
                            priority, remaining_frame = self.frame_queue.get_nowait()
                            if remaining_frame.get('frame_id', 0) != END_OF_STREAM_FRAME_ID:
                                # Process this frame normally
                                remaining_id = remaining_frame['frame_id']
                                remaining_pts = remaining_frame['pts_ms']
                                if remaining_id == self.expected_frame_id:
                                    target_time = playback_start_time + (remaining_pts / 1000.0)
                                    current_time = time.time()
                                    delay_ms = max(0, (current_time - target_time) * 1000.0)
                                    print(f"PLAYED frame {remaining_id} (PTS: {remaining_pts}ms, delay: {delay_ms:.2f}ms)")
                                    self.metrics.record_frame_played(delay_ms)
                                    self.expected_frame_id = remaining_id + 1
                                elif remaining_id > self.expected_frame_id:
                                    # Dropped frames
                                    dropped_count = remaining_id - self.expected_frame_id
                                    for i in range(dropped_count):
                                        print(f"DROPPED frame {self.expected_frame_id + i}")
                                        self.metrics.record_frame_dropped()
                                    self.expected_frame_id = remaining_id + 1
                        except queue.Empty:
                            break
                    # Stream ended naturally - mark as not playing so client can start new video
                    print("Video playback completed.")
                    self.is_playing = False
                    # Display metrics when video ends naturally
                    self.print_metrics()
                    break
                
                # Check for sequence gaps (dropped frames)
                if frame_id > self.expected_frame_id:
                    dropped_count = frame_id - self.expected_frame_id
                    for i in range(dropped_count):
                        print(f"DROPPED frame {self.expected_frame_id + i}")
                        self.metrics.record_frame_dropped()
                    self.expected_frame_id = frame_id + 1
                elif frame_id < self.expected_frame_id:
                    # Out-of-order or duplicate frame - skip it
                    print(f"Skipping out-of-order/duplicate frame {frame_id} (expected {self.expected_frame_id})")
                    continue
                else:
                    self.expected_frame_id = frame_id + 1
                
                # Calculate target playback time
                # Target_Time = Start_Time + pts_ms
                target_time = playback_start_time + (pts_ms / 1000.0)
                current_time = time.time()
                
                # Calculate delay (how late we are)
                delay_ms = (current_time - target_time) * 1000.0
                
                # Sleep if we're early
                if current_time < target_time:
                    sleep_duration = target_time - current_time
                    time.sleep(sleep_duration)
                    delay_ms = 0.0  # We were on time
                else:
                    # We're late - record the delay
                    if delay_ms > 0:
                        pass  # Delay already calculated
                
                # "Play" the frame (simulate)
                print(f"PLAYED frame {frame_id} (PTS: {pts_ms}ms, delay: {delay_ms:.2f}ms)")
                self.metrics.record_frame_played(delay_ms)
                
                last_pts_ms = pts_ms
                
            except Exception as e:
                if self.is_playing:
                    print(f"Error in video player: {e}")
                break
        
        print("Video player thread stopped")
    
    def close(self):
        """Close all connections and cleanup."""
        if self.is_playing:
            self.stop_video()
        
        if self.tcp_sock:
            self.tcp_sock.close()
            self.tcp_sock = None
    
    def print_metrics(self):
        """Print playback metrics summary."""
        summary = self.metrics.get_summary()
        print("\n" + "="*50)
        print("PLAYBACK METRICS SUMMARY")
        print("="*50)
        print(f"Total Frames Played: {summary['total_frames_played']}")
        print(f"Total Frames Dropped: {summary['total_frames_dropped']}")
        print(f"Total Stalls: {summary['total_stalls']}")
        print(f"Max Delay: {summary['max_delay_ms']:.2f} ms")
        print(f"Average Delay: {summary['avg_delay_ms']:.2f} ms")
        print(f"95th Percentile Delay: {summary['p95_delay_ms']:.2f} ms")
        print(f"Average Stall Duration: {summary['avg_stall_duration_ms']:.2f} ms")
        print("="*50 + "\n")


def main():
    """Main CLI loop for user interaction."""
    client = VideoClient()
    
    # Connect to server
    if not client.connect_tcp():
        return
    
    try:
        print("\nVideo Streaming Client")
        print("Commands: PLAY <video_filename> <udp_port> | STOP | QUIT")
        print("-" * 50)
        
        while True:
            try:
                user_input = input("\n> ").strip().split()
                
                if not user_input:
                    continue
                
                command = user_input[0].upper()
                
                if command == "PLAY":
                    if len(user_input) != 3:
                        print("Usage: PLAY <video_filename> <udp_port>")
                        continue
                    
                    video_filename = user_input[1]
                    try:
                        udp_port = int(user_input[2])
                    except ValueError:
                        print("Error: UDP port must be a number")
                        continue
                    
                    client.play_video(video_filename, udp_port)
                
                elif command == "STOP":
                    client.stop_video()
                    client.print_metrics()
                
                elif command == "QUIT" or command == "EXIT":
                    client.stop_video()
                    client.print_metrics()
                    break
                
                else:
                    print(f"Unknown command: {command}")
                    print("Commands: PLAY <video_filename> <udp_port> | STOP | QUIT")
            
            except KeyboardInterrupt:
                print("\nInterrupted by user")
                client.stop_video()
                client.print_metrics()
                break
            except EOFError:
                print("\nEOF reached")
                client.stop_video()
                client.print_metrics()
                break
    
    finally:
        client.close()
        print("Client closed.")


if __name__ == "__main__":
    main()

