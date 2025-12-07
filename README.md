# VideoPlayer-CNproject

For Computer Networks; Video player (chunked media delivery)

## 1 Team Information

- Julian Spindola, Andrew Cadena, Oscar Lesage, Ben Johnson-Gomez, Christian Torres
- Video Streaming (Chunked Media Delivery)

## 2 Project Overview

- We plan to make a simple, headless, no GUI video streaming application, metrics will be collected from logs rather than displayed video.

## 3 Transport Protocol Design Plan

Given the need for low latency and minimal delay in video streaming, we implement a UDP-based protocol with reliability mechanisms. **UDP is used for both control signals and video data transmission**. To ensure reliability for critical control commands (PLAY and STOP), we implement a **Stop-and-Wait** mechanism on top of UDP, which provides TCP-like reliability guarantees for these commands. Video data is transmitted as unreliable UDP packets to prioritize speed and low latency.

### Reliable Control Protocol (Stop-and-Wait)

Control commands (PLAY and STOP) are sent over UDP with a custom reliability layer that implements Stop-and-Wait:

- **Control Packet Format** (9-byte header + payload):

  - `Command_Type` (1 byte): Identifies the message type (`1` = Play, `2` = Stop)
  - `Sequence_Number` (4 bytes): Uniquely identifies the particular command
  - `Payload_Length` (4 bytes): Length of the data following the header
  - `Payload` (variable): Command-specific data (e.g., "video_filename udp_port" for PLAY)

- **Reliability Mechanism**:
  - The sender waits for an ACK after sending each command
  - ACK format: `ACK_Type` (1 byte, value `10`), `Acked_Sequence_Number` (4 bytes), optional metadata (4 bytes for total_chunks in PLAY ACKs)
  - Timeout-based retransmission: If no ACK is received within 0.5 seconds, the command is retransmitted
  - Maximum of 5 retry attempts before giving up
  - This ensures that control commands are reliably delivered, similar to TCP's reliability guarantees

### Unreliable Video Data Protocol

Video frames are transmitted as unreliable UDP packets to maximize throughput and minimize latency:

- **Frame Data Packet Format** (20-byte header + compressed data):

  - `conn_id` (4 bytes, unsigned int): Unique connection identifier for the client session
  - `frame_id` (4 bytes, unsigned int): Sequence number for the video frame, helps detect packet loss and reordering
  - `pts_ms` (4 bytes, float): Presentation Timestamp in milliseconds, indicates when the frame should be played
  - `len` (4 bytes, unsigned int): Length of the compressed data payload in bytes
  - `checksum` (4 bytes, unsigned int): Adler-32 checksum of the compressed data for integrity verification
  - `Compressed_Data` (variable): Zlib-compressed video chunk data

- **End-of-Stream Marker**:

  - Special packet with 20-byte header where `frame_id = 0xFFFFFFFF`, `pts_ms = 0.0`, `len = 0`, and `checksum = 0`
  - Signals the end of the video stream to the client

- **Loss Handling**:
  - Lost or corrupted frames are detected by checking for gaps in `frame_id` sequence
  - Checksum verification ensures data integrity - corrupted packets are dropped
  - Connection ID verification ensures packets belong to the current session
  - Due to the importance of speed and real-time playback, dropped frames are not retransmitted
  - Frame loss is logged for metrics collection

The server uses `time.sleep()` to maintain a steady frame rate (24 FPS) when sending packets.

## 4 Application Layer Design Plan

Our client will interact with our server through the use of command-line arguments. The two primary commands are the following:

1. PLAY `<video>` `<port>`

- This would play a specified video file on the server on the specified port number for receiving UDP data.

2. STOP

- This would inform the server to terminate the video stream for the current client connection.

Concurrency is supported by managing each client connection with its own dedicated streaming thread. The server uses a single UDP socket for both control and data transmission, with each client identified by their IP address and specified UDP port. When a client sends a PLAY command, the server creates a new streaming thread that sends video data to the client's specified UDP port.

## 5 Testing and Metrics Plan

