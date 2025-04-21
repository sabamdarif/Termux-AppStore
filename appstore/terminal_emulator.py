#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango
import re
import subprocess
import threading
import os
import pty
import fcntl
import select
import signal
import time
import termios
import struct
import sys

class AnsiColorParser:
    """Class to parse ANSI escape sequences and apply formatting to a GTK TextView"""
    
    # ANSI escape sequence regex
    ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[((?:\d+;)*\d+)?([A-Za-z])')
    
    # Basic ANSI color codes
    COLORS = {
        # Foreground colors
        '30': (0.0, 0.0, 0.0),      # Black
        '31': (0.8, 0.0, 0.0),      # Red
        '32': (0.0, 0.8, 0.0),      # Green
        '33': (0.8, 0.8, 0.0),      # Yellow
        '34': (0.0, 0.0, 0.8),      # Blue
        '35': (0.8, 0.0, 0.8),      # Magenta
        '36': (0.0, 0.8, 0.8),      # Cyan
        '37': (0.8, 0.8, 0.8),      # White
        '90': (0.5, 0.5, 0.5),      # Bright Black (Gray)
        '91': (1.0, 0.0, 0.0),      # Bright Red
        '92': (0.0, 1.0, 0.0),      # Bright Green
        '93': (1.0, 1.0, 0.0),      # Bright Yellow
        '94': (0.0, 0.0, 1.0),      # Bright Blue
        '95': (1.0, 0.0, 1.0),      # Bright Magenta
        '96': (0.0, 1.0, 1.0),      # Bright Cyan
        '97': (1.0, 1.0, 1.0),      # Bright White
        # Background colors
        '40': (0.0, 0.0, 0.0),      # Black
        '41': (0.8, 0.0, 0.0),      # Red
        '42': (0.0, 0.8, 0.0),      # Green
        '43': (0.8, 0.8, 0.0),      # Yellow
        '44': (0.0, 0.0, 0.8),      # Blue
        '45': (0.8, 0.0, 0.8),      # Magenta
        '46': (0.0, 0.8, 0.8),      # Cyan
        '47': (0.8, 0.8, 0.8),      # White
        '100': (0.5, 0.5, 0.5),     # Bright Black (Gray)
        '101': (1.0, 0.0, 0.0),     # Bright Red
        '102': (0.0, 1.0, 0.0),     # Bright Green
        '103': (1.0, 1.0, 0.0),     # Bright Yellow
        '104': (0.0, 0.0, 1.0),     # Bright Blue
        '105': (1.0, 0.0, 1.0),     # Bright Magenta
        '106': (0.0, 1.0, 1.0),     # Bright Cyan
        '107': (1.0, 1.0, 1.0),     # Bright White
    }
    
    # Text attributes
    ATTRIBUTES = {
        '0': {'name': 'reset', 'tags': []},
        '1': {'name': 'bold', 'tags': ['bold']},
        '2': {'name': 'dim', 'tags': ['dim']},
        '3': {'name': 'italic', 'tags': ['italic']},
        '4': {'name': 'underline', 'tags': ['underline']},
        '5': {'name': 'blink', 'tags': ['blink']},
        '7': {'name': 'reverse', 'tags': ['reverse']},
        '9': {'name': 'strikethrough', 'tags': ['strikethrough']},
    }
    
    def __init__(self):
        # Initialize tag table for the TextView buffer
        self.active_tags = []
    
    def ensure_tag(self, buffer, tag_name, properties):
        """Ensure a tag exists in the buffer with given properties"""
        tag = buffer.get_tag_table().lookup(tag_name)
        if not tag:
            tag = buffer.create_tag(tag_name, **properties)
        return tag
    
    def apply_formatting(self, buffer, text):
        """Apply ANSI formatting to text and insert into buffer"""
        if not text:
            return

        # Starting position for insertion
        end_iter = buffer.get_end_iter()
        
        # Process text character by character, applying tags when needed
        i = 0
        last_text_pos = 0
        
        while i < len(text):
            match = self.ANSI_ESCAPE_PATTERN.search(text, i)
            
            if not match:
                # No more escape sequences, insert the rest of the text
                plain_text = text[last_text_pos:]
                if plain_text:
                    self._insert_with_active_tags(buffer, plain_text)
                break
            
            # Insert any text before the escape sequence
            if match.start() > last_text_pos:
                plain_text = text[last_text_pos:match.start()]
                self._insert_with_active_tags(buffer, plain_text)
            
            # Process the ANSI code
            codes = match.group(1)
            command = match.group(2)
            
            if command == 'm':  # SGR (Select Graphic Rendition)
                if codes:
                    self._process_sgr_codes(buffer, codes)
                else:
                    # Reset all attributes if no codes provided
                    self.active_tags = []
            
            # Move past the escape sequence
            i = match.end()
            last_text_pos = i
            
    def _insert_with_active_tags(self, buffer, text):
        """Insert text into buffer with active tags applied"""
        if not text:
            return
            
        end_iter = buffer.get_end_iter()
        mark = buffer.create_mark(None, end_iter, True)
        
        buffer.insert(end_iter, text)
        
        # Get the start and end positions of the newly inserted text
        new_end_iter = buffer.get_end_iter()
        start_iter = buffer.get_iter_at_mark(mark)
        
        # Apply all active tags to the inserted text
        for tag_name in self.active_tags:
            tag = buffer.get_tag_table().lookup(tag_name)
            if tag:
                buffer.apply_tag(tag, start_iter, new_end_iter)
        
        buffer.delete_mark(mark)
    
    def _process_sgr_codes(self, buffer, codes_str):
        """Process SGR (Select Graphic Rendition) codes"""
        codes = codes_str.split(';')
        
        for code in codes:
            if not code:
                continue
                
            # Handle reset
            if code == '0':
                self.active_tags = []
                continue
                
            # Text attribute
            if code in self.ATTRIBUTES and code != '0':
                for tag_type in self.ATTRIBUTES[code]['tags']:
                    tag_name = f"ansi_{tag_type}"
                    
                    if tag_type == 'bold':
                        self.ensure_tag(buffer, tag_name, {'weight': Pango.Weight.BOLD})
                    elif tag_type == 'dim':
                        self.ensure_tag(buffer, tag_name, {'weight': Pango.Weight.LIGHT})
                    elif tag_type == 'italic':
                        self.ensure_tag(buffer, tag_name, {'style': Pango.Style.ITALIC})
                    elif tag_type == 'underline':
                        self.ensure_tag(buffer, tag_name, {'underline': Pango.Underline.SINGLE})
                    elif tag_type == 'blink':
                        # Blinking is not directly supported, use background instead
                        self.ensure_tag(buffer, tag_name, {'background': 'lightgray'})
                    elif tag_type == 'reverse':
                        # Swap foreground and background colors
                        self.ensure_tag(buffer, tag_name, {'background': 'white', 'foreground': 'black'})
                    elif tag_type == 'strikethrough':
                        self.ensure_tag(buffer, tag_name, {'strikethrough': True})
                    
                    if tag_name not in self.active_tags:
                        self.active_tags.append(tag_name)
                        
            # Foreground color
            elif code.startswith('3') or code.startswith('9'):
                if code in self.COLORS:
                    r, g, b = self.COLORS[code]
                    tag_name = f"ansi_fg_{code}"
                    self.ensure_tag(buffer, tag_name, {'foreground-rgba': Gdk.RGBA(r, g, b, 1.0)})
                    
                    # Replace any existing foreground color
                    self.active_tags = [tag for tag in self.active_tags if not tag.startswith('ansi_fg_')]
                    self.active_tags.append(tag_name)
                    
            # Background color
            elif code.startswith('4') or code.startswith('10'):
                if code in self.COLORS:
                    r, g, b = self.COLORS[code]
                    tag_name = f"ansi_bg_{code}"
                    self.ensure_tag(buffer, tag_name, {'background-rgba': Gdk.RGBA(r, g, b, 1.0)})
                    
                    # Replace any existing background color
                    self.active_tags = [tag for tag in self.active_tags if not tag.startswith('ansi_bg_')]
                    self.active_tags.append(tag_name)
    
    def strip_ansi(self, text):
        """Remove ANSI escape sequences from text"""
        return self.ANSI_ESCAPE_PATTERN.sub('', text)


class TerminalEmulator:
    """Emulates a terminal in a GTK TextView"""
    
    def __init__(self, text_view):
        self.text_view = text_view
        self.buffer = text_view.get_buffer()
        self.ansi_parser = AnsiColorParser()
        self.last_line_was_animation = False
        self.line_buffer = ""  # Buffer to accumulate partial lines
        
        # Ensure monospace font for terminal-like appearance
        self.text_view.set_monospace(True)
        
        # Set initial terminal colors (will be overridden by CSS)
        self.text_view.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 1))
        self.text_view.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(1, 1, 1, 1))
        
        # Add terminal view style class
        self.text_view.get_style_context().add_class("terminal-view")
    
    def append_text(self, text, with_ansi=True):
        """Append text to the terminal view"""
        if not text:
            return
            
        # Handle special control codes
        # Convert CR+LF to just LF
        text = text.replace('\r\n', '\n')
        
        # Filter out common warning messages if they appear as complete lines
        if '\n' in text:
            filtered_lines = []
            for line in text.splitlines(True):  # Keep line endings
                if not any(warning in line for warning in [
                    "proot warning: can't sanitize binding",
                    "WARNING: apt does not have a stable CLI interface"
                ]):
                    filtered_lines.append(line)
            
            # If all lines were filtered out, just return
            if not filtered_lines:
                return
                
            # Use the filtered text instead
            text = ''.join(filtered_lines)
        elif any(warning in text for warning in [
            "proot warning: can't sanitize binding",
            "WARNING: apt does not have a stable CLI interface"
        ]):
            # Skip the text entirely if it's just a warning
            return
        
        # Special handling for carriage returns
        if '\r' in text:
            # Process animations
            self._handle_carriage_returns(text, with_ansi)
        else:
            # Standard text processing
            self._handle_normal_text(text, with_ansi)
    
    def _handle_carriage_returns(self, text, with_ansi):
        """Handle text with carriage returns (animations)"""
        self.last_line_was_animation = True
        lines = text.split('\r')
        
        # Process all but the last part normally (if there are multiple carriage returns)
        for i in range(len(lines) - 1):
            # Skip empty segments
            if not lines[i]:
                continue
            
            # Process each segment
            if i == 0 and self.line_buffer:
                # First segment: append to line buffer
                self.line_buffer += lines[i]
                self._append_segment(self.line_buffer, with_ansi)
                self.line_buffer = ""
            elif i == 0:
                # First segment with empty buffer: append normally
                self._append_segment(lines[i], with_ansi)
            else:
                # Other segments: replace the last line
                self._replace_last_line(lines[i], with_ansi)
        
        # Handle the last part specifically (after the last \r)
        if lines[-1]:
            self._replace_last_line(lines[-1], with_ansi)
    
    def _handle_normal_text(self, text, with_ansi):
        """Handle text without carriage returns"""
        # Check if this is a continuation of a partial line
        if self.line_buffer:
            # Complete the line
            text = self.line_buffer + text
            self.line_buffer = ""
        
        # Check if we need a newline after an animation
        if self.last_line_was_animation and not text.startswith('\n'):
            if '\n' in text:
                # If text contains newlines, animation is done
                self.last_line_was_animation = False
            
            # Ensure there's a line break between animation and new content
            # but only if we're starting a new logical line
            if not text.strip().startswith('\n'):
                end_iter = self.buffer.get_end_iter()
                self.buffer.insert(end_iter, '\n')
        
        # Process each line separately for better control
        lines = text.split('\n')
        
        # Handle all complete lines
        for i in range(len(lines) - 1):
            line = lines[i]
            self._append_segment(line + '\n', with_ansi)
            self.last_line_was_animation = False
        
        # Handle the last line (might be incomplete)
        if lines[-1]:
            # If the original text ended with a newline, add it
            if text.endswith('\n'):
                self._append_segment(lines[-1] + '\n', with_ansi)
                self.last_line_was_animation = False
            else:
                # This is a partial line, save it for later
                self.line_buffer = lines[-1]
                # Still display the partial line
                self._append_segment(lines[-1], with_ansi)
    
    def _append_segment(self, text, with_ansi=True):
        """Append a segment of text to the terminal"""
        # Skip empty text
        if not text:
            return
            
        # Filter out common warning messages line by line
        if '\n' in text:
            # For multiline text, filter line by line
            filtered_lines = []
            for line in text.splitlines(True):  # Keep line endings
                if not any(warning in line for warning in [
                    "proot warning: can't sanitize binding",
                    "WARNING: apt does not have a stable CLI interface"
                ]):
                    filtered_lines.append(line)
            
            # If all lines were filtered out, just return
            if not filtered_lines:
                return
                
            # Use the filtered text instead
            text = ''.join(filtered_lines)
        else:
            # For single line, check if it should be filtered
            if any(warning in text for warning in [
                "proot warning: can't sanitize binding",
                "WARNING: apt does not have a stable CLI interface"
            ]):
                return
        
        # Check if we need to add a newline before the new text
        # Only add a newline if:
        # 1. Buffer is not empty
        # 2. We're not in an animation sequence
        # 3. The last character is not a newline
        # 4. The new text doesn't start with a newline
        if (self.buffer.get_char_count() > 0 and 
            not self.last_line_was_animation):
            
            # Get the last character in the buffer
            end_iter = self.buffer.get_end_iter()
            start_iter = end_iter.copy()
            if start_iter.backward_char():  # This returns False if we can't move back (empty buffer)
                last_char = self.buffer.get_text(start_iter, end_iter, False)
                
                # If the last character isn't a newline and the new text doesn't start with one,
                # add a newline before the new text
                if last_char != '\n' and not text.startswith('\n'):
                    # Insert a newline first
                    self.buffer.insert(end_iter, '\n')
        
        # Process text with ANSI escape sequences
        if with_ansi:
            self.ansi_parser.apply_formatting(self.buffer, text)
        else:
            # Just append the text without processing
            end_iter = self.buffer.get_end_iter()
            self.buffer.insert(end_iter, text)
        
        # Scroll to the end
        self._scroll_to_end()
    
    def _replace_last_line(self, text, with_ansi=True):
        """Replace the last line of the terminal with new text (for carriage returns)"""
        # Get the end of the buffer
        end_iter = self.buffer.get_end_iter()
        
        # Find the start of the current line
        line_start = self._find_line_start(end_iter)
        
        # Delete the content of the line
        self.buffer.delete(line_start, end_iter)
        
        # Insert the new text
        if with_ansi:
            self.ansi_parser.apply_formatting(self.buffer, text)
        else:
            self.buffer.insert(self.buffer.get_end_iter(), text)
        
        # Scroll to the end
        self._scroll_to_end()
    
    def _find_line_start(self, end_iter):
        """Find the start of the current line, handling edge cases better"""
        # Create a copy of the iterator
        start_iter = end_iter.copy()
        
        # Move to the start of the line
        start_iter.set_line_offset(0)
        
        return start_iter
    
    def _scroll_to_end(self):
        """Scroll the view to the end"""
        # Using Gdk.threads_enter/leave to ensure thread safety for GTK operations
        try:
            # Make sure text_view and buffer are still valid and accessible
            if not self.text_view or not isinstance(self.text_view, Gtk.TextView):
                return False
                
            # Get the current buffer from the text view, don't rely on possibly stale self.buffer
            buffer = self.text_view.get_buffer()
            if not buffer or not isinstance(buffer, Gtk.TextBuffer):
                return False
            
            # Verify that the text_view is still mapped (visible on screen)
            # This helps avoid issues when scrolling during widget destruction
            if not self.text_view.get_mapped():
                return False
            
            # Get the adjustment for the vertical scrollbar
            sw = self.text_view.get_parent()
            if not sw or not isinstance(sw, Gtk.ScrolledWindow):
                return False
                
            vadj = sw.get_vadjustment()
            if not vadj:
                return False
            
            # Simple and reliable approach: just set the value to the upper limit
            # This avoids the need for creating and managing marks
            GLib.idle_add(lambda: vadj.set_value(vadj.get_upper() - vadj.get_page_size()))
            return False
        except Exception:
            # Silently catch all exceptions during scrolling
            return False
    
    def clear(self):
        """Clear the terminal view"""
        self.buffer.delete(self.buffer.get_start_iter(), self.buffer.get_end_iter())
        self.last_line_was_animation = False
        self.line_buffer = ""
    
    def get_text(self):
        """Get the terminal contents"""
        start_iter, end_iter = self.buffer.get_bounds()
        return self.buffer.get_text(start_iter, end_iter, False)
        
    def save_terminal_output(self, parent_window=None, app_name=None):
        """Save terminal contents to a file
        
        Args:
            parent_window: The parent window for the file dialog
            app_name: Optional app name for the default filename
        """
        text = self.get_text()
        
        # Create file chooser dialog
        file_dialog = Gtk.FileChooserDialog(
            title="Save Terminal Output",
            parent=parent_window,
            action=Gtk.FileChooserAction.SAVE
        )
        file_dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )
        
        # Set default filename and location
        home_dir = os.path.expanduser("~")
        file_dialog.set_current_folder(home_dir)
        default_filename = f"{app_name.lower().replace(' ', '_')}_output.log" if app_name else "terminal_output.log"
        file_dialog.set_current_name(default_filename)
        
        # Add file filters
        text_filter = Gtk.FileFilter()
        text_filter.set_name("Text files")
        text_filter.add_mime_type("text/plain")
        text_filter.add_pattern("*.txt")
        text_filter.add_pattern("*.log")
        file_dialog.add_filter(text_filter)
        
        all_filter = Gtk.FileFilter()
        all_filter.set_name("All files")
        all_filter.add_pattern("*")
        file_dialog.add_filter(all_filter)
        
        # Show the dialog
        response = file_dialog.run()
        result = False
        
        if response == Gtk.ResponseType.OK:
            filename = file_dialog.get_filename()
            try:
                # Save current content
                with open(filename, 'w') as f:
                    # Write the clean text without ANSI codes
                    f.write(self.ansi_parser.strip_ansi(text))
                self.append_text(f"\nOutput saved to {filename}\n")
                result = True
            except Exception as e:
                self.append_text(f"\nError saving output: {e}\n")
                result = False
        
        file_dialog.destroy()
        return result


