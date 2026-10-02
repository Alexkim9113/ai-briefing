# O-2D Priority 5 -- Responsive regression check for the new "인텔리전스" main-site nav link
# (added in O-2D Priority 1-3, commit 9eb0cae, briefing.py page()). This does not re-run the
# existing N-6 responsive_validation.py suite (which renders report_engine/public_delivery/
# operator_ui sample pages) -- it targets the one page type that suite does not cover: the
# real, already-built main-site page (site/home.html) that carries the nav bar the new link
# was added to.
#
# Method: reuses the exact same headless-Chromium-binary approach and the exact same documented
# 500px-minimum-window-size environment limitation as responsive_validation.py (see that module's
# docstring) -- no playwright/CDP client is installed in this sandbox, so a literal 375px viewport
# cannot be produced here either. Honesty over a forced pass: every result records the ACTUAL
# window.innerWidth achieved, never a claimed-but-unachieved 375.
#
# Measurement technique: `--screenshot` alone gives only a PNG (useful for visual confirmation,
# not machine-checkable). To get real DOM metrics (scrollWidth/clientWidth for horizontal-overflow,
# and nav-link bounding boxes for overlap) out of a bare Chromium binary with no CDP client, this
# test injects a small inline <script> before </body> of a COPY of the real home.html that computes
# those metrics after load and writes them into `document.title` as `PROBE_RESULT:{...json...}`,
# then runs `chrome --headless --dump-dom --virtual-time-budget=...` and parses the title back out.
# The injected script only reads layout geometry; it does not alter the page's own markup or CSS.
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import responsive_validation as rv  # noqa: E402  (reuse CHROME_BIN + documented env limitation)

REPO_ROOT = HERE.parent.parent.parent
HOME_HTML = REPO_ROOT / "site" / "home.html"
SCRATCH = HERE / "_nav_responsive_scratch"

REQUESTED_WIDTHS = (375, 390, 768)
# Same ~500px floor responsive_validation.py documented for this sandbox's headless Chromium CLI;
# 768 is achievable exactly. Recorded here again (not imported silently) so a reader of this file
# alone sees the honest actual-vs-requested mapping without having to cross-reference the other file.
ACHIEVABLE_WIDTHS = {375: 500, 390: 500, 768: 768}

PROBE_SCRIPT = """
<script>
(function(){
  function run(){
    var sw = document.documentElement.scrollWidth;
    var cw = document.documentElement.clientWidth;
    var nav = document.querySelector('nav a[href*="intelligence"]');
    var links = Array.prototype.slice.call(document.querySelectorAll('nav a'));
    var boxes = links.map(function(e){var r=e.getBoundingClientRect();
      return {t:e.textContent,x:r.x,y:r.y,w:r.width,h:r.height};});
    var overlaps = [];
    for (var i=0;i<boxes.length;i++){
      for (var j=i+1;j<boxes.length;j++){
        var a=boxes[i], b=boxes[j];
        if (a.x < b.x+b.w && a.x+a.w > b.x && a.y < b.y+b.h && a.y+a.h > b.y){
          overlaps.push(a.t+'|'+b.t);
        }
      }
    }
    document.title = 'PROBE_RESULT:' + JSON.stringify({
      innerWidth: window.innerWidth,
      scrollWidth: sw,
      clientWidth: cw,
      overflow: sw > cw + 1,
      navPresent: !!nav,
      navText: nav ? nav.textContent : null,
      overlaps: overlaps
    });
  }
  if (document.readyState === 'complete') { setTimeout(run, 200); }
  else { window.addEventListener('load', function(){ setTimeout(run, 200); }); }
})();
</script>
</body>"""


def _build_probe_copy():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    html = HOME_HTML.read_text(encoding="utf-8")
    probe_path = SCRATCH / "home_probe.html"
    probe_path.write_text(html.replace("</body>", PROBE_SCRIPT, 1), encoding="utf-8")
    return probe_path


def _measure(width):
    probe_path = _build_probe_copy()
    result = subprocess.run(
        [rv.CHROME_BIN, "--headless", "--disable-gpu", "--no-sandbox",
         f"--window-size={width},1200", "--virtual-time-budget=3000",
         "--dump-dom", f"file://{probe_path}"],
        capture_output=True, text=True, timeout=30,
    )
    m = re.search(r"PROBE_RESULT:(\{.*?\})</title>", result.stdout, re.S)
    if not m:
        return {"ok": False, "stderr": result.stderr[-500:], "stdout_tail": result.stdout[-500:]}
    return {"ok": True, **json.loads(m.group(1))}


def _chrome_available():
    return Path(rv.CHROME_BIN).exists()


pytestmark = [
    pytest.mark.skipif(not _chrome_available(), reason="headless Chromium binary not present in this environment"),
    pytest.mark.skipif(not HOME_HTML.exists(), reason="site/home.html not built"),
]


@pytest.mark.parametrize("requested_width", REQUESTED_WIDTHS)
def test_nav_intelligence_link_present_and_no_overflow_or_overlap(requested_width):
    m = _measure(requested_width)
    assert m["ok"], f"probe failed to produce a result: {m}"
    # Honesty check: never silently claim the literal requested width was achieved.
    assert m["innerWidth"] == ACHIEVABLE_WIDTHS[requested_width], (
        f"requested {requested_width}px actually rendered at {m['innerWidth']}px "
        f"(expected documented proxy {ACHIEVABLE_WIDTHS[requested_width]}px)"
    )
    assert m["navPresent"], "인텔리전스 nav link (nav a[href*=intelligence]) missing from rendered home.html"
    assert m["navText"] == "인텔리전스"
    assert not m["overflow"], (
        f"document-level horizontal overflow at {requested_width}px "
        f"(scrollWidth={m['scrollWidth']} > clientWidth={m['clientWidth']})"
    )
    assert m["overlaps"] == [], f"overlapping nav links at {requested_width}px: {m['overlaps']}"


def test_cleanup():
    shutil.rmtree(SCRATCH, ignore_errors=True)
