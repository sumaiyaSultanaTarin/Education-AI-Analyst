# AgenticAI Project — Session Context Handoff

Carried over from the parent course-directory chat, so work can continue from here without losing context.

## Who / what
- User: MSc student. Goal: build an agentic AI project for coursework (university-level, not production-grade).
- Usual workflow: Google Colab. Now moving local setup into this `agenticAI/` folder, under the course directory
  `T:\Gratuate\2nd Sem\Computer Science Applications and Advancements`.

## System check (done 2026-08-14, read-only, no installs yet at that point)
| Component | Spec | Note |
|---|---|---|
| OS | Windows 10 Home, 64-bit | |
| CPU | Intel i5-1335U, 10 cores / 12 threads | solid |
| RAM | ~7.65 GB total | fine for API-based agent work; tight for local LLM inference |
| GPU | Intel UHD (integrated) + NVIDIA MX550, 2GB VRAM | too small for meaningfully running local LLMs |
| Disk C: | 20.5 GB free / 199 GB | tight — avoid installing large packages/venvs here |
| Disk T: | 197 GB free / 276 GB | plenty of room — this project lives here |

### Already installed on the machine
- Python 3.13.1 at `C:\Python313` (pip 24.3.1 present; otherwise a clean interpreter, no project packages yet)
- Git 2.47.1
- VS Code 1.132.0
- Conda: **not** installed

## Decision so far
Agentic AI work will be **API-based** (Claude/OpenAI API calls), not local model hosting — the GPU/RAM ruled out
running open-weight LLMs locally in any useful way. This matches typical MSc coursework scope anyway.

## Planned setup (approved by user, not yet executed as of this handoff)
1. Create a Python **virtual environment** for this project, located under `agenticAI/` on the T: drive (not C:,
   to avoid the low free-space issue there).
2. Core packages: `anthropic` and/or `openai` (API SDKs), `python-dotenv` (API key management), `requests`.
3. Agent framework: `langchain` + `langgraph` (default choice; open to swapping for something lighter, or a
   hand-rolled agent loop, if the user prefers).
4. `jupyter`/`notebook` (or VS Code's Jupyter extension) to replicate the Colab notebook workflow locally.
5. Optionally `langsmith` or similar tracing tool for debugging agent runs / writeup material.

## Setup executed (done 2026-08-14)
This new session started with `agenticAI/` as its actual root (confirmed via `pwd`), so all commands below ran
directly here — no more `cd`-ing needed.

1. **Venv created**: `.venv/` inside `agenticAI/` (on T:, avoiding tight C: drive). Python 3.13.1.
2. **Core packages installed**: `anthropic` 0.122.0, `openai` 3.0.0, `python-dotenv` 1.2.2, `requests` 2.34.2.
3. **Agent framework installed**: `langchain` 1.3.15, `langgraph` 1.2.11.
4. **Jupyter installed**: `notebook` 7.6.2, `jupyterlab` 4.6.3, `ipykernel` 7.3.0.
   - **Gotcha hit**: installing the `jupyter` meta-package (which pulls in `ipywidgets`) failed with a Windows
     long-path `OSError` — one bundled JS asset filename combined with this deeply nested folder path exceeded
     Windows' 260-char limit. Fix: installed `notebook` + `ipykernel` directly instead of the `jupyter` meta-package,
     skipping `ipywidgets` (interactive widget sliders — not needed for basic notebook use). Not running as admin
     in this session, so couldn't flip the `LongPathsEnabled` registry key as an alternative fix.
   - Registered the venv as a Jupyter kernel: `agenticAI` / display name "Python (agenticAI)".
5. **Verified**: all packages import cleanly (checked via `importlib.metadata.version()` since `langgraph` doesn't
   expose `__version__` directly — that's normal, not a bug). `jupyter --version` runs fine.

### If `ipywidgets` is needed later
Either (a) enable Windows long paths (admin PowerShell: `Set-ItemProperty -Path
'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -Value 1`, no reboot needed on
Win10/11), then retry `pip install ipywidgets`, or (b) move/symlink the venv to a shorter path.

## Notes on continuity
Claude Code's live session working directory is fixed to wherever the session was launched (the parent course
folder in this case) — it can't be silently relocated mid-session. This file is the practical workaround: it's a
standing record of context inside `agenticAI/`. If a *new* Claude Code session is later started with
`agenticAI/` as its root, pointing it at this file restores full context. Meanwhile, within the current session,
work is being done using `agenticAI/`-prefixed paths (and `cd`-ing into it for shell commands) so all project
artifacts land in the right place regardless.
