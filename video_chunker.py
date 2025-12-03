import os
import shutil
from config import CHUNK_SIZE, CHUNKS_DIR, VIDEO_PATH

def chunk_video():
  """
    Reads the source video file in binary mode and writes fixed-size
    chunks to the output directory.
  """
  if not os.path.exists(VIDEO_PATH):
    raise FileNotFoundError(f"Video file not found at {VIDEO_PATH}")

  if os.path.exists(CHUNKS_DIR):
    # clean directory
    shutil.rmtree(CHUNKS_DIR)

  os.makedirs(CHUNKS_DIR, exist_ok=True)
  print(f"created output directory: {CHUNKS_DIR}")
  
  print(f"chunking video file: {VIDEO_PATH} into {CHUNKS_DIR}...")

  chunk_count = 0 

  try:
    with open(VIDEO_PATH, 'rb') as video_file:
      while True:
        data = video_file.read(CHUNK_SIZE)

        if not data:
          break

        chunk_name = f'chunk_{chunk_count:05d}.bin'
        chunk_path = os.path.join(CHUNKS_DIR, chunk_name)
        with open(chunk_path, 'wb') as chunk_file:
          chunk_file.write(data)

        chunk_count += 1

        if chunk_count % 100 == 0:
          print(f"wrote {chunk_count} chunks to {CHUNKS_DIR}")
  except Exception as e:
    print(f"Error chunking video file: {e}")
    raise e

if __name__ == '__main__':
  chunk_video()