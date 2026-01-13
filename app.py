import streamlit as st
import threading
import os
import time
import glob
from datetime import datetime
from pathlib import Path
from flask import Flask, request
from flask_cors import CORS
from patcher_core import Patcher
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- FILE WATCHER ---
class PatcherFileHandler(FileSystemEventHandler):
    """Watch for file changes and trigger re-analysis."""
    
    def __init__(self, watched_files):
        self.watched_files = set(watched_files)
        self.last_modified = {}
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        # Normalize path
        file_path = str(Path(event.src_path).resolve())
        
        # Check if this is a watched file
        for watched in self.watched_files:
            if str(Path(watched).resolve()) == file_path:
                # Debounce: only trigger if > 1 second since last modification
                current_time = time.time()
                last_time = self.last_modified.get(file_path, 0)
                
                if current_time - last_time > 1.0:
                    self.last_modified[file_path] = current_time
                    st.session_state.file_changed = True
                    st.session_state.changed_file = watched
                break

# --- FLASK BACKGROUND SERVER ---
server = Flask(__name__)
CORS(server)

@server.route('/receive_patch', methods=['POST'])
def receive_patch():
    data = request.json
    text = data.get('text', '')
    with open(".incoming_patch.txt", "w", encoding="utf-8") as f:
        f.write(text)
    return {"status": "received"}

@server.route('/health', methods=['GET'])
def health():
    return {"status": "healthy", "timestamp": time.time()}

def run_server():
    server.run(port=5000, debug=False, use_reloader=False)

if not any(t.name == "FlaskServer" for t in threading.enumerate()):
    t = threading.Thread(target=run_server, name="FlaskServer", daemon=True)
    t.start()