To test our system, we will put it under a load of three lossy network profiles. We can do this by simulating random loss inside our program when sending packets.

For metrics and logging, we will store the following data:

- Startup delay
- Stall durations
- Total count of frames played vs. dropped
- Total bytes of payload played
- Total playback duration
- All frame delays
- 95th-percentile frame delay

These will be printed to the user when they enter STOP into the console.

## 6 Progress Summary (Midterm Status)

So far, only our tasks, objectives, and program file structure have been put in place to guide our development throughout the remainder of the semester. We plan to start the implementation of core features in steps:

1. Start the implementation of `server.py` to accept UDP control commands from multiple clients.
2. Begin implementation of `client.py` to start the transfer of data.
3. Enhance the client by implementing buffering and playback.
4. Develop loss and lateness logic, along with metrics.
5. Test application with our loss simulation

## 7 How to Run

### Prerequisites

- Python 3.x installed
- The example video file `test.mp4` should be located in the `video_source/` directory

### Running the Project

#### Step 1: Start the Server

Open a terminal/command prompt and navigate to the project directory. Start the server:

```bash
python server.py
```

You should see output indicating the server is listening:

```
[SERVER] UDP Control/Data socket bound to 127.0.0.1:50000
[SERVER] Listener thread started. Awaiting commands...
```

**Keep this terminal window open** - the server must remain running.

#### Step 2: Start the Client

Open a **new** terminal/command prompt window and navigate to the project directory. Start the client:

```bash
python client.py
```

You should see:

```
UDP socket bound to port 9000

--- Video Client CLI ---
Available Commands: PLAY <file> <port>, STOP, QUIT
```

#### Step 3: Play the Example Video

In the client terminal, enter the PLAY command with the example video:

```
> PLAY test.mp4 9000
```

This command:

- Requests the server to stream `test.mp4` from the `video_source/` directory
- Sets up UDP reception on port `9000` (you can use any available port number)

You should see output like:

```
Sent PLAY command for test.mp4 on UDP port 9000
UDP socket bound to port 9000
UDP receiver thread started
Video player thread started
Pre-buffering: waiting for 10 frames...
Pre-buffering complete after XXX.XXms. Starting playback...
PLAYED frame 0 (PTS: 0ms, delay: 0.00ms)
PLAYED frame 1 (PTS: 41ms, delay: 0.00ms)
...
```

#### Step 4: Stop Playback

To stop the video and view metrics, enter:

```
> STOP
```

The client will:

- Send a STOP command to the server
- Display playback metrics including:
  - Total frames played
  - Total frames dropped
  - Total stalls
  - Max delay, average delay, and 95th percentile delay
  - Average stall duration

#### Step 5: Exit

To exit the client, enter:

```
> QUIT
```

Or press `Ctrl+C` in either terminal to stop the server or client.

### Example Session

```
> PLAY test.mp4 9000
Sent PLAY command for test.mp4 on UDP port 9000
UDP socket bound to port 9000
UDP receiver thread started
Video player thread started
Pre-buffering: waiting for 10 frames...
Pre-buffering complete after 450.23ms. Starting playback...
PLAYED frame 0 (PTS: 0ms, delay: 0.00ms)
PLAYED frame 1 (PTS: 41ms, delay: 0.00ms)
...
Video playback completed.

==================================================
PLAYBACK METRICS SUMMARY
==================================================
Total Frames Played: 37
Total Frames Dropped: 0
Total Stalls: 0
Max Delay: 0.00 ms
Average Delay: 0.00 ms
95th Percentile Delay: 0.00 ms
Average Stall Duration: 0.00 ms
==================================================

> QUIT
Client closed.
```

### Notes

- The video will automatically end when the stream completes, and metrics will be displayed automatically
- You can play multiple videos in sequence by issuing multiple PLAY commands (after stopping the previous one)
- Make sure the UDP port you specify (e.g., 9000) is not already in use by another application
- The server supports multiple concurrent clients, each with their own UDP port for receiving video data
- Control commands use a reliable UDP protocol with Stop-and-Wait to ensure delivery
