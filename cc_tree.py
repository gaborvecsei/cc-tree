import argparse
import json
import os
import sys
from datetime import datetime

TRUNCATE = 60


def load_sessions(project_path):
    sessions = {}
    for fname in os.listdir(project_path):
        if not fname.endswith(".jsonl"):
            continue
        sid = fname[:-6]
        session = {
            "id": sid,
            "title": None,
            "forked_from": None,
            "first_user_msg": None,
            "last_ts": None,
            "msg_count": 0
        }
        with open(os.path.join(project_path, fname)) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = data.get("type")
                if "customTitle" in data:
                    session["title"] = data["customTitle"]
                elif t == "ai-title" and not session["title"]:
                    session["title"] = data.get("aiTitle")
                if t == "user":
                    session["msg_count"] += 1
                    if session["first_user_msg"] is None:
                        content = data.get("message", {}).get("content", "")
                        if isinstance(content, list):
                            content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                        session["first_user_msg"] = content.strip()
                if ts := data.get("timestamp"):
                    session["last_ts"] = ts
                if "forkedFrom" in data and session["forked_from"] is None:
                    forked = data["forkedFrom"]
                    if isinstance(forked, dict):
                        session["forked_from"] = forked.get("sessionId")
        sessions[sid] = session
    return sessions


def fmt_ts(ts):
    if not ts:
        return "unknown"
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M")


def label(session, full_id):
    text = session["title"] or session["first_user_msg"] or session["id"]
    if len(text) > TRUNCATE:
        text = text[:TRUNCATE - 1] + "…"
    sid = session["id"] if full_id else session["id"][:8]
    meta = f"{fmt_ts(session['last_ts'])} · {session['msg_count']} msgs"
    return f"{text} [{meta}] ({sid})"


def print_tree(sid, children, sessions, full_id, prefix="", is_last=True):
    connector = "└── " if is_last else "├── "
    print(prefix + connector + label(sessions[sid], full_id))
    child_prefix = prefix + ("    " if is_last else "│   ")
    kids = children.get(sid, [])
    for i, child in enumerate(kids):
        print_tree(child, children, sessions, full_id, child_prefix, i == len(kids) - 1)


def build_and_print(project_path, full_id):
    sessions = load_sessions(project_path)
    if not sessions:
        return False

    children = {sid: [] for sid in sessions}
    roots = []
    for sid, s in sessions.items():
        parent = s["forked_from"]
        if parent and parent in sessions:
            children[parent].append(sid)
        else:
            roots.append(sid)

    for i, root in enumerate(roots):
        print(label(sessions[root], full_id))
        kids = children.get(root, [])
        for j, child in enumerate(kids):
            print_tree(child, children, sessions, full_id, "", j == len(kids) - 1)
        if i < len(roots) - 1:
            print()

    return True


def main():
    parser = argparse.ArgumentParser(description="Visualize Claude Code session branch trees.")
    parser.add_argument(
        "--claude-dir",
        default=os.path.expanduser("~/.claude/projects"),
        metavar="DIR",
        help="Claude projects directory (default: ~/.claude/projects)",
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        metavar="DIR",
        help="Project directory to inspect (default: current working directory)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show session trees for all projects",
    )
    parser.add_argument(
        "--full-id",
        action="store_true",
        help="Show full session UUIDs instead of the first 8 characters",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.claude_dir):
        print(f"Claude directory not found: {args.claude_dir}")
        sys.exit(1)

    if args.all:
        projects = sorted(os.listdir(args.claude_dir))
        found_any = False
        printed_any = False
        for project in projects:
            project_path = os.path.join(args.claude_dir, project)
            if not os.path.isdir(project_path):
                continue
            has_sessions = any(f.endswith(".jsonl") for f in os.listdir(project_path))
            if not has_sessions:
                continue
            if printed_any:
                print()
            print(f"── {project}")
            if build_and_print(project_path, args.full_id):
                found_any = True
            printed_any = True
        if not found_any:
            print("No Claude Code sessions found.")
    else:
        cwd = args.project_dir or os.getcwd()
        project_name = cwd.replace(os.sep, "-")
        project_path = os.path.join(args.claude_dir, project_name)

        if not os.path.isdir(project_path):
            print("No Claude Code sessions found for this project.")
            sys.exit(0)

        if not build_and_print(project_path, args.full_id):
            print("No Claude Code sessions found for this project.")


if __name__ == "__main__":
    main()