class CommandRunner:
    """Runs shell commands and displays output in a terminal"""
    
    def __init__(self, terminal):
        self.terminal = terminal
        self.process = None
        self.is_running = False
        self.master_fd = None
        self.slave_fd = None
        self.io_watch_id = None
        self.final_output_received = False
        self.output_buffer = bytearray()  # Buffer to accumulate output
    
    def run_command(self, command, on_complete=None):
        """Run a shell command and display its output in the terminal"""
        if self.is_running:
            self.terminal.append_text("A command is already running. Please wait for it to complete.\n")
            return False
        
        self.is_running = True
        self.final_output_received = False
        self.output_buffer = bytearray()
        self.terminal.append_text(f"Running: {command}\n\n")
        
        try:
            # Create a pseudo-terminal for interactive commands
            self.master_fd, self.slave_fd = pty.openpty()
            
            # Configure terminal size to match a standard terminal
            fcntl.ioctl(self.slave_fd, 
                        termios.TIOCSWINSZ, 
                        struct.pack("HHHH", 24, 80, 0, 0))
            
            # Make the master file descriptor non-blocking
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            # Set up environment variables for a proper interactive terminal
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            env['COLUMNS'] = '80'
            env['LINES'] = '24'
            env['APT_FORCE_CLI_PROMPT'] = '1'
            env['PYTHONUTF8'] = '1'  # Ensure Python uses UTF-8
            
            # Start the process attached to the slave end of the pty
            self.process = subprocess.Popen(
                ['bash', '-c', command],
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                universal_newlines=False,  # Using binary mode for pty
                env=env,
                preexec_fn=os.setsid  # Create a new process group
            )
            
            # Close the slave end of the pty in the parent process
            os.close(self.slave_fd)
            self.slave_fd = None
            
            # Set up an IO watch to read from the pty master
            self.io_watch_id = GLib.io_add_watch(
                self.master_fd,
                GLib.PRIORITY_DEFAULT,
                GLib.IOCondition.IN | GLib.IOCondition.HUP,
                self._on_pty_output
            )
            
            # Start a thread to monitor the process completion
            def monitor_process():
                return_code = self.process.wait()
                
                # Ensure we've processed all the output before marking as complete
                # Wait until the IO watch has been removed
                time.sleep(0.2)
                
                # Process any remaining data
                self._flush_output_buffer()
                
                # Mark that we've received the final output
                self.final_output_received = True
                
                # Now notify UI that command is complete
                GLib.idle_add(self._command_completed, return_code, on_complete)
            
            thread = threading.Thread(target=monitor_process)
            thread.daemon = True
            thread.start()
            
            return True
            
        except Exception as e:
            self.terminal.append_text(f"Error running command: {str(e)}\n")
            self._cleanup()
            return False
    
    def _on_pty_output(self, fd, condition):
        """Handle output from the pty"""
        if condition & GLib.IOCondition.IN:
            try:
                data = os.read(fd, 4096)
                if data:
                    # Add to our buffer
                    self.output_buffer.extend(data)
                    
                    # Try to process as much of the buffer as possible
                    self._process_output_buffer()
                    
                    return True
            except OSError:
                pass
        
        # HUP or error condition
        self._cleanup_io_watch()
        return False
    
    def _process_output_buffer(self):
        """Process the output buffer, trying to find complete lines or control sequences"""
        # Find any complete lines in the buffer
        try:
            # Decode as much as possible
            text = self.output_buffer.decode('utf-8', errors='replace')
            
            # Update the terminal
            GLib.idle_add(self._update_terminal, text)
            
            # Clear the buffer after processing
            self.output_buffer = bytearray()
        except UnicodeDecodeError:
            # If we can't decode everything, try to find complete UTF-8 sequences
            # This is simplified - a real implementation would be more careful
            # about preserving partial UTF-8 sequences at the end of the buffer
            return
    
    def _flush_output_buffer(self):
        """Flush any remaining data in the output buffer"""
        if self.output_buffer:
            try:
                text = self.output_buffer.decode('utf-8', errors='replace')
                GLib.idle_add(self._update_terminal, text)
                self.output_buffer = bytearray()
            except Exception:
                pass
    
    def _update_terminal(self, text):
        """Update the terminal with new text (called from main thread)"""
        self.terminal.append_text(text)
        return False  # Required for GLib.idle_add
    
    def _command_completed(self, return_code, on_complete):
        """Handle command completion (called from main thread)"""
        # Only show the completion message if we've received all the output
        if self.final_output_received:
            # Add a blank line to separate from previous output
            self.terminal.append_text("\n\nCommand completed with return code: " + str(return_code) + "\n")
            self._cleanup()
            
            if on_complete:
                on_complete(return_code)
        
        return False  # Required for GLib.idle_add
    
    def _cleanup_io_watch(self):
        """Clean up the IO watch"""
        if self.io_watch_id is not None:
            GLib.source_remove(self.io_watch_id)
            self.io_watch_id = None
    
    def _cleanup(self):
        """Clean up all resources"""
        self._cleanup_io_watch()
        
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        
        if self.slave_fd is not None:
            try:
                os.close(self.slave_fd)
            except OSError:
                pass
            self.slave_fd = None
        
        self.process = None
        self.is_running = False
    
    def cancel(self):
        """Cancel the running command"""
        if self.is_running and self.process:
            try:
                # Send SIGTERM to the entire process group
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.terminal.append_text("\nCommand terminated by user.\n")
            except Exception as e:
                self.terminal.append_text(f"\nError terminating command: {str(e)}\n")
            
            self._cleanup()
            return True
        
        return False


