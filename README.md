# ⚡ AI Code Integrator v2.0

> **Safe, Smart, Simple** — Eliminate the copy-paste integration loop between LLMs and your codebase.

## 🎯 What is This?

AI Code Integrator bridges the gap between AI-generated code suggestions and your actual codebase. Instead of manually hunting down lines to modify, this tool:

1. **Parses** AI-generated patches in a structured format
2. **Validates** changes with fuzzy matching and safety checks
3. **Visualizes** diffs with color-coded previews
4. **Applies** changes atomically with automatic backups
5. **Reverts** changes safely with hash verification

## ✨ Key Features

### 🛡️ Safety First
- **Atomic Transactions**: All-or-nothing application of multi-file changes
- **Automatic Backups**: Every change creates a timestamped backup
- **Hash Verification**: Prevents data loss from stale undos
- **Ambiguity Detection**: Refuses to guess when multiple matches exist

### 🔍 Smart Matching
- **Exact Match**: Fastest path for character-perfect matches
- **Whitespace Flexible**: Handles tab/space differences gracefully
- **Fuzzy Matching**: Finds similar code blocks with confidence scores
- **Context-Aware**: Shows line numbers and surrounding code

### 🎨 Enhanced UX
- **Visual Diffs**: Side-by-side comparison of changes
- **Status Dashboard**: Real-time feedback on patch validity
- **History Tracking**: Browse and undo recent patches
- **Suggestions Engine**: Actionable tips for fixing errors

### 🚀 Developer Experience
- **Browser Extension Support**: Send patches directly from AI chat
- **Batch Operations**: Queue multiple patches (coming soon)
- **Keyboard Shortcuts**: Fast navigation and actions
- **Auto-cleanup**: Old backups are automatically removed

## 📦 Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd ai-code-integrator

# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py
```

The app will open at `http://localhost:8501`

## 🎬 Quick Start

### Step 1: Generate Patches from AI

Ask your AI assistant (Claude, ChatGPT, etc.) to generate patches using this format:

```
FILE: src/utils.py
<<<<< SEARCH
def old_function(x):
    return x * 2
=====
def new_function(x, multiplier=2):
    """Enhanced function with configurable multiplier."""
    return x * multiplier
>>>>>

FILE: tests/test_utils.py
<<<<< SEARCH
def test_old():
    assert old_function(5) == 10
=====
def test_new():
    assert new_function(5) == 10
    assert new_function(5, 3) == 15
>>>>>
```

### Step 2: Paste and Analyze

1. Copy the AI's output
2. Paste into the "Patch Input" area
3. Click **🔍 Analyze**

### Step 3: Review Results

The tool will show you:
- ✅ **Green**: Exact matches ready to apply
- ⚠️ **Yellow**: Fuzzy matches needing review
- ❌ **Red**: Errors that must be fixed

### Step 4: Apply or Fix

- If all checks pass → Click **🚀 Apply All Changes**
- If errors exist → Follow the suggestions to fix them
- Need to revert? → Click **↩️ Undo Last Patch**

## 🧠 How It Works

### The Matching Algorithm

```
1. Exact Match (Fastest)
   └─ Search for character-perfect match
   └─ If unique → ✅ Success

2. Flexible Regex (Smart)
   └─ Normalize whitespace/indentation
   └─ If unique → ⚠️ Warning + Diff

3. Fuzzy Match (Last Resort)
   └─ Calculate similarity scores
   └─ If > 80% → ⚠️ Warning + Review
   └─ If < 80% → ❌ Error + Suggestions
```

### Safety Mechanisms

| Scenario | Protection | Action |
|----------|-----------|---------|
| Ambiguous context | Detects multiple matches | Abort with error |
| Missing file | Validates existence | Create if SEARCH is empty |
| Manual edits | Hash verification | Block unsafe undos |
| Partial failure | Dry-run validation | All-or-nothing apply |
| Whitespace mismatch | Flexible matching | Apply with warning |
| AI hallucination | Similarity threshold | Reject low-confidence matches |

## 🎓 Format Specification

### Creating a New File

```
FILE: new_module.py
<<<<< SEARCH

=====
"""New module documentation."""

def new_function():
    pass
>>>>>
```

Note: Empty SEARCH block signals file creation

### Modifying Existing Code

