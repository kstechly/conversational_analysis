Runs in the terminal.
`python3 conversational_analysis_editor.py [INPUT.txt]`

# Conversational Analysis Editor
A simple terminal-based editor for conversational data, designed for editing dialogue transcripts. Built to follow the format in Hepburn and Bolden's chapter 4 (pages: 57-76) in the Handbook of Conversational Analysis (2012): *The Conversation Analytic Approach to Transcription*.
## Overview
This editor allows you to:
* View and edit dialogue entries with speaker names and content
* Navigate through multi-line entries
* Split and combine dialogue entries
* Save and load dialogue files
* Undo changes

If a filename is provided, the editor will load that file. Otherwise, it will start with a blank document.

## File Format
The editor uses a simple tab-separated format:
* Each line represents one dialogue entry
* Speaker name and content are separated by a tab character
- Example: `Speaker Name[TAB]This is what they said`
## Keyboard Shortcuts
### Navigation
* Arrow keys: Move the cursor
* Tab: Toggle between speaker name and content fields
* Home: Move cursor to beginning of line
* End: Move cursor to end of line (in content field)
### Editing
* Enter (in content field): Split the current entry at cursor position
* Backspace at beginning of entry: Combine with previous entry
* \\ (in speaker field): Clear the speaker name
* Page Up: Move current entry up (swap with previous entry)
* Page Down: Move current entry down (swap with next entry)
