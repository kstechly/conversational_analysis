#!/usr/bin/env python3
import curses
import sys
import os

class DialogueEntry:
    def __init__(self, speaker, text):
        self.speaker = speaker
        self.text = text

class Editor:
    def __init__(self, stdscr, filename=None):
        self.stdscr = stdscr
        self.filename = filename
        self.entries = []
        self.display_lines = []  # Each element: (entry_index, offset, display_text)
        self.cursor_display_line = 0  # Which display line the cursor is on
        self.cursor_field = 'content'  # Either 'speaker' or 'content'
        self.cursor_pos = 0  # Position within the current field's text
        self.status_msg = ""
        self.scroll_offset = 0  # New: Track how many lines we've scrolled
        self.keystroke_count = 0
        self.autosave_interval = 10  # Define autosave_interval
        self.undo_stack = []  # New: Stack for undo functionality
        self.initial_load = True  # Flag to track initial load

        # Fixed column widths.
        self.ln_width = 6      # line number column width
        self.sp_width = 15     # speaker name column width
        self.col_sep = 1       # separator

        # Load file if provided; else start with one default entry.
        if filename:
            self.load_file(filename)
        else:
            self.entries.append(DialogueEntry("Speaker", ""))
        self.reflow()
        self.initial_load = False  # Set to false after initial reflow
        
        # Save initial state for undo
        self.save_undo_state()

    def load_file(self, filename):
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.rstrip("\n")
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        self.entries.append(DialogueEntry(parts[0], parts[1]))
                    else:
                        self.entries.append(DialogueEntry(parts[0], ""))
        except Exception as e:
            self.status_msg = f"Error loading file: {e}"

    def save_file(self):
        if self.filename is None:
            self.status_msg = "No filename provided."
            return
        try:
            with open(self.filename, 'w') as f:
                for entry in self.entries:
                    f.write(f"{entry.speaker}\t{entry.text}\n")
            self.status_msg = "File saved."
        except Exception as e:
            self.status_msg = f"Error saving file: {e}"

    def reflow(self):
        """
        Recalculate display_lines from self.entries based on the current window size.
        Also performs automatic reflowing of consecutive entries with the same speaker
        (unless they contain square brackets).
        """
        # First, combine consecutive entries with the same speaker if they don't contain brackets
        # Only do this during initial load
        if self.initial_load:
            self.combine_same_speaker_entries()
        
        self.display_lines = []
        height, width = self.stdscr.getmaxyx()
        content_width = width - (self.ln_width + self.sp_width + 2 * self.col_sep)
        
        # Process each dialogue entry.
        for entry_idx, entry in enumerate(self.entries):
            wrapped = self.wrap_text(entry.text, content_width)
            if not wrapped:
                wrapped = [(0, "")]
            
            for offset, line in wrapped:
                self.display_lines.append((entry_idx, offset, line))
        
        # Clamp cursor if needed.
        if self.cursor_display_line >= len(self.display_lines):
            self.cursor_display_line = len(self.display_lines) - 1
            self.cursor_pos = 0
        cur_len = self.get_current_field_length()
        if self.cursor_pos > cur_len:
            self.cursor_pos = cur_len

    def combine_same_speaker_entries(self):
        """
        Combine consecutive entries with the same speaker if they don't contain square brackets.
        """
        i = 0
        while i < len(self.entries) - 1:
            current = self.entries[i]
            next_entry = self.entries[i + 1]
            
            # Check if entries have the same speaker and neither contains square brackets
            if (current.speaker == next_entry.speaker and 
                '[' not in current.text and ']' not in current.text and
                '[' not in next_entry.text and ']' not in next_entry.text):
                
                # Check if combining would exceed max line length
                combined_length = len(current.text) + 1 + len(next_entry.text)  # +1 for space
                if combined_length <= 150:  # Allow for multiple wrapped lines
                    # Add a space if the current entry doesn't end with punctuation
                    if current.text and current.text[-1] not in '.!?,:;':
                        current.text += ' '
                    
                    # Combine the entries
                    current.text += next_entry.text
                    
                    # Remove the next entry
                    self.entries.pop(i + 1)
                    
                    # Don't increment i, so we check the new next entry
                    continue
            
            i += 1

    def wrap_text(self, text, width):
        """
        Wrap text into a list of (start_offset, substring) tuples,
        trying to break at spaces when possible.
        Enforces a maximum line length of 50 characters.
        """
        # Enforce maximum width of 50 characters
        max_width = min(width, 50)
        
        lines = []
        start = 0
        while start < len(text):
            remaining = len(text) - start
            if remaining <= max_width:
                lines.append((start, text[start:]))
                break
            segment = text[start:start+max_width+1]
            break_index = segment.rfind(" ")
            if break_index == -1 or break_index == 0:
                lines.append((start, text[start:start+max_width]))
                start += max_width
            else:
                lines.append((start, text[start:start+break_index]))
                start += break_index + 1  # Skip the space
        return lines

    def render(self):
        # Use erase() plus double-buffering to avoid flashing.
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        content_width = width - (self.ln_width + self.sp_width + 2 * self.col_sep)
        max_display_lines = height - 1  # Reserve bottom line for status

        # Apply scroll offset to determine which lines to display
        start_line = self.scroll_offset
        end_line = min(start_line + max_display_lines, len(self.display_lines))
        
        # Render visible lines
        for i, line_idx in enumerate(range(start_line, end_line)):
            entry_idx, offset, line_text = self.display_lines[line_idx]
            entry = self.entries[entry_idx]
            ln_str = str(line_idx+1).rjust(self.ln_width)
            try:
                self.stdscr.addstr(i, 0, ln_str)
            except curses.error:
                pass
            sp_str = entry.speaker.ljust(self.sp_width)
            try:
                self.stdscr.addstr(i, self.ln_width + self.col_sep, sp_str)
            except curses.error:
                pass
            content_str = line_text.ljust(content_width)
            try:
                self.stdscr.addstr(i, self.ln_width + self.sp_width + 2 * self.col_sep, content_str)
            except curses.error:
                pass

        try:
            self.stdscr.addstr(height-1, 0, self.status_msg[:width-1])
        except curses.error:
            pass

        # Compute cursor x coordinate.
        if self.cursor_field == 'speaker':
            x = self.ln_width + self.col_sep + self.cursor_pos
        else:
            x = self.ln_width + self.sp_width + 2 * self.col_sep + self.cursor_pos
        if x >= width:
            x = width - 1
            
        # Compute cursor y coordinate, accounting for scroll offset
        y = self.cursor_display_line - self.scroll_offset
        if y < 0:
            y = 0
        elif y >= max_display_lines:
            y = max_display_lines - 1
            
        try:
            self.stdscr.move(y, x)
        except curses.error:
            pass

        self.stdscr.noutrefresh()
        curses.doupdate()

    def process_key(self, key):
        self.status_msg = ""
        
        # Increment keystroke counter and check for autosave
        self.keystroke_count += 1
        if self.keystroke_count >= self.autosave_interval:
            self.autosave()
            self.keystroke_count = 0
        
        # Debug key code if it's a control character
        if key < 32 and key != 9 and key != 10:  # Not tab or enter
            self.status_msg = f"Control key pressed: ASCII {key}"
            return
            
        # Handle Ctrl+\ (ASCII 28) specifically
        if key == 28:  # Ctrl+\
            self.status_msg = "Ctrl+\\ pressed (ignored)"
            return
            
        # Single key shortcuts
        if key == ord('\\') and self.cursor_field == 'speaker':  # \ to clear speaker
            self.save_undo_state()
            entry_idx, _, _ = self.display_lines[self.cursor_display_line]
            self.entries[entry_idx].speaker = ""
            self.cursor_pos = 0
            self.reflow()
            return
        if key == ord('`'):  # ` to save
            self.save_file()
            return
        if key == ord('~'):  # ~ to quit
            raise KeyboardInterrupt
        if key == curses.KEY_DC:  # Delete key for undo
            self.undo()
            return

        # Shortcut: Home key moves cursor to beginning-of-line
        if key == curses.KEY_HOME:
            self.cursor_pos = 0
            return
            
        # Shortcut: End key moves cursor to end-of-line in content.
        if key == curses.KEY_END and self.cursor_field == 'content':
            self.cursor_pos = self.get_current_field_length()
            return

        # Move current entry up (Page Up)
        if key == curses.KEY_PPAGE:
            self.move_entry_up()
            return
            
        # Move current entry down (Page Down)
        if key == curses.KEY_NPAGE:
            self.move_entry_down()
            return

        if key == 9:  # Tab toggles active field.
            self.cursor_field = 'speaker' if self.cursor_field == 'content' else 'content'
            self.cursor_pos = 0
            return
        if key == 19:  # Ctrl+S to save.
            self.save_file()
            return
        if key == 17:  # Ctrl+Q to quit.
            raise KeyboardInterrupt

        # Handle Enter key (ASCII 10) to split the current dialogue entry.
        if key in (10, curses.KEY_ENTER):
            if self.cursor_field == 'content':
                self.save_undo_state()
                self.split_line_at_cursor()
            return

        # Navigation: Arrow keys.
        if key == curses.KEY_UP:
            if self.cursor_display_line > 0:
                self.cursor_display_line -= 1
                self.cursor_pos = min(self.cursor_pos, self.get_current_field_length())
                # Scroll up if needed
                if self.cursor_display_line < self.scroll_offset:
                    self.scroll_offset = self.cursor_display_line
            return
        if key == curses.KEY_DOWN:
            if self.cursor_display_line < len(self.display_lines) - 1:
                self.cursor_display_line += 1
                self.cursor_pos = min(self.cursor_pos, self.get_current_field_length())
                # Scroll down if needed
                height, _ = self.stdscr.getmaxyx()
                max_visible = height - 1  # Reserve bottom line for status
                if self.cursor_display_line >= self.scroll_offset + max_visible:
                    self.scroll_offset = self.cursor_display_line - max_visible + 1
            return
        if key == curses.KEY_LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
            else:
                # If at beginning of a wrapped content line, move to the end of the previous wrap.
                if self.cursor_field == 'content':
                    current_entry_idx, _, _ = self.display_lines[self.cursor_display_line]
                    for i in range(self.cursor_display_line - 1, -1, -1):
                        if self.display_lines[i][0] == current_entry_idx:
                            self.cursor_display_line = i
                            self.cursor_pos = len(self.display_lines[i][2])
                            break
            return
        if key == curses.KEY_RIGHT:
            if self.cursor_pos < self.get_current_field_length():
                self.cursor_pos += 1
            else:
                # If at end of a content line, move to the beginning of the next line
                if self.cursor_field == 'content' and self.cursor_display_line < len(self.display_lines) - 1:
                    # Check if the next line is a continuation of the same entry or a new entry
                    current_entry_idx, _, _ = self.display_lines[self.cursor_display_line]
                    next_entry_idx, _, _ = self.display_lines[self.cursor_display_line + 1]
                    
                    # Move to the next line regardless of whether it's the same entry or not
                    self.cursor_display_line += 1
                    self.cursor_pos = 0
                    
                    # Scroll down if needed
                    height, _ = self.stdscr.getmaxyx()
                    max_visible = height - 1  # Reserve bottom line for status
                    if self.cursor_display_line >= self.scroll_offset + max_visible:
                        self.scroll_offset = self.cursor_display_line - max_visible + 1
            return
            
        # Handle backspace
        if key in (curses.KEY_BACKSPACE, 127):
            self.handle_backspace()
            return

        # Only process printable characters (32-126, excluding our shortcuts)
        if 32 <= key <= 126 and chr(key) not in ['\\', '`', '~']:
            self.handle_insert(chr(key))
            return

    def get_current_field_length(self):
        entry_idx, offset, line_text = self.display_lines[self.cursor_display_line]
        entry = self.entries[entry_idx]
        if self.cursor_field == 'speaker':
            return len(entry.speaker)
        else:
            return len(line_text)

    def handle_insert(self, char):
        self.save_undo_state()
        entry_idx, offset, _ = self.display_lines[self.cursor_display_line]
        entry = self.entries[entry_idx]
        if self.cursor_field == 'speaker':
            entry.speaker = entry.speaker[:self.cursor_pos] + char + entry.speaker[self.cursor_pos:]
            self.cursor_pos += 1
            self.reflow()
        else:
            old_actual_offset = offset + self.cursor_pos
            entry.text = entry.text[:old_actual_offset] + char + entry.text[old_actual_offset:]
            new_actual_offset = old_actual_offset + 1
            self.reflow()
            self.set_cursor_for_content(entry_idx, new_actual_offset)

    def handle_backspace(self):
        self.save_undo_state()
        if self.cursor_field == 'speaker':
            entry_idx, _, _ = self.display_lines[self.cursor_display_line]
            entry = self.entries[entry_idx]
            if self.cursor_pos > 0:
                entry.speaker = entry.speaker[:self.cursor_pos-1] + entry.speaker[self.cursor_pos:]
                self.cursor_pos -= 1
            self.reflow()
            return

        # For content field:
        entry_idx, offset, _ = self.display_lines[self.cursor_display_line]
        entry = self.entries[entry_idx]
        actual_offset = offset + self.cursor_pos

        # If at beginning of a wrapped line (but not at the very start of text), just merge (move cursor)
        if self.cursor_pos == 0 and offset > 0:
            for i in range(self.cursor_display_line - 1, -1, -1):
                if self.display_lines[i][0] == entry_idx:
                    self.cursor_display_line = i
                    self.cursor_pos = len(self.display_lines[i][2])
                    return

        # If at the beginning of an entry (not a wrapped line) and not the first entry
        if self.cursor_pos == 0 and offset == 0 and entry_idx > 0:
            # Get the previous entry
            prev_entry = self.entries[entry_idx - 1]
            
            # Check if combining would exceed content width
            height, width = self.stdscr.getmaxyx()
            content_width = width - (self.ln_width + self.sp_width + 2 * self.col_sep)
            
            # Only combine if the result won't be too long
            if len(prev_entry.text) + len(entry.text) <= content_width * 3:  # Allow reasonable wrapping
                # Remember the length of the previous entry's text
                prev_text_len = len(prev_entry.text)
                
                # Combine the entries
                prev_entry.text += entry.text
                
                # Remove the current entry
                self.entries.pop(entry_idx)
                
                # Reflow to update display
                self.reflow()
                
                # Position cursor at the join point (beginning of the moved text)
                self.set_cursor_for_content(entry_idx - 1, prev_text_len)
                return

        if actual_offset > 0:
            entry.text = entry.text[:actual_offset-1] + entry.text[actual_offset:]
            new_actual_offset = actual_offset - 1
            self.reflow()
            self.set_cursor_for_content(entry_idx, new_actual_offset)

    def set_cursor_for_content(self, entry_idx, target_offset):
        new_line_index = None
        new_cursor_pos = 0
        for i, (e_idx, off, line_text) in enumerate(self.display_lines):
            if e_idx == entry_idx:
                if off <= target_offset <= off + len(line_text):
                    new_line_index = i
                    new_cursor_pos = target_offset - off
                    break
                elif target_offset > off + len(line_text):
                    continue
        if new_line_index is None:
            for i in range(len(self.display_lines)-1, -1, -1):
                if self.display_lines[i][0] == entry_idx:
                    new_line_index = i
                    new_cursor_pos = len(self.display_lines[i][2])
                    break
        # If exactly at end of a line and a next wrapped line exists for the same entry, jump to next line.
        if new_line_index is not None:
            current_line = self.display_lines[new_line_index]
            if new_cursor_pos == len(current_line[2]):
                next_index = new_line_index + 1
                if next_index < len(self.display_lines) and self.display_lines[next_index][0] == entry_idx:
                    new_line_index = next_index
                    new_cursor_pos = 0
        if new_line_index is not None:
            self.cursor_display_line = new_line_index
            self.cursor_field = 'content'
            self.cursor_pos = new_cursor_pos

    def move_entry_up(self):
        """Move the current entry up one position."""
        self.save_undo_state()
        entry_idx, offset, _ = self.display_lines[self.cursor_display_line]
        
        # If this is a continuation line (not the first line of an entry),
        # we need to split the entry at this point
        if offset > 0:
            # Get the current entry
            entry = self.entries[entry_idx]
            
            # Split the entry at the current offset
            first_part = entry.text[:offset]
            second_part = entry.text[offset:]
            
            # Update the current entry with just the first part
            entry.text = first_part
            
            # Create a new entry with the second part
            new_entry = DialogueEntry(entry.speaker, second_part)
            
            # Insert the new entry after the current one
            self.entries.insert(entry_idx + 1, new_entry)
            
            # Update entry_idx to point to the new entry
            entry_idx += 1
        
        # Can't move up if it's the first entry
        if entry_idx <= 0:
            self.status_msg = "Already at the top"
            return
            
        # Swap with the previous entry
        self.entries[entry_idx], self.entries[entry_idx-1] = self.entries[entry_idx-1], self.entries[entry_idx]
        
        # Reflow to update display
        self.reflow()
        
        # Update cursor position to follow the moved entry
        for i, (e_idx, off, _) in enumerate(self.display_lines):
            if e_idx == entry_idx - 1 and off == 0:  # The entry is now at index-1
                self.cursor_display_line = i
                break
                
        self.status_msg = "Moved entry up"
    
    def move_entry_down(self):
        """Move the current entry down one position."""
        self.save_undo_state()
        entry_idx, offset, _ = self.display_lines[self.cursor_display_line]
        
        # If this is a continuation line (not the first line of an entry),
        # we need to split the entry at this point
        if offset > 0:
            # Get the current entry
            entry = self.entries[entry_idx]
            
            # Split the entry at the current offset
            first_part = entry.text[:offset]
            second_part = entry.text[offset:]
            
            # Update the current entry with just the first part
            entry.text = first_part
            
            # Create a new entry with the second part
            new_entry = DialogueEntry(entry.speaker, second_part)
            
            # Insert the new entry after the current one
            self.entries.insert(entry_idx + 1, new_entry)
            
            # Update entry_idx to point to the new entry
            entry_idx += 1
            
            # Reflow to update display
            self.reflow()
            
            # Find the new position of the second part
            for i, (e_idx, off, _) in enumerate(self.display_lines):
                if e_idx == entry_idx and off == 0:
                    self.cursor_display_line = i
                    break
        
        # Can't move down if it's the last entry
        if entry_idx >= len(self.entries) - 1:
            self.status_msg = "Already at the bottom"
            return
            
        # Swap with the next entry
        self.entries[entry_idx], self.entries[entry_idx+1] = self.entries[entry_idx+1], self.entries[entry_idx]
        
        # Reflow to update display
        self.reflow()
        
        # Update cursor position to follow the moved entry
        for i, (e_idx, off, _) in enumerate(self.display_lines):
            if e_idx == entry_idx + 1 and off == 0:  # The entry is now at index+1
                self.cursor_display_line = i
                break
                
        self.status_msg = "Moved entry down"

    def split_line_at_cursor(self):
        """Split the current line at the cursor position into two separate entries."""
        entry_idx, offset, _ = self.display_lines[self.cursor_display_line]
        entry = self.entries[entry_idx]
        
        # Calculate the actual position in the entry's text
        actual_pos = offset + self.cursor_pos
        
        # Can't split if we're not in the content field
        if self.cursor_field != 'content':
            self.status_msg = "Can only split when cursor is in content"
            return
            
        # Split the text at the cursor position
        first_part = entry.text[:actual_pos]
        second_part = entry.text[actual_pos:]
        
        # Update the current entry with just the first part
        entry.text = first_part
        
        # Create a new entry with the second part and same speaker
        new_entry = DialogueEntry(entry.speaker, second_part)
        
        # Insert the new entry after the current one
        self.entries.insert(entry_idx + 1, new_entry)
        
        # Reflow to update display
        self.reflow()
        
        # Position cursor at the beginning of the new entry
        for i, (e_idx, off, _) in enumerate(self.display_lines):
            if e_idx == entry_idx + 1 and off == 0:
                self.cursor_display_line = i
                self.cursor_pos = 0
                break
                
        self.status_msg = f"Split line at cursor (pos {actual_pos})"

    def get_swap_filename(self):
        """Get the filename for the swap file."""
        if self.filename:
            # Extract just the filename without path
            base_filename = os.path.basename(self.filename)
            return f".{base_filename}.swp"
        return ".unnamed.swp"

    def autosave(self):
        """Save to a swap file."""
        swap_file = self.get_swap_filename()
        try:
            with open(swap_file, 'w') as f:
                for entry in self.entries:
                    f.write(f"{entry.speaker}\t{entry.text}\n")
            self.status_msg = f"Autosaved to {swap_file}"
        except Exception as e:
            self.status_msg = f"Error autosaving: {e}"
            import traceback
            self.status_msg += f" {traceback.format_exc()}"

    def save_undo_state(self):
        """Save the current state to the undo stack."""
        # Create deep copies of entries to avoid reference issues
        entries_copy = []
        for entry in self.entries:
            entries_copy.append(DialogueEntry(entry.speaker, entry.text))
            
        # Save cursor state too
        cursor_state = {
            'cursor_display_line': self.cursor_display_line,
            'cursor_field': self.cursor_field,
            'cursor_pos': self.cursor_pos,
            'scroll_offset': self.scroll_offset
        }
        
        # Add to undo stack (limit stack size to prevent memory issues)
        if len(self.undo_stack) >= 100:
            self.undo_stack.pop(0)  # Remove oldest state
        self.undo_stack.append((entries_copy, cursor_state))

    def undo(self):
        """Restore the previous state from the undo stack."""
        if len(self.undo_stack) <= 1:
            self.status_msg = "Nothing to undo"
            return
            
        # Remove current state
        self.undo_stack.pop()
            
        # Get the previous state
        entries_copy, cursor_state = self.undo_stack[-1]
        
        # Restore entries
        self.entries = []
        for entry in entries_copy:
            self.entries.append(DialogueEntry(entry.speaker, entry.text))
            
        # Restore cursor state
        self.cursor_display_line = cursor_state['cursor_display_line']
        self.cursor_field = cursor_state['cursor_field']
        self.cursor_pos = cursor_state['cursor_pos']
        self.scroll_offset = cursor_state['scroll_offset']
        
        # Reflow to update display
        self.reflow()
        
        self.status_msg = "Undo successful"

def main(stdscr):
    curses.curs_set(1)
    stdscr.keypad(True)
    filename = sys.argv[1] if len(sys.argv) > 1 else None
    editor = Editor(stdscr, filename)
    while True:
        try:
            editor.render()
            key = stdscr.getch()
            editor.process_key(key)
        except KeyboardInterrupt:
            break

if __name__ == '__main__':
    curses.wrapper(main)

