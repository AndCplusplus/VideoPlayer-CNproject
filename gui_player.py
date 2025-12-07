"""
Optional Tiny GUI for video player
Displays playback progress, current frame info, and ASCII visualization
"""

import tkinter as tk
from tkinter import ttk
import threading
import hashlib

class VideoPlayerGUI:
    """Minimal GUI for video playback visualization."""
    
    def __init__(self):
        self.root = None
        self.progress_var = None
        self.frame_label = None
        self.status_label = None
        self.canvas = None
        self.ascii_label = None
        self.gui_thread = None
        self.is_running = False
        self.lock = threading.Lock()
        
        # Playback state
        self.current_frame = 0
        self.total_frames = 0
        self.is_playing = False
        self.status_text = "Ready"
        
    def start(self):
        """Start the GUI in a separate thread."""
        if self.is_running:
            return
            
        self.is_running = True
        self.gui_thread = threading.Thread(target=self._create_gui, daemon=True)
        self.gui_thread.start()
        
    def _create_gui(self):
        """Create and run the GUI (runs in GUI thread)."""
        self.root = tk.Tk()
        self.root.title("Video Player - Playback Monitor")
        self.root.geometry("400x300")
        self.root.resizable(False, False)
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Status: Ready", font=("Arial", 10, "bold"))
        self.status_label.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)
        
        # Frame info
        self.frame_label = ttk.Label(main_frame, text="Frame: 0 / 0", font=("Arial", 9))
        self.frame_label.grid(row=1, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)
        
        # Progress bar
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=2, column=0, columnspan=2, pady=(0, 10), sticky=(tk.W, tk.E))
        
        ttk.Label(progress_frame, text="Progress:", font=("Arial", 8)).grid(row=0, column=0, sticky=tk.W)
        self.progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                       maximum=100, length=350, mode='determinate')
        progress_bar.grid(row=1, column=0, pady=(5, 0), sticky=(tk.W, tk.E))
        
        progress_frame.columnconfigure(0, weight=1)
        
        # ASCII visualization frame
        viz_frame = ttk.LabelFrame(main_frame, text="Frame Visualization", padding="5")
        viz_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.ascii_label = tk.Text(viz_frame, width=40, height=8, font=("Courier", 6), 
                                   wrap=tk.WORD, state=tk.DISABLED, bg="#1e1e1e", fg="#00ff00")
        self.ascii_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        viz_frame.columnconfigure(0, weight=1)
        viz_frame.rowconfigure(0, weight=1)
        
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Start update loop
        self._update_display()
        
        # Run GUI main loop
        self.root.mainloop()
        
    def _on_closing(self):
        """Handle window close event."""
        self.is_running = False
        if self.root:
            self.root.quit()
            self.root.destroy()
            
    def _update_display(self):
        """Periodically update the GUI display."""
        if not self.is_running or not self.root:
            return
            
        try:
            with self.lock:
                status = self.status_text
                frame_num = self.current_frame
                total = self.total_frames
                playing = self.is_playing
                
            # Update status
            status_display = f"Status: {status}"
            if playing:
                status_display += " [▶ PLAYING]"
            else:
                status_display += " [⏸ PAUSED]"
                
            self.status_label.config(text=status_display)
            
            # Update frame count - only show total if we know it (total > 0 and reasonable)
            if total > 0 and total >= frame_num:
                self.frame_label.config(text=f"Frame: {frame_num} / {total}")
            else:
                self.frame_label.config(text=f"Frame: {frame_num}")
            
            # Update progress bar
            if total > 0 and total >= frame_num:
                # Calculate progress as percentage, ensuring we don't exceed 100%
                progress = min(100.0, (frame_num / total) * 100.0)
                self.progress_var.set(progress)
            elif total > 0:
                # If frame_num exceeds total (shouldn't happen, but handle gracefully)
                self.progress_var.set(100.0)
            else:
                # No total known yet, keep at 0
                self.progress_var.set(0)
                
            # Schedule next update
            if self.root:
                self.root.after(100, self._update_display)
                
        except tk.TclError:
            # Window was closed
            self.is_running = False
            
    def update_frame(self, frame_id, frame_data, total_frames=0):
        """Update GUI with new frame information."""
        if not self.is_running:
            return
            
        with self.lock:
            self.current_frame = frame_id
            if total_frames > 0:
                self.total_frames = total_frames
            self.is_playing = True
            self.status_text = "Playing"
            
            # Generate ASCII art from frame data
            ascii_art = self._generate_ascii_art(frame_data)
            
        # Update ASCII display (needs to be in GUI thread)
        if self.root:
            self.root.after(0, self._update_ascii, ascii_art)
            
    def _update_ascii(self, ascii_art):
        """Update ASCII art display (called from GUI thread)."""
        if not self.ascii_label:
            return
        try:
            self.ascii_label.config(state=tk.NORMAL)
            self.ascii_label.delete("1.0", tk.END)
            self.ascii_label.insert("1.0", ascii_art)
            self.ascii_label.config(state=tk.DISABLED)
        except tk.TclError:
            pass
            
    def _generate_ascii_art(self, frame_data):
        """Generate ASCII art visualization from frame data."""
        if not frame_data:
            return "No frame data"
            
        # Create a simple visualization based on data hash and characteristics
        data_hash = hashlib.md5(frame_data[:min(1024, len(frame_data))]).hexdigest()
        data_size = len(frame_data)
        
        # Use hash to generate a pattern
        chars = " .:-=+*#%@"
        lines = []
        
        # Create a 10x10 grid pattern based on hash
        for i in range(10):
            line = ""
            for j in range(20):
                idx = (i * 20 + j) % len(data_hash)
                char_val = int(data_hash[idx], 16)
                char_idx = (char_val + data_size) % len(chars)
                line += chars[char_idx]
            lines.append(line)
            
        # Add metadata
        metadata = f"Size: {data_size} bytes\nHash: {data_hash[:16]}..."
        result = "\n".join(lines) + "\n\n" + metadata
        
        return result
        
    def set_total_frames(self, total_frames):
        """Set the total number of frames. Can be called before GUI is fully initialized."""
        with self.lock:
            if total_frames > 0:
                self.total_frames = total_frames
    
    def set_status(self, status, playing=False):
        """Update playback status."""
        if not self.is_running:
            return
        with self.lock:
            self.status_text = status
            self.is_playing = playing
            
    def set_stopped(self):
        """Set status to stopped."""
        if not self.is_running:
            return
        with self.lock:
            self.is_playing = False
            self.status_text = "Stopped"
            
    def stop(self):
        """Stop the GUI."""
        self.is_running = False
        if self.root:
            self.root.after(0, self.root.quit)

