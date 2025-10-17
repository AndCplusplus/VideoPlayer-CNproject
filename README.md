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

- Command_Type, a 1-byte integer to identify the message type (1 = Play, 2 = Pause, etc.)
- Sequence_Number, a 4-byte number to uniquely identify the particular command
- Payload_Length, the length of the data following the header

Our timer will wait for an ACK from the receiver and time out if it is not received.

For our UDP header, we will have the following fields:

- conn_id, this defines the unique ID of the connected client
- frame_id, this will define the sequence number for the video frame, and helps with detecting packet loss
- pts_ms, the Presentation Timestamp will tell the client what frame should be playing, helping detection of late packets and playback timing
- len, the length of the video data in this packet
- checksum, used to detect data corruption

We will use code on our server, such as time.sleep(), to send packets at a steady rate.

# 4 Application Layer Design Plan

    Message format and command grammar (e.g., LIST, GET <file>, MSG <room> <text>, PLAY <video>).
    How your client and server will interact.
    How concurrency will be supported (at least 2 clients).

# 5 Testing and Metrics Plan

    How you plan to test your system under the three lossy network profiles (Clean, Random Loss, Bursty Loss).
    Which metrics you intend to measure (e.g., throughput, latency, retransmissions, dropped frames, stall time).

# 6 Progress Summary (Midterm Status)

    What has been implemented so far (with brief descriptions of working components).
    What remains to be completed for the final milestone.
    Evidence of progress such as code structure, working prototypes, or initial testing.