class TerminalWindow(Gtk.Window):
    """Simple terminal window for demonstration purposes"""
    
    def __init__(self):
        Gtk.Window.__init__(self, title="Terminal Emulator")
        self.set_default_size(800, 500)
        
        # Apply CSS styling
        self.load_css()
        
        # Apply window style class
        self.get_style_context().add_class("terminal-window")
        
        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(main_box)
        
        # Create command entry
        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry_box.set_margin_start(10)
        entry_box.set_margin_end(10)
        entry_box.set_margin_top(10)
        
        self.command_entry = Gtk.Entry()
        self.command_entry.set_placeholder_text("Enter command...")
        self.command_entry.connect("activate", self.on_command_enter)
        entry_box.pack_start(self.command_entry, True, True, 0)
        
        run_button = Gtk.Button(label="Run")
        run_button.get_style_context().add_class("run-button")
        run_button.connect("clicked", self.on_command_enter)
        entry_box.pack_start(run_button, False, False, 0)
        
        clear_button = Gtk.Button(label="Clear")
        clear_button.get_style_context().add_class("clear-button")
        clear_button.connect("clicked", self.on_clear_clicked)
        entry_box.pack_start(clear_button, False, False, 0)
        
        main_box.pack_start(entry_box, False, False, 0)
        
        # Create terminal view
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)
        scrolled_window.set_margin_start(10)
        scrolled_window.set_margin_end(10)
        scrolled_window.set_margin_bottom(10)
        
        self.terminal_view = Gtk.TextView()
        self.terminal_view.set_editable(False)
        self.terminal_view.set_cursor_visible(False)
        self.terminal_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.terminal_view.get_style_context().add_class("terminal-view")
        
        scrolled_window.add(self.terminal_view)
        main_box.pack_start(scrolled_window, True, True, 0)
        
        # Initialize terminal emulator
        self.terminal = TerminalEmulator(self.terminal_view)
        self.command_runner = CommandRunner(self.terminal)
        
        # Show initial message
        self.terminal.append_text("Terminal Emulator Ready\n")
        self.terminal.append_text("Type a command and press Enter to execute it.\n\n")
        
        # Connect cancel button (Ctrl+C) shortcut
        self.connect("key-press-event", self.on_key_press)
        
        # Connect to destroy signal
        self.connect("destroy", Gtk.main_quit)
    
    def load_css(self):
        """Load CSS from terminal_style.css"""
        css_provider = Gtk.CssProvider()
        
        try:
            css_file = "terminal_style.css"
            css_provider.load_from_path(css_file)
            
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception as e:
            print(f"Error loading CSS: {e}")
    
    def on_command_enter(self, widget):
        """Handle command entry"""
        command = self.command_entry.get_text().strip()
        if command:
            self.command_runner.run_command(command)
            self.command_entry.set_text("")
    
    def on_clear_clicked(self, button):
        """Clear the terminal"""
        self.terminal.clear()
    
    def on_key_press(self, widget, event):
        """Handle key press events"""
        # Check for Ctrl+C to cancel running command
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval == Gdk.KEY_c:
            if self.command_runner.is_running:
                self.command_runner.cancel()
            return True
        return False


