## Terminal flash line effect

This pattern rapidly swaps a list of words or phrases on a single terminal line (no wrapping) so it looks like the output is flashing from start to finish.

### Core mechanics
- Render a fixed-width line: wrap the text node in a container that uses monospace fonts and `white-space: pre` to prevent reflow.
- Prevent ghost characters: either clear the text node before each write or pre-pad shorter strings to the length of the longest one.
- Keep updates cheap: write with `textContent` only; do not touch the DOM structure while flashing.
- Cursor realism: keep the cursor in a sibling `<span>` so its blink animation is not reset when the text changes.

### Example snippet
```html
<div class="terminal">
  <span class="line-wrap"><span id="line"></span><span class="cursor">█</span></span>
</div>
<script>
const words = ["Initializing...", "Connecting to host", "Fetching data", "Done"];
const line = document.getElementById("line");
const delayMs = 90;
const max = Math.max(...words.map(word => word.length));
const pad = word => word.padEnd(max, " ");

let i = 0;
const flash = () => {
  line.textContent = pad(words[i]);
  i += 1;
  if (i < words.length) {
    setTimeout(flash, delayMs);
  }
};

setTimeout(flash, delayMs);
</script>
<style>
.terminal {
  font: 16px/1.4 "Fira Code", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: #0b0c10;
  color: #c5c8c6;
  padding: 12px 16px;
}
.line-wrap { white-space: pre; display: inline-flex; align-items: center; }
.cursor { margin-left: 2px; animation: blink 1s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }
</style>
```

### Implementation tips
- If you do not pre-pad strings, clear the text node (`line.textContent = ""`) before writing the next word so shorter words do not leave trailing characters.
- For a tighter feel, replace `setTimeout` with `requestAnimationFrame` to sync with the display’s refresh rate.
- To loop the sequence, reset `i = 0` after the last item and keep the timer running.
