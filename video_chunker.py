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
    data = self.file.read(CHUNK_SIZE)

    if not data:
      return None, 0, True

    # Calculate the PTS (Presentation Timestamp) in milliseconds
    pts_ms = self.frame_id * FRAME_INTERVAL_MS

    self.frame_id += 1
    self.total_bytes_read += len(data)

    is_last = self.total_bytes_read >= self.file_size

    return data, pts_ms, is_last

  def close(self):
    self.file.close()