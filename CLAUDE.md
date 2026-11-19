# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Windows-only PySide6 desktop app that watches a YouTube LIVE and flags PlayStation Store voucher codes (12 alphanumeric chars, formatted `XXXX-XXXX-XXXX`). It attaches to one Chrome tab via Playwright/CDP, takes screenshots of that tab (OCR) and captures that tab's audio (Whisper transcription), regex-extracts code candidates, and lets the user send one to the PlayStation redeem page, where Playwright types it into the code field. It never clicks the final redeem button and never validates codes: the human confirms. UI strings, comments, and the README are in Spanish; keep that convention for user-facing text.

## Commands

- Environment: Windows 11, Python 3.14 x64 (`.venv` is already created on 3.14.7; `install.bat` uses `py -3.14`). The `install.bat` error message still says 3.12; ignore that.
- Install: `install.bat` (creates `.venv`, upgrades pip, `pip install -r requirements.txt`). Dependencies are already installed in `.venv` and all have 3.14 wheels.
- OCR uses the `rapidocr` package (3.x) plus `onnxruntime`, not the old `rapidocr_onnxruntime`, which stops at Python 3.12. The 3.x API is `engine(img).txts` (a tuple of strings, or `None` when no text is found), not `result, _ = engine(img)`.
- GPU Whisper needs the CUDA 12 runtime DLLs (`cublas64_12.dll`, cuDNN 9) that `ctranslate2` loads lazily with `LoadLibrary`. They come from the pip packages `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` (in `requirements.txt`), and `SpeechWorker._register_nvidia_dlls()` adds their `site-packages\nvidia\*\bin` folders to `PATH`. A missing DLL fails at transcribe time, not at model creation, so `SpeechWorker` also falls back to CPU if `transcribe` raises. When testing Whisper, use real speech (Windows SAPI can synthesize a wav): VAD discards pure tones before the model, so they don't exercise CUDA.
- Run: `run.bat`, or `.venv\Scripts\activate` then `python main.py`
- There is no test suite, linter, build step, or git repo. Verify changes by running the app (or importing modules and calling `extract_codes` directly for the pure logic in `processing/`).

## Architecture

Entry point `main.py` creates a `QApplication` and `app.dashboard.Dashboard`. The pipeline is a set of `QThread` workers wired together with Qt signals inside `Dashboard.start_monitoring`:

```
TabWorker --audio_chunk--> SpeechWorker --transcript--\
          \--frame-------> OCRWorker    --text_found----+--> Dashboard.handle_text --> extract_codes --> CodeRegistry.add --> bus.code --> table
(fallback: AudioWorker --audio_chunk--> SpeechWorker, system loopback audio)
Dashboard "Canjear" --> RedeemWorker (own thread, own Playwright connection)
```

- `browser/chrome.py` launches Chrome with `--remote-debugging-port=9222` and its own profile `chrome-profile/` (Chrome >= 136 ignores the debug port on the default profile; the user logs in to YouTube/PlayStation once in this profile), and lists tabs via `http://127.0.0.1:9222/json/list`. The tab picked in the UI is identified by CDP `targetId`.
- `browser/tab_worker.py` (`TabWorker`) connects with `connect_over_cdp`, finds the page by `targetId`, and loops: `page.screenshot` every N seconds -> RGB frame, plus `page.wait_for_timeout(100)` to pump Playwright events. Audio comes from `browser/tab_audio.js`, injected into the page: it taps the `<video>` with `captureStream()`, sends ~5 s Int16 mono chunks through an exposed binding (`__psnAudioSend`), and the worker resamples them to 16 kHz float32. Playwright's sync API is bound to the thread that created it, so everything for one connection must stay in one `QThread`; that is why redeem has its own worker instead of sharing `TabWorker`.
- `Dashboard.start_monitoring` builds only the workers the "Detectar con" mode needs (audio + OCR / solo audio / solo OCR): `TabWorker` exists only if OCR is on or tab audio is used (`capture_frames` / `capture_audio` flags), `SpeechWorker` only with audio, `OCRWorker` only with OCR. Every text from `handle_text` goes to the on-screen feed (`add_transcript`, which skips consecutive identical text per source because OCR repeats itself); "Limpiar códigos" empties the table but deliberately keeps `CodeRegistry`, otherwise OCR would re-add the code still on screen within seconds; "Limpiar feed" also resets `_last_feed`. Each new code is added to the table, made the current row and selected so "Copiar seleccionado" works immediately.
- `capture/audio_capture.py` (`AudioWorker`) is the fallback: 5 s chunks of 16 kHz mono from the *default output device* via `soundcard` loopback (the "Audio solo de la pestaña" checkbox off). `capture/screen_capture.py` (full-monitor `mss` grab) is no longer used by anything.
- `recognition/` consumes it. `SpeechWorker` runs `faster-whisper` ("small" model, tries CUDA float16 and falls back to CPU int8). `OCRWorker` runs `rapidocr`. Both read from small bounded `queue.Queue`s and drop data when full, so a slow consumer loses frames or audio instead of building a backlog.
- `processing/code_extractor.py` holds the detection heuristic. `TOKEN` matches only consecutive codes: 12 alphanumerics glued together or 3 groups of 4 joined by literal dashes (never spaces/newlines, so neighbouring words don't merge into a fake code). A candidate needs at least one digit. For `"Audio"` sources it also runs `normalize_spoken`, which maps spoken digit words to digits, and gives that path a lower confidence (0.78). OCR gets 0.95 and plain audio 0.90. Confidence is decided by substring checks on the `source` string (`"OCR"`, `"Audio"`), so the source labels emitted by workers (`"Pantalla (OCR)"`, `"Audio"`) are load-bearing.
- `processing/deduplication.py` (`CodeRegistry`) dedupes on the code with dashes stripped, case-insensitive. The registry is recreated on each Start.
- `redemption/redeem_assistant.py` (`RedeemWorker`) opens a new tab on `https://store.playstation.com/redeem` (redirects to the user's region and opens the redeem dialog) in the CDP Chrome's default context, polls up to 5 min for a visible code `<input>` (matched by placeholder/aria-label/name/id containing "code"/"código"), and `fill`s the code without dashes. It must never click anything. The field selectors are generic guesses: they have only been tested against a fake page, not the real PlayStation page behind login, so adjust `_FIELD_SELECTORS` if the real field isn't found.

Workers share a convention: a `threading.Event` stop flag, a `stop()` method, and a top-level `try/except` in `run()` that prints the error and exits the thread. `TabWorker` and `RedeemWorker` also have a `status` signal that the dashboard shows in the status label. Heavy imports (`soundcard`, `cv2`, `faster_whisper`, `rapidocr`, `playwright`) are done lazily inside `run()`.

## Known issues

- The `install.bat` error message still says Python 3.12, but the project targets 3.14 (the README was updated for v2).
- The `bus` parameter on the worker constructors is accepted but unused.
- Playwright screenshots of a minimized or fully hidden Chrome window can fail; the tab must be visible. Per-tab audio and the redeem selectors are verified only against local test pages, not a real YouTube LIVE or the real PlayStation Store.
- `capture/screen_capture.py` and the `mss` dependency are dead code from V1 (deletion was not permitted in-session).
- To test the browser side without touching the real Chrome, launch `chrome.exe --headless=new --remote-debugging-port=9222 --user-data-dir=<temp>` with a local HTML page (a `<video>` fed by a canvas + oscillator `MediaStream` works for the audio tap) and drive `TabWorker` / `RedeemWorker` under a `QCoreApplication`.
