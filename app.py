import streamlit as st
import threading
import os
import time
import glob
from datetime import datetime
from flask import Flask, request
from flask_cors import CORS
from patcher_core import Patcher

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

# --- HELPER FUNCTIONS ---
def copy_to_clipboard_js(text: str) -> str:
    """Generate JavaScript to copy text to clipboard."""
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
        st.text("Ctrl+Enter: Analyze")
        st.text("Ctrl+Shift+Enter: Apply")
        st.text("Ctrl+Z: Undo")
        st.caption("(Coming soon)")

# --- MAIN AREA ---

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
    
    if st.button("🔍 Analyze", use_container_width=True, type="primary", key="analyze_btn"):
        if raw_input.strip():
            with st.spinner("Analyzing patches..."):
                blocks = patcher.parse_response(raw_input)
                if blocks:
                    st.session_state.analyzed_blocks = blocks
                    st.session_state.last_analysis = patcher.analyze_blocks(blocks)
                    st.rerun()
                else:
                    st.error("No valid patch blocks found")
        else:
            st.warning("Please paste a patch first")
    
    if st.button("🗑️ Clear", use_container_width=True, key="clear_btn"):
        st.session_state.incoming_patch = ""
        st.session_state.last_analysis = None
        st.session_state.analyzed_blocks = None
        st.rerun()
    
    if st.button("🔄 Refresh Files", use_container_width=True, help="Re-analyze if files changed"):
        if st.session_state.analyzed_blocks:
            st.session_state.last_analysis = patcher.analyze_blocks(st.session_state.analyzed_blocks)
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
                        st.markdown(
                            f"<div class='diff-preview'>{res.diff_preview}</div>",
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

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col2:
    st.markdown("""
    <div style='text-align: center; opacity: 0.6; font-size: 12px;'>
        <p>AI Code Integrator v2.0 • Safe, Smart, Simple</p>
        <p>Use sidebar to copy files to AI • Selective apply with checkboxes</p>
    </div>
    """, unsafe_allow_html=True)