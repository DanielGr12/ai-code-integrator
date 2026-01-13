import os
import re
import json
import shutil
import hashlib
import time
import difflib
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from pathlib import Path

# --- DATA STRUCTURES ---
@dataclass
class PatchBlock:
    filename: str
    search_block: str
    replace_block: str
    valid_match: Optional[str] = None
    line_number: Optional[int] = None
    match_quality: float = 0.0
    enabled: bool = True  # For selective application

@dataclass
class PatchStatus:
    filename: str
    status: str
    message: str
    diff_preview: str = ""
    line_number: Optional[int] = None
    similarity_score: Optional[float] = None
    suggestions: List[str] = field(default_factory=list)
    error_context: Optional[str] = None  # Actual code from file for AI feedback
    file_content_preview: Optional[str] = None  # For copy-to-AI feature

# --- CORE LOGIC ---
class Patcher:
    HISTORY_FILE = ".patch_history.json"
    BACKUP_DIR = ".ai_backups"
    IGNORE_FILE = ".patchignore"
    MAX_HISTORY = 50
    SIMILARITY_THRESHOLD = 80

    def __init__(self):
        self.backup_dir = Path(self.BACKUP_DIR)
        self.backup_dir.mkdir(exist_ok=True)
        self.ignore_patterns = self._load_ignore_patterns()
        self._clean_old_backups()

    def _load_ignore_patterns(self) -> List[str]:
        """Load patterns from .patchignore file."""
        ignore_file = Path(self.IGNORE_FILE)
        if not ignore_file.exists():
            # Create default ignore file
            defaults = [
                "*.lock",
                "*.min.js",
                "*.min.css",
                ".env*",
                "node_modules/**",
                "__pycache__/**",
                "*.pyc",
                ".git/**"
            ]
            ignore_file.write_text("\n".join(defaults))
            return defaults
        
        patterns = []
        for line in ignore_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
        return patterns

    def _is_ignored(self, filepath: str) -> bool:
        """Check if file matches ignore patterns."""
        path = Path(filepath)
        for pattern in self.ignore_patterns:
            if '*' in pattern:
                # Simple glob matching
                pattern_re = pattern.replace('.', r'\.').replace('*', '.*').replace('?', '.')
                if re.match(pattern_re, str(path)):
                    return True
            elif pattern in str(path):
                return True
        return False

    def _clean_old_backups(self, max_age_days: int = 7):
        """Remove backups older than max_age_days."""
        cutoff = time.time() - (max_age_days * 86400)
        for backup in self.backup_dir.glob("*.bak"):
            if backup.stat().st_mtime < cutoff:
                try:
                    backup.unlink()
                except Exception:
                    pass

    def _calculate_hash(self, filepath: str) -> str:
        """Generates SHA256 hash."""
        path = Path(filepath)
        if not path.exists():
            return "EMPTY"
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two strings (0-100)."""
        norm1 = ' '.join(text1.split())
        norm2 = ' '.join(text2.split())
        ratio = difflib.SequenceMatcher(None, norm1, norm2).ratio()
        return ratio * 100

    def _get_context_window(self, content: str, start_line: int, window_size: int = 10) -> str:
        """Extract surrounding lines for error reporting."""
        lines = content.split('\n')
        start = max(0, start_line - window_size // 2)
        end = min(len(lines), start_line + window_size // 2)
        
        context_lines = []
        for i in range(start, end):
            marker = ">>>" if i == start_line else "   "
            context_lines.append(f"{marker} {i+1:4d} | {lines[i]}")
        
        return "\n".join(context_lines)

    def _find_best_match(self, search_text: str, content: str) -> Tuple[Optional[str], Optional[int], float]:
        """Find the best match for search_text in content."""
        lines = content.split('\n')
        search_lines = search_text.split('\n')
        search_len = len(search_lines)
        
        best_match = None
        best_line = None
        best_score = 0.0
        best_matched_text = None
        
        for i in range(len(lines) - search_len + 1):
            window = '\n'.join(lines[i:i + search_len])
            score = self._calculate_similarity(search_text, window)
            
            if score > best_score:
                best_score = score
                best_match = window
                best_line = i + 1
                best_matched_text = window
        
        return best_matched_text, best_line, best_score

    def _generate_flexible_regex(self, search_text: str) -> str:
        """Advanced Regex Generation."""
        search_text = search_text.strip()
        if not search_text:
            return ""
        tokens = re.findall(r"[\w]+|[^\s\w]", search_text)
        escaped_tokens = [re.escape(t) for t in tokens]
        pattern = r"\s*".join(escaped_tokens)
        return pattern

    def _generate_diff_preview(self, original: str, modified: str, format_type: str = "unified") -> str:
        """Generate diff preview in unified or split format."""
        original_lines = original.split('\n')
        modified_lines = modified.split('\n')
        
        if format_type == "unified":
            diff = difflib.unified_diff(
                original_lines,
                modified_lines,
                lineterm='',
                n=3
            )
            return '\n'.join(diff)
        else:  # split
            diff_html = []
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, original_lines, modified_lines).get_opcodes():
                if tag == 'equal':
                    for line in original_lines[i1:i2]:
                        diff_html.append(f"  {line}")
                elif tag == 'delete':
                    for line in original_lines[i1:i2]:
                        diff_html.append(f"- {line}")
                elif tag == 'insert':
                    for line in modified_lines[j1:j2]:
                        diff_html.append(f"+ {line}")
                elif tag == 'replace':
                    for line in original_lines[i1:i2]:
                        diff_html.append(f"- {line}")
                    for line in modified_lines[j1:j2]:
                        diff_html.append(f"+ {line}")
            return '\n'.join(diff_html)

    def generate_ai_error_report(self, status: PatchStatus, file_content: str) -> str:
        """Generate formatted error report for AI to fix the patch."""
        report = [
            "🔴 PATCH ERROR REPORT",
            "=" * 60,
            f"File: {status.filename}",
            f"Status: {status.status.upper()}",
            f"Error: {status.message}",
            ""
        ]
        
        if status.error_context:
            report.extend([
                "Actual code found in file:",
                "```",
                status.error_context,
                "```",
                ""
            ])
        
        if status.suggestions:
            report.extend([
                "Suggestions:",
                *[f"  • {s}" for s in status.suggestions],
                ""
            ])
        
        report.extend([
            "Please regenerate the SEARCH block with:",
            "1. More unique context (function signature, comments)",
            "2. Exact indentation from the actual file",
            "3. At least 5-10 lines of surrounding code"
        ])
        
        return "\n".join(report)

    def check_git_status(self) -> Dict[str, any]:
        """Check git repository status."""
        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode != 0:
                return {"is_repo": False}
            
            # Check for uncommitted changes
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            dirty_files = []
            if status_result.stdout:
                for line in status_result.stdout.splitlines():
                    if line.strip():
                        dirty_files.append(line[3:])  # Remove status prefix
            
            return {
                "is_repo": True,
                "is_dirty": len(dirty_files) > 0,
                "dirty_files": dirty_files
            }
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {"is_repo": False}

    def stage_files(self, files: List[str]) -> bool:
        """Stage files in git."""
        try:
            subprocess.run(
                ['git', 'add'] + files,
                capture_output=True,
                timeout=5,
                check=True
            )
            return True
        except Exception:
            return False

    def parse_response(self, text: str) -> List[PatchBlock]:
        """Parse AI response into patch blocks."""
        pattern = re.compile(
            r"FILE:\s*(.*?)\n<<<<< SEARCH\n(.*?)\n=====\n(.*?)\n>>>>>",
            re.DOTALL
        )
        matches = pattern.findall(text)
        
        blocks = []
        for fname, search, replace in matches:
            filename = fname.strip()
            
            if not filename or filename.startswith('/'):
                continue
                
            blocks.append(PatchBlock(
                filename=filename,
                search_block=search,
                replace_block=replace,
                valid_match=None,
                enabled=True
            ))
        
        return blocks

    def analyze_blocks(self, blocks: List[PatchBlock]) -> List[PatchStatus]:
        """Analyze patch blocks with comprehensive validation."""
        results = []
        
        for block in blocks:
            filepath = Path(block.filename)
            
            # Check ignore patterns
            if self._is_ignored(block.filename):
                results.append(PatchStatus(
                    block.filename,
                    "error",
                    "🚫 File is protected by .patchignore",
                    suggestions=["Remove from .patchignore if you want to patch this file"]
                ))
                continue
            
            # File creation case
            if not filepath.exists():
                if block.search_block.strip() == "":
                    if not filepath.parent.exists():
                        results.append(PatchStatus(
                            block.filename,
                            "warning",
                            f"⚠️ Parent directory '{filepath.parent}' will be created.",
                            suggestions=["Ensure the directory path is correct"]
                        ))
                    else:
                        results.append(PatchStatus(
                            block.filename,
                            "success",
                            "✨ New file will be created."
                        ))
                else:
                    results.append(PatchStatus(
                        block.filename,
                        "error",
                        "❌ File not found (SEARCH block must be empty for new files).",
                        suggestions=["Leave SEARCH block empty to create a new file"]
                    ))
                continue

            # File deletion case
            if block.replace_block.strip() == "":
                results.append(PatchStatus(
                    block.filename,
                    "warning",
                    "🗑️ File will be deleted.",
                    suggestions=["Ensure you want to delete this file completely"]
                ))
                continue

            # Read file content
            try:
                content = filepath.read_text(encoding='utf-8')
            except Exception as e:
                results.append(PatchStatus(
                    block.filename,
                    "error",
                    f"❌ Cannot read file: {str(e)}"
                ))
                continue

            # Empty search block for existing file
            if not block.search_block.strip():
                results.append(PatchStatus(
                    block.filename,
                    "error",
                    "❌ SEARCH block is empty for existing file.",
                    suggestions=["Provide context to locate where to insert code"]
                ))
                continue

            # Try exact match first
            if block.search_block in content:
                count = content.count(block.search_block)
                line_num = content[:content.find(block.search_block)].count('\n') + 1
                
                if count == 1:
                    block.valid_match = block.search_block
                    block.line_number = line_num
                    block.match_quality = 100.0
                    
                    diff = self._generate_diff_preview(block.search_block, block.replace_block)
                    
                    results.append(PatchStatus(
                        block.filename,
                        "success",
                        f"✅ Exact match found at line {line_num}.",
                        diff_preview=diff,
                        line_number=line_num,
                        similarity_score=100.0
                    ))
                    continue
                else:
                    # Multiple matches - provide context for AI
                    first_match_pos = content.find(block.search_block)
                    first_match_line = content[:first_match_pos].count('\n')
                    error_context = self._get_context_window(content, first_match_line, 15)
                    
                    results.append(PatchStatus(
                        block.filename,
                        "error",
                        f"⛔ Ambiguous! Found {count} exact matches.",
                        suggestions=[
                            "Add more surrounding context to make the search unique",
                            "Include function/class signatures or unique comments"
                        ],
                        error_context=error_context,
                        file_content_preview=content[:1000]
                    ))
                    continue

            # Try flexible regex matching
            regex_pattern = self._generate_flexible_regex(block.search_block)
            if regex_pattern:
                matches = list(re.finditer(regex_pattern, content, re.DOTALL))
                
                if len(matches) == 1:
                    found_text = matches[0].group(0)
                    line_num = content[:matches[0].start()].count('\n') + 1
                    
                    block.valid_match = found_text
                    block.line_number = line_num
                    block.match_quality = 95.0
                    
                    diff = self._generate_diff_preview(found_text, block.replace_block)
                    
                    results.append(PatchStatus(
                        block.filename,
                        "warning",
                        f"⚠️ Match found at line {line_num} (whitespace differences).",
                        diff_preview=diff,
                        line_number=line_num,
                        similarity_score=95.0,
                        suggestions=["Review the diff carefully for indentation changes"]
                    ))
                    continue
                elif len(matches) > 1:
                    first_match_line = content[:matches[0].start()].count('\n')
                    error_context = self._get_context_window(content, first_match_line, 15)
                    
                    results.append(PatchStatus(
                        block.filename,
                        "error",
                        f"⛔ Found {len(matches)} similar blocks.",
                        suggestions=["Provide more unique context"],
                        error_context=error_context
                    ))
                    continue

            # Try fuzzy matching as last resort
            best_match, line_num, similarity = self._find_best_match(
                block.search_block, content
            )
            
            if similarity >= self.SIMILARITY_THRESHOLD:
                block.valid_match = best_match
                block.line_number = line_num
                block.match_quality = similarity
                
                diff = self._generate_diff_preview(
                    block.search_block,
                    best_match,
                    "unified"
                )
                
                error_context = self._get_context_window(content, line_num - 1, 15)
                
                results.append(PatchStatus(
                    block.filename,
                    "warning",
                    f"⚠️ Fuzzy match at line {line_num} ({similarity:.1f}% similar).",
                    diff_preview=f"--- AI Expected\n+++ File Contains\n{diff}",
                    line_number=line_num,
                    similarity_score=similarity,
                    suggestions=[
                        "Verify the match is correct before applying",
                        "AI may have slightly different version of the code"
                    ],
                    error_context=error_context
                ))
            else:
                # No match found - provide best attempt for AI feedback
                if line_num:
                    error_context = self._get_context_window(content, line_num - 1, 20)
                else:
                    error_context = content[:500]
                
                results.append(PatchStatus(
                    block.filename,
                    "error",
                    f"❌ No match found. Best similarity: {similarity:.1f}%",
                    suggestions=[
                        "Check if the file has been recently modified",
                        "Verify you're editing the correct file",
                        "AI may have hallucinated or used outdated code"
                    ],
                    error_context=error_context,
                    file_content_preview=content
                ))

        return results

    def apply_patches(self, blocks: List[PatchBlock], auto_stage: bool = False) -> Tuple[List[str], str]:
        """Apply patches with optional git staging."""
        timestamp = int(time.time())
        history_entry = {"timestamp": timestamp, "files": [], "description": ""}
        modified_files = []

        # Filter to only enabled blocks
        blocks = [b for b in blocks if b.enabled]

        # Pre-flight validation
        for block in blocks:
            filepath = Path(block.filename)
            if filepath.exists() and not block.valid_match and block.search_block.strip():
                raise Exception(
                    f"Safety halt: {block.filename} has no valid match target."
                )

        # Apply changes
        for block in blocks:
            filepath = Path(block.filename)
            
            if not filepath.exists():
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(block.replace_block, encoding='utf-8')
                
                history_entry["files"].append({
                    "path": block.filename,
                    "action": "create",
                    "backup": None,
                    "post_hash": self._calculate_hash(block.filename)
                })
                modified_files.append(block.filename)
                continue

            if block.replace_block.strip() == "":
                backup_path = self.backup_dir / f"{filepath.name}_{timestamp}.bak"
                shutil.copy(filepath, backup_path)
                filepath.unlink()
                
                history_entry["files"].append({
                    "path": block.filename,
                    "action": "delete",
                    "backup": str(backup_path),
                    "pre_hash": self._calculate_hash(str(backup_path))
                })
                modified_files.append(block.filename)
                continue

            backup_path = self.backup_dir / f"{filepath.name}_{timestamp}.bak"
            shutil.copy(filepath, backup_path)

            content = filepath.read_text(encoding='utf-8')
            
            if block.valid_match:
                new_content = content.replace(block.valid_match, block.replace_block, 1)
                filepath.write_text(new_content, encoding='utf-8')

                history_entry["files"].append({
                    "path": block.filename,
                    "action": "modify",
                    "backup": str(backup_path),
                    "post_hash": self._calculate_hash(block.filename),
                    "line_number": block.line_number
                })
                modified_files.append(block.filename)

        # Git integration
        git_msg = ""
        if auto_stage and modified_files:
            if self.stage_files(modified_files):
                git_msg = f" (Staged {len(modified_files)} files in git)"

        history = self._load_history()
        history.append(history_entry)
        
        if len(history) > self.MAX_HISTORY:
            history = history[-self.MAX_HISTORY:]
        
        self._save_history(history)
        
        return modified_files, git_msg

    def _load_history(self) -> list:
        """Load patch history."""
        history_path = Path(self.HISTORY_FILE)
        if not history_path.exists():
            return []
        try:
            return json.loads(history_path.read_text())
        except Exception:
            return []

    def _save_history(self, history: list):
        """Save patch history."""
        Path(self.HISTORY_FILE).write_text(json.dumps(history, indent=2))

    def undo_last(self) -> Tuple[str, List[str]]:
        """Undo last patch with safety checks."""
        history = self._load_history()
        if not history:
            return "No history to undo.", []

        last_entry = history.pop()
        restored_files = []

        for fentry in last_entry["files"]:
            filepath = Path(fentry["path"])
            
            if fentry["action"] == "modify":
                if not filepath.exists():
                    return f"🛑 File {fentry['path']} no longer exists.", []
                    
                current_hash = self._calculate_hash(fentry["path"])
                if current_hash != fentry["post_hash"]:
                    return (
                        f"🛑 STOP: {fentry['path']} was manually modified since patch. "
                        f"Undoing will overwrite your changes."
                    ), []

        try:
            for fentry in last_entry["files"]:
                filepath = Path(fentry["path"])
                
                if fentry["action"] == "create":
                    if filepath.exists():
                        filepath.unlink()
                        restored_files.append(fentry["path"])
                        
                elif fentry["action"] == "delete":
                    backup_path = Path(fentry["backup"])
                    if backup_path.exists():
                        shutil.copy(backup_path, filepath)
                        restored_files.append(fentry["path"])
                        
                elif fentry["action"] == "modify":
                    backup_path = Path(fentry["backup"])
                    if backup_path.exists():
                        shutil.copy(backup_path, filepath)
                        restored_files.append(fentry["path"])

            self._save_history(history)
            return "✅ Successfully reverted changes.", restored_files
            
        except Exception as e:
            return f"❌ Error during undo: {str(e)}", restored_files

    def get_history_summary(self, limit: int = 10) -> List[dict]:
        """Get summary of recent patches."""
        history = self._load_history()
        recent = history[-limit:] if len(history) > limit else history
        
        summaries = []
        for entry in reversed(recent):
            summaries.append({
                "timestamp": entry["timestamp"],
                "files_changed": len(entry["files"]),
                "actions": [f["action"] for f in entry["files"]],
                "filenames": [f["path"] for f in entry["files"]]
            })
        
        return summaries

    def get_file_content(self, filepath: str, max_chars: int = 50000) -> Optional[str]:
        """Get file content for copying to AI."""
        try:
            path = Path(filepath)
            if not path.exists():
                return None
            content = path.read_text(encoding='utf-8')
            if len(content) > max_chars:
                return content[:max_chars] + f"\n\n... (truncated, {len(content)} total chars)"
            return content
        except Exception:
            return None