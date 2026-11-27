# Ask a question

Ask is Dime's core surface: a user types a question into the composer, watches the agent work (thinking status, tool chips, streaming text), and receives a final answer with artifacts and evidence. It can also be halted mid-run.

## Sub-features

- `chat-empty` shows the empty state with headline, composer, and suggested prompts.
- `chat-suggest` fills the composer from a suggested prompt row.
- `chat-stream` shows thinking status, tool chips, and streaming text during a run.
- `chat-answer` lands a final answer with artifacts and a copy action.
- `chat-halt` stops a live run and shows the stopped state.
- `chat-replay` exercises the full streaming render path provider-free.
- `chat-history` persists completed runs in the thread after reload.

## How to get to it (user POV)

- Open `/?tab=chat` (the default landing view).
- Pick a suggested prompt on the empty state, or type in the composer and press Enter.
- Open `/?tab=chat&replay=generative` for the development replay fixture.

## Driving it with dime-drive

Preconditions:

- Doctor passes; host and frontend owned by this checkout.
- For live proofs: a provider key configured and the lane named in the report. For layout proofs: replay fixture only.

- **Empty state.** `node helpers/dime-drive.cjs shot --url "http://localhost:3010/?tab=chat" --out artifacts/verify/ask-chat/$RUN/empty.png --wait-text "What are we looking into?"` — the composer and `.suggestion-row` buttons render.
- **Replay stream.** Steps script: navigate `/?tab=chat&replay=generative`; `{wait-text: "Development replay"}` (fixture banner present); `{wait-for: "article.assistant-turn"}`; `{wait-text: "Shai"}`; interleave `{shot}` mid-stream and after completion. The replay auto-submits its prompt — no composer interaction needed. Proof: artifacts render inline inside the assistant turn.
- **Composer fill.** On the empty state: `{click: ".suggestion-row"}` fills the composer with that prompt text — assert with a shot before sending (do not send live unless doing a live proof).
- **Halt (live only).** Submit a long question, `{wait-for: "article.assistant-turn"}`, click the stop control in the composer dock, `{assert-text: "Stopped"}`. The stream goes quiescent — no further text growth.
- **Stream contract (live, no browser).** `curl -N -X POST localhost:9910/api/v2/chat/stream -H 'content-type: application/json' -d '{"question":"...","thread":"verify-...","model":"<lane>"}'` — the first frame must be a `status` event ("Reading the question") ahead of any token frames; `tool_call` frames carry tool names. Save the transcript as evidence. This is the exact endpoint the UI consumes.
- **History.** After a completed run, reload `/?tab=chat` in a fresh browser context: the prior user turn and answer render from thread history.

## Gotchas

- The replay banner must be visible in replay proofs — a replay-looking proof without the banner is indistinguishable from a live claim.
- Live runs cost provider quota and can take minutes; never use them for layout-only assertions.
- The model picker shows "Unavailable" for lanes without keys — an unavailable model silently blocks submission; check `chat.model` state via the UI before blaming the stream.
- The first visible frame latency is dominated by model thinking time (tens of seconds on some lanes); the `status` frame should still precede tokens — assert ordering, not wall-clock.
- `thread` params must match `^[A-Za-z0-9_-]{1,80}$` or the shell falls back.
