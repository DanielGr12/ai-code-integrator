import streamlit as st
import threading
import os
import time
from datetime import datetime
from flask import Flask, request
from flask_cors import CORS
from patcher_core import Patcher

# --- FLASK BACKGROUND SERVER (For Chrome Extension) ---
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
    /* Main styling */
    .stTextArea textarea {
        font-family: 'Fira Code', 'Courier New', monospace;
        font-size: 13px;
        line-height: 1.5;
    }
    
    /* Status boxes */
    .status-box {
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid;
    }
    .success {
        background-color: #d4edda;
        color: #155724;
        border-left-color: #28a745;
    }
    .error {
        background-color: #f8d7da;
        color: #721c24;
        border-left-color: #dc3545;
    }
    .warning {
        background-color: #fff3cd;
        color: #856404;
        border-left-color: #ffc107;
    }
    
    /* Diff preview */
    .diff-preview {
        background-color: #f6f8fa;
        border: 1px solid #d0d7de;
        border-radius: 6px;
        padding: 12px;
        font-family: 'Fira Code', monospace;
        font-size: 12px;
        overflow-x: auto;
        white-space: pre;
    }
    
    /* Stats cards */
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 10px 0;
    }
    .stat-number {
        font-size: 32px;
        font-weight: bold;
        margin: 10px 0;
    }
    .stat-label {
        font-size: 14px;
        opacity: 0.9;
    }
    
    /* Suggestions */
    .suggestion {
        background-color: #e7f3ff;
        border-left: 3px solid #2196F3;
        padding: 10px;
        margin: 5px 0;
        border-radius: 4px;
    }
    
    /* Header gradient */
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin-bottom: 20px;
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
    if st.button("↩️ Undo Last Patch", use_container_width=True, type="secondary"):
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
        auto_apply = st.checkbox(
            "Auto-apply on 100% match",
            help="Automatically apply changes when exact matches are found"
        )
        
        show_line_numbers = st.checkbox(
            "Show line numbers",
            value=True,
            help="Display line numbers in analysis results"
        )
        
        context_lines = st.slider(
            "Diff context lines",
            min_value=1,
            max_value=10,
            value=3,
            help="Number of context lines in diff preview"
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
    st.success(f"✅ Successfully applied changes to {len(st.session_state.success_files)} file(s)!")
    for fname in st.session_state.success_files:
        st.text(f"  ✓ {fname}")
    st.session_state.show_success = False
    st.session_state.success_files = []

# Input tabs
tab1, tab2 = st.tabs(["📝 Patch Input", "📊 Batch Operations"])

with tab1:
    col1, col2 = st.columns([3, 1])
    
    with col1:
        raw_input = st.text_area(
            "Paste AI-generated patch here",
            value=st.session_state.incoming_patch,
            height=300,
            placeholder="FILE: example.py\n<<<<< SEARCH\n...\n=====\n...\n>>>>>",
            help="Paste the complete output from your AI assistant"
        )
    
    with col2:
        st.markdown("### Quick Actions")
        
        if st.button("🔍 Analyze", use_container_width=True, type="primary"):
            if raw_input.strip():
                with st.spinner("Analyzing patches..."):
                    blocks = patcher.parse_response(raw_input)
                    if blocks:
                        st.session_state.last_analysis = patcher.analyze_blocks(blocks)
                        st.rerun()
                    else:
                        st.error("No valid patch blocks found")
            else:
                st.warning("Please paste a patch first")
        
        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state.incoming_patch = ""
            st.session_state.last_analysis = None
            st.rerun()
        
        if raw_input:
            blocks = patcher.parse_response(raw_input)
            st.metric("Blocks Found", len(blocks))

with tab2:
    st.info("🚧 Batch operations coming soon!")
    st.write("Features planned:")
    st.write("• Apply multiple patches from different files")
    st.write("• Queue management")
    st.write("• Conflict resolution")

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
        
        # Detailed results
        can_apply = True
        
        for idx, res in enumerate(results):
            status_emoji = {
                "success": "✅",
                "warning": "⚠️",
                "error": "❌"
            }
            
            if res.status == "error":
                can_apply = False
            
            # Expander title with status
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
        
        st.divider()
        
        # Apply button
        if can_apply:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button(
                    "🚀 Apply All Changes",
                    use_container_width=True,
                    type="primary"
                ):
                    try:
                        with st.spinner("Applying patches..."):
                            modified = patcher.apply_patches(blocks)
                            st.session_state.show_success = True
                            st.session_state.success_files = modified
                            st.session_state.incoming_patch = ""
                            st.session_state.last_analysis = None
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to apply patches: {str(e)}")
        else:
            st.error("❌ Cannot apply patches. Please fix the errors above first.")
            
            # Show retry suggestion
            if error_count > 0:
                st.info("""
                **Tips for fixing errors:**
                1. Ask the AI to provide more context in the SEARCH block
                2. Verify you're working with the latest version of the files
                3. Check if the file paths are correct
                """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; opacity: 0.6; font-size: 12px;'>
    <p>AI Code Integrator v2.0 • Safe, Smart, Simple</p>
    <p>Press ⬇️ thumbs down on any result to report issues</p>
</div>
""", unsafe_allow_html=True)