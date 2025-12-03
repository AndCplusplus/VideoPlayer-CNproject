import os
import hashlib
from config import VIDEO_PATH, CHUNKS_DIR

RECONSTRUCTED_FILENAME = 'reconstructed_video.mp4'

def get_file_checksum(filepath):
    """Calculates MD5 hash of a file to verify integrity."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        # Read in chunks to avoid memory issues with large files
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def verify_chunks():
    print("--- Starting Verification ---")
    
    # 1. Gather all chunk files
    try:
        chunk_files = [f for f in os.listdir(CHUNKS_DIR) if f.endswith('.bin')]
    except FileNotFoundError:
        print("Error: video_chunks directory not found. Run video_chunker.py first.")
        return

    # CRITICAL: Sort them! OS file listing order is not guaranteed.
    # We rely on the filenames being frame_00000, frame_00001, etc.
    chunk_files.sort()
    
    if not chunk_files:
        print("No chunks found!")
        return

    print(f"Found {len(chunk_files)} chunks. Reassembling...")

    # 2. Stitch them back together
    with open(RECONSTRUCTED_FILENAME, 'wb') as outfile:
        for chunk_name in chunk_files:
            chunk_path = os.path.join(CHUNKS_DIR, chunk_name)
            with open(chunk_path, 'rb') as infile:
                outfile.write(infile.read())

    print(f"Reconstructed file created: {RECONSTRUCTED_FILENAME}")

    # 3. Compare with Original
    print("\n--- Integrity Check ---")
    
    if not os.path.exists(VIDEO_PATH):
        print(f"Warning: Original file {VIDEO_PATH} not found. Cannot verify hash.")
        print(f"Please manually check if {RECONSTRUCTED_FILENAME} plays correctly.")
        return

    original_hash = get_file_checksum(VIDEO_PATH)
    new_hash = get_file_checksum(RECONSTRUCTED_FILENAME)

    print(f"Original MD5:      {original_hash}")
    print(f"Reconstructed MD5: {new_hash}")

    if original_hash == new_hash:
        print("\nSUCCESS: The reconstructed video matches the original exactly. ✅")
        # Cleanup (optional)
        os.remove(RECONSTRUCTED_FILENAME)
        print("Test file removed.")
    else:
        print("\nFAILURE: Hashes do not match. The chunking process corrupted data. ❌")

if __name__ == "__main__":
    verify_chunks()