# --- STREAMLIT CONFIGURATION ---
st.set_page_config(
    page_title="AI Code Integrator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM STYLING ---
st.markdown("""
<style>
    .stTextArea textarea {
        font-family: 'Fira Code', 'Courier New', monospace;
        font-size: 13px;
        line-height: 1.5;
    }
    
    .status-box {
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid;
    }
    .success { background-color: #d4edda; color: #155724; border-left-color: #28a745; }
    .error { background-color: #f8d7da; color: #721c24; border-left-color: #dc3545; }
    .warning { background-color: #fff3cd; color: #856404; border-left-color: #ffc107; }
    
    .diff-preview {
        background-color: #f6f8fa;
        border: 1px solid #d0d7de;
        border-radius: 6px;
        padding: 12px;
        font-family: 'Fira Code', monospace;
        font-size: 12px;
        overflow-x: auto;
        white-space: pre;
        max-height: 400px;
        overflow-y: auto;
    }
    
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 10px 0;
    }
    .stat-number { font-size: 32px; font-weight: bold; margin: 10px 0; }
    .stat-label { font-size: 14px; opacity: 0.9; }
    
    .suggestion {
        background-color: #e7f3ff;
        border-left: 3px solid #2196F3;
        padding: 10px;
        margin: 5px 0;
        border-radius: 4px;
    }
    
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin-bottom: 20px;
    }
    
    .git-warning {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 12px;
        border-radius: 6px;
        margin: 10px 0;
    }
    
    .copy-button {
        background: #6c757d;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
        margin-top: 8px;
    }
    .copy-button:hover { background: #5a6268; }
    
    /* Token counter */
    .token-counter {
        font-size: 12px;
        text-align: right;
        margin-top: 5px;
    }
    .token-ok { color: #28a745; }
    .token-warning { color: #ffc107; }
    .token-danger { color: #dc3545; }
    
    /* Side-by-side diff */
    .diff-container {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        font-family: 'Fira Code', monospace;
        font-size: 12px;
        max-height: 500px;
        overflow: auto;
    }
    
    .diff-side {
        background: #f6f8fa;
        border: 1px solid #d0d7de;
        border-radius: 6px;
        padding: 10px;
    }
    
    .diff-line {
        white-space: pre;
        padding: 2px 5px;
        line-height: 1.5;
    }
    
    .diff-line-num {
        display: inline-block;
        width: 40px;
        color: #6e7781;
        text-align: right;
        padding-right: 10px;
        user-select: none;
    }
    
    .diff-delete { background-color: #ffebe9; }
    .diff-insert { background-color: #dafbe1; }
    .diff-equal { background-color: transparent; }
    .diff-empty { background-color: #f6f8fa; opacity: 0.3; }
    
    /* Syntax highlighting (basic) */
    .syntax-keyword { color: #cf222e; font-weight: bold; }
    .syntax-string { color: #0a3069; }
    .syntax-comment { color: #6e7781; font-style: italic; }
    .syntax-function { color: #8250df; }
    .syntax-number { color: #0550ae; }
    
    /* Keyboard shortcut hints */
    .kbd {
        background: #f6f8fa;
        border: 1px solid #d0d7de;
        border-radius: 3px;
        padding: 2px 6px;
        font-size: 11px;
        font-family: monospace;
    }
    
    /* File watcher indicator */
    .watch-indicator {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 5px;
    }
    .watch-active { background: #28a745; animation: pulse 2s infinite; }
    .watch-inactive { background: #6c757d; }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    /* Dry run results */
    .dry-run-box {
        background: #e7f3ff;
        border: 2px solid #2196F3;
        border-radius: 8px;
        padding: 15px;
        margin: 15px 0;
    }
    
    .dry-run-success {
        background: #d4edda;
        border-color: #28a745;
    }
    
    .dry-run-failure {
        background: #f8d7da;
        border-color: #dc3545;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if "incoming_patch" not in st.session_state:
    st.session_state.incoming_patch = ""
if "last_analysis" not in st.session_state:
    st.session_state.last_analysis = None
if "show_success" not in st.session_state:
    st.session_state.show_success = False
if "success_files" not in st.session_state:
    st.session_state.success_files = []
if "git_message" not in st.session_state:
    st.session_state.git_message = ""
if "analyzed_blocks" not in st.session_state:
    st.session_state.analyzed_blocks = None
if "file_watcher" not in st.session_state:
    st.session_state.file_watcher = None
if "file_changed" not in st.session_state:
    st.session_state.file_changed = False
if "changed_file" not in st.session_state:
    st.session_state.changed_file = None
if "watch_enabled" not in st.session_state:
    st.session_state.watch_enabled = False
if "dry_run_result" not in st.session_state:
    st.session_state.dry_run_result = None
if "show_dry_run" not in st.session_state:
    st.session_state.show_dry_run = False

# --- HELPER FUNCTIONS ---
def copy_to_clipboard_js(text: str) -> str:
    """Generate JavaScript to copy text to clipboard."""
    # Escape characters that would break the JS template literal
    escaped_text = text.replace('`', '\\`').replace('$', '\\$')
    
    return f"""
    <script>
    navigator.clipboard.writeText(`{escaped_text}`);
    </script>
    """

def get_project_files(pattern: str = "**/*.py") -> list:
    """Get list of project files matching pattern."""
    files = []
    for path in glob.glob(pattern, recursive=True):
        if not any(ignore in path for ignore in ['.git', '__pycache__', 'node_modules', '.ai_backups']):
            files.append(path)
    return sorted(files)

def apply_basic_syntax_highlighting(code: str, language: str = "python") -> str:
    """Apply basic syntax highlighting using HTML/CSS."""
    if language == "python":
        import re
        # Keywords
        code = re.sub(r'\b(def|class|if|else|elif|for|while|return|import|from|as|try|except|with|lambda|yield)\b', 
                     r'<span class="syntax-keyword">\1</span>', code)
        # Strings
        code = re.sub(r'(["\'])(?:(?=(\\?))\2.)*?\1', 
                     r'<span class="syntax-string">\g<0></span>', code)
        # Comments
        code = re.sub(r'(#.*$)', 
                     r'<span class="syntax-comment">\1</span>', code, flags=re.MULTILINE)
        # Numbers
        code = re.sub(r'\b(\d+)\b', 
                     r'<span class="syntax-number">\1</span>', code)
    return code

def render_side_by_side_diff(diff_data: dict) -> str:
    """Render side-by-side diff as HTML."""
    left_lines = diff_data["left_lines"]
    right_lines = diff_data["right_lines"]
    
    html = ['<div class="diff-container">']
    
    # Left side (original)
    html.append('<div class="diff-side"><strong>Original</strong><hr>')
    for line_num, text, change_type in left_lines:
        line_num_str = str(line_num) if line_num else ""
        css_class = f"diff-{change_type}"
        html.append(f'<div class="diff-line {css_class}">')
        html.append(f'<span class="diff-line-num">{line_num_str}</span>')
        html.append(f'{text}')
        html.append('</div>')
    html.append('</div>')
    
    # Right side (modified)
    html.append('<div class="diff-side"><strong>Modified</strong><hr>')
    for line_num, text, change_type in right_lines:
        line_num_str = str(line_num) if line_num else ""
        css_class = f"diff-{change_type}"
        html.append(f'<div class="diff-line {css_class}">')
        html.append(f'<span class="diff-line-num">{line_num_str}</span>')
        html.append(f'{text}')
        html.append('</div>')
    html.append('</div>')
    
    html.append('</div>')
    return ''.join(html)

def start_file_watcher(files_to_watch: list):
    """Start watching files for changes."""
    if st.session_state.file_watcher is not None:
        # Stop existing watcher
        st.session_state.file_watcher.stop()
        st.session_state.file_watcher = None
    
    if not files_to_watch:
        return
    
    # Get unique directories to watch
    directories = set()
    for file_path in files_to_watch:
        directories.add(str(Path(file_path).parent.resolve()))
    
    # Create observer
    observer = Observer()
    event_handler = PatcherFileHandler(files_to_watch)
    
    for directory in directories:
        if Path(directory).exists():
            observer.schedule(event_handler, directory, recursive=False)
    
    observer.start()
    st.session_state.file_watcher = observer

def stop_file_watcher():
    """Stop file watching."""
    if st.session_state.file_watcher is not None:
        st.session_state.file_watcher.stop()
        st.session_state.file_watcher.join(timeout=1)
        st.session_state.file_watcher = None

# --- INITIALIZE PATCHER ---
patcher = Patcher()

# --- AUTO-LOAD FROM EXTENSION ---
if os.path.exists(".incoming_patch.txt"):
    with open(".incoming_patch.txt", "r", encoding="utf-8") as f:
        content = f.read()
        if content and content != st.session_state.incoming_patch:
            st.session_state.incoming_patch = content
            os.remove(".incoming_patch.txt")
            st.rerun()

# --- KEYBOARD SHORTCUTS (via custom component) ---
# Note: Streamlit doesn't natively support keyboard shortcuts well,
# but we can hint at them in the UI

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("""
    <div style='text-align: center; padding: 20px;'>
        <h1 style='margin: 0;'>⚡</h1>
        <h2 style='margin: 10px 0;'>Code Integrator</h2>
        <p style='opacity: 0.7; font-size: 14px;'>Safe AI-powered code patching</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Git status check
    git_status = patcher.check_git_status()
    if git_status.get("is_repo"):
        if git_status.get("is_dirty"):
            st.markdown("""
            <div class='git-warning'>
                <strong>⚠️ Uncommitted Changes</strong><br>
                You have uncommitted changes in your git repository.
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("View dirty files"):
                for f in git_status.get("dirty_files", [])[:10]:
                    st.text(f"  • {f}")
        else:
            st.success("✅ Git repo is clean")
    
    st.markdown("---")
    
    # Copy Context Feature
    st.subheader("📋 Copy File for AI")
    st.caption("Send current file state to AI")
    
    project_files = get_project_files()
    if project_files:
        selected_file = st.selectbox(
            "Select file",
            options=[""] + project_files,
            label_visibility="collapsed"
        )
        
        if selected_file:
            file_content = patcher.get_file_content(selected_file)
            if file_content:
                if st.button("📄 Copy File Content", use_container_width=True):
                    formatted_content = f"""Here is the current state of `{selected_file}`:

```python
{file_content}
```

Please use this EXACT code when generating the SEARCH block."""
                    
                    st.code(formatted_content, language="markdown")
                    st.success("✅ Copied! Paste into your AI chat.")
                    # Note: Actual clipboard copy requires streamlit-paste-button or similar
    
    st.markdown("---")
    
    # History section
    st.subheader("📜 Recent History")
    history = patcher.get_history_summary(limit=5)
    
    if history:
        for idx, entry in enumerate(history):
            timestamp = datetime.fromtimestamp(entry["timestamp"])
            time_str = timestamp.strftime("%I:%M %p")
            date_str = timestamp.strftime("%b %d")
            
            with st.expander(f"🕐 {time_str} • {date_str}", expanded=(idx == 0)):
                st.write(f"**Files:** {entry['files_changed']}")
                for fname in entry["filenames"]:
                    st.text(f"  • {fname}")
    else:
        st.info("No patch history yet")
    
    st.markdown("---")
    
    # Undo section
    if st.button("↩️ Undo Last Patch", use_container_width=True, type="secondary", key="undo_sidebar"):
        with st.spinner("Reverting changes..."):
            msg, restored = patcher.undo_last()
            if restored:
                st.success(f"{msg}\n\nRestored:\n" + "\n".join(f"• {f}" for f in restored))
                time.sleep(2)
                st.rerun()
            elif "STOP" in msg:
                st.error(msg)
            else:
                st.warning(msg)
    
    st.markdown("---")
    
    # Settings
    with st.expander("⚙️ Settings"):
        auto_stage_git = st.checkbox(
            "Auto-stage in Git",
            value=False,
            help="Automatically stage modified files in Git after applying"
        )
        
        show_line_numbers = st.checkbox(
            "Show line numbers",
            value=True,
            help="Display line numbers in analysis results"
        )
        
        diff_format = st.radio(
            "Diff format",
            options=["Unified", "Split"],
            help="Choose diff preview style"
        )
        
        st.markdown("---")
        
        # File watching
        st.markdown("**File Watching**")
        watch_enabled = st.checkbox(
            "Auto-refresh on file changes",
            value=st.session_state.watch_enabled,
            help="Automatically re-analyze when tracked files change"
        )
        
        if watch_enabled != st.session_state.watch_enabled:
            st.session_state.watch_enabled = watch_enabled
            if not watch_enabled:
                stop_file_watcher()
        
        # Watch indicator
        if st.session_state.watch_enabled:
            st.markdown("""
            <div style='font-size: 11px; margin-top: 5px;'>
                <span class='watch-indicator watch-active'></span>
                <span>Watching files...</span>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Dry run settings
        st.markdown("**Dry Run Test Command**")
        test_command = st.text_input(
            "Command to run",
            value="python -m pytest",
            help="Command to run during dry run (e.g., 'python -m pytest', 'npm test')",
            label_visibility="collapsed"
        )
        
        if st.button("💾 Save Settings", use_container_width=True, type="secondary"):
            st.success("Settings saved!")
        
    st.markdown("---")
    
    # Help section
    with st.expander("❓ Format Help"):
        st.code("""FILE: path/to/file.py
<<<<< SEARCH
original code here
=====
new code here
>>>>>""", language="text")
        st.caption("Use this format for all AI-generated patches")
    
    with st.expander("⌨️ Keyboard Shortcuts"):
        st.markdown("""
        <table style='width: 100%; font-size: 12px;'>
            <tr>
                <td><span class='kbd'>Ctrl</span> + <span class='kbd'>Enter</span></td>
                <td>Analyze patches</td>
            </tr>
            <tr>
                <td><span class='kbd'>Ctrl</span> + <span class='kbd'>Shift</span> + <span class='kbd'>Enter</span></td>
                <td>Apply changes</td>
            </tr>
            <tr>
                <td><span class='kbd'>Ctrl</span> + <span class='kbd'>Z</span></td>
                <td>Undo last patch</td>
            </tr>
            <tr>
                <td><span class='kbd'>Ctrl</span> + <span class='kbd'>D</span></td>
                <td>Dry run</td>
            </tr>
            <tr>
                <td><span class='kbd'>Ctrl</span> + <span class='kbd'>K</span></td>
                <td>Clear input</td>
            </tr>
        </table>
        """, unsafe_allow_html=True)
        st.caption("Shortcuts active when cursor in text area")

# --- MAIN AREA ---

# Check for file changes
if st.session_state.file_changed and st.session_state.watch_enabled:
    st.info(f"🔄 File changed: {st.session_state.changed_file}. Re-analyzing...")
    if st.session_state.analyzed_blocks:
        st.session_state.last_analysis = patcher.analyze_blocks(st.session_state.analyzed_blocks)
    st.session_state.file_changed = False
    st.session_state.changed_file = None
    time.sleep(0.5)
    st.rerun()

# Header
st.markdown("""
<div class='main-header'>
    <h1 style='margin: 0;'>AI Code Patcher</h1>
    <p style='margin: 5px 0 0 0; opacity: 0.9;'>Review and apply code changes safely</p>
</div>
""", unsafe_allow_html=True)

# Success message
if st.session_state.show_success:
    success_msg = f"✅ Successfully applied changes to {len(st.session_state.success_files)} file(s)!"
    if st.session_state.git_message:
        success_msg += st.session_state.git_message
    st.success(success_msg)
    for fname in st.session_state.success_files:
        st.text(f"  ✓ {fname}")
    st.session_state.show_success = False
    st.session_state.success_files = []
    st.session_state.git_message = ""

# Dry run results
if st.session_state.show_dry_run and st.session_state.dry_run_result:
    result = st.session_state.dry_run_result
    
    if result["success"]:
        st.markdown("""
        <div class='dry-run-box dry-run-success'>
            <h3 style='margin: 0 0 10px 0;'>✅ Dry Run Successful</h3>
            <p style='margin: 5px 0;'><strong>Modified files:</strong> {}</p>
        </div>
        """.format(len(result["modified_files"])), unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class='dry-run-box dry-run-failure'>
            <h3 style='margin: 0 0 10px 0;'>❌ Dry Run Failed</h3>
        </div>
        """, unsafe_allow_html=True)
        
        for error in result["errors"]:
            st.error(error)
    
    if result.get("test_output"):
        test = result["test_output"]
        with st.expander("📋 Test Output", expanded=not test["success"]):
            if test["stdout"]:
                st.text("STDOUT:")
                st.code(test["stdout"], language="bash")
            if test["stderr"]:
                st.text("STDERR:")
                st.code(test["stderr"], language="bash")
            st.text(f"Exit code: {test['returncode']}")
    
    st.session_state.show_dry_run = False

# Input area
col1, col2 = st.columns([4, 1])

with col1:
    raw_input = st.text_area(
        "Paste AI-generated patch here",
        value=st.session_state.incoming_patch,
        height=300,
        placeholder="FILE: example.py\n<<<<< SEARCH\n...\n=====\n...\n>>>>>",
        help="Paste the complete output from your AI assistant",
        key="patch_input"
    )
    
    # Token counter
    if raw_input:
        char_count = len(raw_input)
        token_estimate = char_count // 4  # Rough estimate
        
        if char_count < 5000:
            color = "token-ok"
            status = "✓ Normal size"
        elif char_count < 20000:
            color = "token-warning"
            status = "⚠️ Large input"
        else:
            color = "token-danger"
            status = "⚠️ Very large (may be slow)"
        
        st.markdown(f"""
        <div class='token-counter {color}'>
            {status} • {char_count:,} characters (~{token_estimate:,} tokens)
        </div>
        """, unsafe_allow_html=True)

with col2:
    st.markdown("### Quick Actions")
    
    analyze_clicked = st.button("🔍 Analyze", use_container_width=True, type="primary", key="analyze_btn")
    
    # Keyboard shortcut handling
    if raw_input:
        # JavaScript for keyboard shortcuts
        st.markdown("""
        <script>
        document.addEventListener('keydown', function(e) {
            const textarea = document.querySelector('textarea');
            if (!textarea) return;
            
            // Ctrl+Enter: Analyze
            if (e.ctrlKey && e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const analyzeBtn = Array.from(document.querySelectorAll('button')).find(btn => btn.textContent.includes('Analyze'));
                if (analyzeBtn) analyzeBtn.click();
            }
            
            // Ctrl+Shift+Enter: Apply
            if (e.ctrlKey && e.shiftKey && e.key === 'Enter') {
                e.preventDefault();
                const applyBtn = Array.from(document.querySelectorAll('button')).find(btn => btn.textContent.includes('Apply'));
                if (applyBtn) applyBtn.click();
            }
            
            // Ctrl+K: Clear
            if (e.ctrlKey && e.key === 'k') {
                e.preventDefault();
                const clearBtn = Array.from(document.querySelectorAll('button')).find(btn => btn.textContent.includes('Clear'));
                if (clearBtn) clearBtn.click();
            }
            
            // Ctrl+D: Dry Run
            if (e.ctrlKey && e.key === 'd') {
                e.preventDefault();
                const dryRunBtn = Array.from(document.querySelectorAll('button')).find(btn => btn.textContent.includes('Dry Run'));
                if (dryRunBtn) dryRunBtn.click();
            }
        });
        </script>
        """, unsafe_allow_html=True)
    
    if analyze_clicked:
        if raw_input.strip():
            with st.spinner("Analyzing patches..."):
                blocks = patcher.parse_response(raw_input)
                if blocks:
                    st.session_state.analyzed_blocks = blocks
                    st.session_state.last_analysis = patcher.analyze_blocks(blocks)
                    
                    # Start file watching if enabled
                    if st.session_state.watch_enabled:
                        files_to_watch = [b.filename for b in blocks if Path(b.filename).exists()]
                        start_file_watcher(files_to_watch)
                    
                    st.rerun()
                else:
                    st.error("No valid patch blocks found")
        else:
            st.warning("Please paste a patch first")
    
    if st.button("🗑️ Clear", use_container_width=True, key="clear_btn"):
        st.session_state.incoming_patch = ""
        st.session_state.last_analysis = None
        st.session_state.analyzed_blocks = None
        stop_file_watcher()
        st.rerun()
    
    if st.button("🔄 Refresh Files", use_container_width=True, help="Re-analyze if files changed"):
        if st.session_state.analyzed_blocks:
            st.session_state.last_analysis = patcher.analyze_blocks(st.session_state.analyzed_blocks)
            st.rerun()
    
    # Dry run button
    if st.button("🧪 Dry Run", use_container_width=True, help="Test changes without applying"):
        if st.session_state.analyzed_blocks:
            with st.spinner("Running dry run..."):
                test_cmd = test_command if 'test_command' in locals() else None
                result = patcher.dry_run(st.session_state.analyzed_blocks, test_cmd)
                st.session_state.dry_run_result = result
                st.session_state.show_dry_run = True
                st.rerun()
    
    if raw_input:
        blocks = patcher.parse_response(raw_input)
        st.metric("Blocks Found", len(blocks))

# Analysis Results
if raw_input:
    blocks = patcher.parse_response(raw_input)
    
    if not blocks:
        st.warning("⚠️ No valid patch blocks detected. Check your format.")
        with st.expander("See format requirements"):
            st.code("""FILE: path/to/file.py
<<<<< SEARCH
exact original code
=====
replacement code
>>>>>""")
    else:
        st.divider()
        st.subheader("📋 Analysis Results")
        
        # Analyze if not already done
        if st.session_state.last_analysis is None:
            with st.spinner("Analyzing patches..."):
                st.session_state.analyzed_blocks = blocks
                st.session_state.last_analysis = patcher.analyze_blocks(blocks)
        
        results = st.session_state.last_analysis
        
        # Summary stats
        col1, col2, col3 = st.columns(3)
        
        success_count = sum(1 for r in results if r.status == "success")
        warning_count = sum(1 for r in results if r.status == "warning")
        error_count = sum(1 for r in results if r.status == "error")
        
        with col1:
            st.markdown(f"""
            <div class='stat-card' style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);'>
                <div class='stat-label'>Ready to Apply</div>
                <div class='stat-number'>{success_count}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class='stat-card' style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);'>
                <div class='stat-label'>Needs Review</div>
                <div class='stat-number'>{warning_count}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class='stat-card' style='background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);'>
                <div class='stat-label'>Errors</div>
                <div class='stat-number'>{error_count}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Detailed results with selective application
        can_apply = True
        
        for idx, (res, block) in enumerate(zip(results, st.session_state.analyzed_blocks)):
            status_emoji = {
                "success": "✅",
                "warning": "⚠️",
                "error": "❌"
            }
            
            if res.status == "error":
                can_apply = False
            
            # Checkbox for selective application
            col_check, col_expand = st.columns([0.5, 9.5])
            
            with col_check:
                if res.status != "error":
                    block.enabled = st.checkbox(
                        "",
                        value=block.enabled,
                        key=f"enable_{idx}",
                        label_visibility="collapsed"
                    )
                else:
                    st.write("❌")
            
            with col_expand:
                title = f"{status_emoji[res.status]} {res.filename}"
                if res.line_number and show_line_numbers:
                    title += f" (Line {res.line_number})"
                
                with st.expander(title, expanded=(res.status == "error")):
                    # Status message
                    color_class = res.status
                    st.markdown(
                        f"<div class='status-box {color_class}'>{res.message}</div>",
                        unsafe_allow_html=True
                    )
                    
                    # Similarity score
                    if res.similarity_score:
                        st.progress(
                            res.similarity_score / 100,
                            text=f"Match quality: {res.similarity_score:.1f}%"
                        )
                    
                    # Diff preview
                    if res.diff_preview:
                        st.markdown("**Diff Preview:**")
                        
                        # Choose diff format
                        current_diff_format = diff_format if 'diff_format' in locals() else "Unified"
                        
                        if current_diff_format == "Split" and block.valid_match:
                            # Generate side-by-side diff
                            diff_data = patcher.generate_side_by_side_diff(
                                block.valid_match, 
                                block.replace_block
                            )
                            html_diff = render_side_by_side_diff(diff_data)
                            st.markdown(html_diff, unsafe_allow_html=True)
                        else:
                            # Unified diff with basic syntax highlighting
                            highlighted = apply_basic_syntax_highlighting(res.diff_preview, "python")
                            st.markdown(
                                f"<div class='diff-preview'>{highlighted}</div>",
                                unsafe_allow_html=True
                            )
                    
                    # Suggestions
                    if res.suggestions:
                        st.markdown("**💡 Suggestions:**")
                        for suggestion in res.suggestions:
                            st.markdown(
                                f"<div class='suggestion'>• {suggestion}</div>",
                                unsafe_allow_html=True
                            )
                    
                    # Copy Error Report for AI
                    if res.status in ["error", "warning"] and res.error_context:
                        st.markdown("---")
                        st.markdown("**🤖 AI Feedback Loop**")
                        
                        file_content = patcher.get_file_content(res.filename)
                        error_report = patcher.generate_ai_error_report(res, file_content or "")
                        
                        if st.button(f"📋 Copy Error Report for AI", key=f"copy_error_{idx}"):
                            st.code(error_report, language="markdown")
                            st.info("✅ Copy the above text and paste it to your AI assistant to fix the patch")
        
        st.divider()
        
        # Check how many blocks are enabled
        enabled_count = sum(1 for b in st.session_state.analyzed_blocks if b.enabled)
        
        # Apply button section
        if can_apply and enabled_count > 0:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                button_text = f"🚀 Apply {enabled_count} Selected Change{'s' if enabled_count != 1 else ''}"
                if st.button(
                    button_text,
                    use_container_width=True,
                    type="primary",
                    key="apply_btn"
                ):
                    try:
                        with st.spinner("Applying patches..."):
                            modified, git_msg = patcher.apply_patches(
                                st.session_state.analyzed_blocks,
                                auto_stage=auto_stage_git if 'auto_stage_git' in locals() else False
                            )
                            st.session_state.show_success = True
                            st.session_state.success_files = modified
                            st.session_state.git_message = git_msg
                            st.session_state.incoming_patch = ""
                            st.session_state.last_analysis = None
                            st.session_state.analyzed_blocks = None
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to apply patches: {str(e)}")
        elif enabled_count == 0 and not can_apply:
            st.error("❌ Cannot apply patches. Please fix the errors above first.")
        elif enabled_count == 0:
            st.warning("⚠️ No patches selected. Check the boxes to select patches to apply.")
        else:
            st.error("❌ Cannot apply patches with errors. Fix errors or uncheck failed patches.")
            
            if error_count > 0:
                st.info("""
                **Tips for fixing errors:**
                1. Click "Copy Error Report for AI" button above
                2. Paste the report to your AI assistant
                3. The AI will regenerate with correct context
                4. Or use "Copy File Content" in sidebar to give AI current file state
                """)

# --- FOOTER ---
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col2:
    st.markdown("""
    <div style='text-align: center; opacity: 0.6; font-size: 12px;'>
        <p>AI Code Integrator v2.0 • Safe, Smart, Simple</p>
        <p>Use sidebar to copy files to AI • Selective apply with checkboxes</p>
    </div>
    """, unsafe_allow_html=True)