def main():
    """Main function"""
    win = TerminalWindow()
    win.show_all()
    Gtk.main()


# New utility functions for external usage
def create_terminal_widget():
    """Creates a scrolled window with a terminal view ready to use
    
    Returns:
        tuple: (scrolled_window, terminal_emulator, command_runner)
    """
    # Create scrolled window
    scrolled_window = Gtk.ScrolledWindow()
    scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrolled_window.set_hexpand(True)
    scrolled_window.set_vexpand(True)
    
    # Create terminal view
    terminal_view = Gtk.TextView()
    terminal_view.set_editable(False)
    terminal_view.set_cursor_visible(False)
    terminal_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    terminal_view.get_style_context().add_class("terminal-view")
    scrolled_window.add(terminal_view)
    
    # Initialize terminal emulator and command runner
    terminal_emulator = TerminalEmulator(terminal_view)
    command_runner = CommandRunner(terminal_emulator)
    
    return scrolled_window, terminal_emulator, command_runner


# Path to the CSS file in the style directory
# Using a function to find the CSS file with fallbacks to handle different installation scenarios
def find_terminal_css_path():
    """Find the terminal CSS file path with two fallback options"""
    possible_paths = [
        # Current directory with style subfolder (development)
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "style", "terminal_style.css"),
        
        # Termux-specific path
        os.path.join("/data/data/com.termux/files/usr/opt/appstore/style/terminal_style.css"),
    ]
    
    # Try each possible path
    for path in possible_paths:
        if os.path.isfile(path):
            print(f"Found terminal CSS at: {path}")
            return path
    
    # If not found, return the default path (will fall back to inline CSS)
    default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style", "terminal_style.css")
    print(f"Terminal CSS not found, using default path: {default_path}")
    return default_path