```
FILE: existing.py
<<<<< SEARCH
# Include enough context to be unique
class OldClass:
    def method(self):
        return "old"
=====
# Your improvements here
class EnhancedClass:
    def method(self):
        """Added documentation."""
        return "new"
>>>>>
```

### Deleting a File

```
FILE: obsolete.py
<<<<< SEARCH
entire file content here
=====

>>>>>
```

Note: Empty REPLACE block signals deletion

## 📊 Understanding the Dashboard

### Status Cards
- **Ready to Apply**: Patches that passed all checks
- **Needs Review**: Fuzzy matches requiring verification
- **Errors**: Issues that must be fixed before applying

### Match Quality Indicators
- **100%**: Exact character match (safest)
- **95-99%**: Whitespace-only differences
- **80-94%**: Fuzzy match (review carefully)
- **< 80%**: Rejected (too uncertain)

### Diff Preview Colors
- `-` Red lines: Code being removed
- `+` Green lines: Code being added
- Gray lines: Unchanged context

## 🔧 Configuration

### Settings (Sidebar)

**Auto-apply on 100% match**
- Automatically apply patches with perfect matches
- Requires no manual review

**Show line numbers**
- Display file locations in analysis
- Helpful for large files

**Diff context lines**
- Control how much surrounding code to show
- Range: 1-10 lines

## 🚨 Troubleshooting

### "No valid patch blocks found"

**Cause**: Format doesn't match the expected structure

**Fix**:
- Ensure `FILE:` line exists
- Verify `<<<<< SEARCH`, `=====`, `>>>>>` markers
- Check for typos in delimiters

### "Ambiguous! Found N matches"

**Cause**: SEARCH block appears multiple times

**Fix**:
- Add more surrounding context
- Include unique identifiers (function names, comments)
- Expand to include parent class/function

### "Context not found"

**Cause**: SEARCH block doesn't exist in file

**Fix**:
- Verify you're editing the correct file
- Check if file was recently modified
- Ask AI to regenerate with current code
- Use fuzzy matching if available

### "File modified manually since patch"

**Cause**: Attempting to undo after manual edits

**Fix**:
- Review your manual changes first
- Commit or stash changes in git
- Use git history instead of tool's undo

## 🎯 Best Practices

### For AI Prompts

1. **Be explicit about context**
   ```
   "Show the SEARCH block including the complete function signature 
   and at least 3 lines before and after"
   ```

2. **Request unique identifiers**
   ```
   "Include the class name and a unique comment in the SEARCH block"
   ```

3. **Verify file paths**
   ```
   "Confirm the file path is relative to project root"
   ```

### For Code Reviews

1. **Always review fuzzy matches** (< 100% confidence)
2. **Check line numbers** for large files
3. **Test after applying** critical changes
4. **Commit frequently** to preserve history

### For Team Usage

1. **Share format specification** with team
2. **Use descriptive commit messages** after applying
3. **Document custom patterns** in SYSTEM_PROMPT.md
4. **Review history regularly** for audit trail

## 🔌 Browser Extension (Optional)

Send patches directly from your AI chat interface:

1. Install the extension (Chrome/Firefox)
2. Configure server URL: `http://localhost:5000`
3. Click "Send to Integrator" in AI chat
4. Patches appear automatically in the tool

## 📈 Advanced Features

### History Management

- **Automatic pruning**: Keeps last 50 patches
- **Backup cleanup**: Removes backups older than 7 days
- **Export history**: JSON format for auditing

### Batch Operations (Coming Soon)

- Queue multiple patch sets
- Dependency resolution
- Conflict detection
- Rollback checkpoints

## 🤝 Contributing

We welcome contributions! Areas for improvement:

- [ ] Git integration (auto-commit)
- [ ] VSCode extension
- [ ] Conflict resolution UI
- [ ] Real-time collaboration
- [ ] Plugin system for custom matchers

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

Built with:
- [Streamlit](https://streamlit.io) - Beautiful UI framework
- [Flask](https://flask.palletsprojects.com) - Extension API server
- Python's `difflib` - Intelligent diff generation

## 📞 Support

- 🐛 **Bug reports**: Open an issue on GitHub
- 💡 **Feature requests**: Start a discussion
- 📖 **Documentation**: Check the wiki
- 💬 **Questions**: Join our Discord server

---

**Made with ❤️ for developers tired of manual code integration**