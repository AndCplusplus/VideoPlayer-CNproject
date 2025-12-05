import os
from config import CHUNK_SIZE, FRAME_INTERVAL_MS

class VideoChunker:
  def __init__(self, video_path):
    if not os.path.exists(video_path):
      raise FileNotFoundError(f"Video file not found: {video_path}")

    self.file = open(video_path, 'rb')
    self.frame_id = 0
    self.total_bytes_read = 0
    self.file_size = os.path.getsize(video_path)

  def next_frame(self):
    # Reads a chunk of data of CHUNK_SIZE
    data = self.file.read(CHUNK_SIZE)

    if not data:
      # If no data is read, we've reached the end of the file
      return None, 0, True

    # Calculate the PTS (Presentation Timestamp) in milliseconds
    # Assumes each chunk represents a single frame interval (simplification)
    pts_ms = self.frame_id * FRAME_INTERVAL_MS

    self.frame_id += 1
    self.total_bytes_read += len(data)

    # Check if the file pointer is at or past the end of the file
    is_last = self.file.tell() >= self.file_size

    return data, pts_ms, is_last

  def close(self):
    self.file.close()