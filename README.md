# VideoPlayer-CNproject

For Computer Networks; Video player (chunked media delivery)

# 1 Team Information

- Julian Spindola, Andrew Cadena, Oscar Lesage, Ben Johnson-Gomez, Christian Torres
- Video Streaming (Chunked Media Delivery)

# 2 Project Overview

- We plan to make a simple, headless, no GUI video streaming application, metrics will be collected from logs rather than displayed video.

# 3 Transport Protocol Design Plan

Given the need for low latency and minimal delay in video streaming, we plan to implement a hybrid protocol. UDP will be used for transmitting video data chunks to ensure fast delivery, while TCP will handle control signals such as play and pause to guarantee reliability for these commands. To ensure reliability with UDP, we will use a checksum method to verify data integrity, along with loss detection, to log dropped frames. Due to the importance of speed, we won’t attempt to retrieve dropped frames. For our TCP portion, we will implement basic TCP-like reliability controls such as ACKs and sequence numbers. These measures should hopefully handle most packet loss and duplication.

For our TCP header, we will define a message format that contains the following fields:

- `Command_Type`, a 1-byte integer to identify the message type (`1` = Play, `2` = Pause, etc.)
- `Sequence_Number`, a 4-byte number to uniquely identify the particular command
- `Payload_Length`, the length of the data following the header

Our timer will wait for an ACK from the receiver and time out if it is not received.

For our UDP header, we will have the following fields:

- `conn_id`, this defines the unique ID of the connected client
- `frame_id`, this will define the sequence number for the video frame, and helps with detecting packet loss
- `pts_ms`, the Presentation Timestamp will tell the client what frame should be playing, helping detection of late packets and playback timing
- `len`, the length of the video data in this packet
- `checksum`, used to detect data corruption

We will use code on our server, such as `time.sleep()`, to send packets at a steady rate.

## 4 Application Layer Design Plan

Our client will interact with our server through the use of command-line arguments. The two primary commands are the following:

1. PLAY `<video>` `<port>`

- This would play a specified video file on the server on the specified port number for receiving UDP data.

2. STOP

- This would inform the server to terminate the video stream for the current client connection.

Concurrency is supported by ensuring that each TCP connection is managed by its own dedicated thread in the program. We will assign each connection its own ID that the UDP socket will manage to determine which client to send data to.

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

1. Start the implementation of `server.py` to accept TPC connections from multiple clients.
2. Begin implementation of `client.py` to start the transfer of data.
3. Enhance the client by implementing buffering and playback.
4. Develop loss and lateness logic, along with metrics.
5. Test application with our loss simulation