TERMINAL_CSS_PATH = find_terminal_css_path()

def apply_terminal_css(widget):
    """Apply terminal CSS styles to a widget"""
    css_provider = Gtk.CssProvider()
    
    # Try to load from the external CSS file first
    try:
        css_provider.load_from_path(TERMINAL_CSS_PATH)
        print(f"Successfully loaded terminal CSS from {TERMINAL_CSS_PATH}")
    except Exception as e:
        # Fall back to inline CSS
        print(f"Could not load terminal CSS from {TERMINAL_CSS_PATH}: {e}")
        print("Using fallback inline CSS")
        css_provider.load_from_data(b"""
        .terminal-view {
            background-color: #282c34;
            color: #abb2bf;
            font-family: monospace;
            padding: 8px;
        }
        .terminal-window {
            background-color: #21252b;
        }
        .run-button {
            background-color: #98c379;
            color: #282c34;
        }
        .clear-button {
            background-color: #e06c75;
            color: #282c34;
        }
        """)
    
    style_context = widget.get_style_context()
    style_context.add_provider(
        css_provider, 
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


def show_command_output(command, app_name=None, parent=None):
    """Show a command output window and run the command
    
    This is a convenience function that creates a CommandOutputWindow,
    runs the command, and returns the window object.
    
    Args:
        command: The command to run
        app_name: The name of the application (for the window title)
        parent: The parent window
        
    Returns:
        CommandOutputWindow: The command output window
    """
    window = CommandOutputWindow(
        title=f"Running {app_name}" if app_name else "Command Output", 
        parent=parent
    )
    window.run_command(command, app_name)
    return window


class CommandOutputWindow(Gtk.Window):
    """Window to display command output with terminal emulation"""
    
    def __init__(self, title="Command Output", parent=None):
        """Initialize the command output window
        
        Args:
            title: Window title
            parent: Parent window (optional)
        """
        Gtk.Window.__init__(self, title=title)
        
        if parent:
            self.set_transient_for(parent)
            self.set_destroy_with_parent(True)
            
        self.set_default_size(700, 500)
        self.set_border_width(10)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.get_style_context().add_class("command-output-dialog")
        
        # Apply CSS styling
        apply_terminal_css(self)
        
        # Set window icon
        icon_name = "utilities-terminal"
        icon_theme = Gtk.IconTheme.get_default()
        if icon_theme.has_icon(icon_name):
            self.set_icon_name(icon_name)
            
        # Create main box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(self.main_box)
        
        # Create terminal widget
        self.scrolled_window, self.terminal_emulator, self.command_runner = create_terminal_widget()
        self.main_box.pack_start(self.scrolled_window, True, True, 0)
        
        # Create button box
        self.button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.button_box.set_halign(Gtk.Align.END)
        self.button_box.set_margin_top(12)
        self.main_box.pack_start(self.button_box, False, False, 0)
        
        # Create clear button
        self.clear_button = Gtk.Button()
        self.clear_button.set_tooltip_text("Clear terminal output")
        clear_icon = Gtk.Image.new_from_icon_name("edit-clear-symbolic", Gtk.IconSize.BUTTON)
        self.clear_button.set_image(clear_icon)
        self.clear_button.get_style_context().add_class("command-output-clear-button")
        self.button_box.pack_start(self.clear_button, False, False, 0)
        
        # Create save button
        self.save_button = Gtk.Button()
        self.save_button.set_tooltip_text("Save terminal output to file")
        save_icon = Gtk.Image.new_from_icon_name("document-save-symbolic", Gtk.IconSize.BUTTON)
        self.save_button.set_image(save_icon)
        self.save_button.get_style_context().add_class("command-output-save-button")
        self.button_box.pack_start(self.save_button, False, False, 0)
        
        # Connect clear button
        self.clear_button.connect("clicked", lambda b: self.terminal_emulator.clear())
        
        # Connect save button
        self.save_button.connect("clicked", lambda b: self.terminal_emulator.save_terminal_output(self))
        
        # Connect window close event
        self.connect("delete-event", self.on_window_close)
        
    def run_command(self, command, app_name=None):
        """Run a command and display its output
        
        Args:
            command: The command to run
            app_name: The name of the app (for save dialog)
        """
        self.app_name = app_name
        self.terminal_emulator.append_text(f"Running: {command}\n\n")
        self.command_runner.run_command(command)
        self.show_all()
        self.present()
        
    def on_window_close(self, widget, event):
        """Handle window close event"""
        if self.command_runner.is_running:
            self.command_runner.cancel()
        return False


if __name__ == "__main__":
    main() 