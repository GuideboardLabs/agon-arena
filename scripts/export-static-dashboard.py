#!/usr/bin/env python3
"""Generate a self-contained, static agon-bench.html for static hosting (IONOS).

Reuses dashboard-server.py's get_model_data() so the numbers match the live
dashboard exactly. Embeds the JSON into the HTML and replaces the /api/models
fetch with the embedded data, so it works with zero backend on any static host.

Usage:
    python3 scripts/export-static-dashboard.py [out.html]
"""
import importlib.util
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ARENA = os.path.dirname(HERE)

# dashboard-server.py has a hyphen, so import via spec_from_file_location
_spec = importlib.util.spec_from_file_location(
    "dashboard_server", os.path.join(HERE, "dashboard-server.py")
)
dashboard_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dashboard_server)
get_model_data = dashboard_server.get_model_data

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ARENA, "agon-bench.html")
    html_path = os.path.join(ARENA, "agon-dashboard.html")
    with open(html_path) as f:
        html = f.read()

    data = get_model_data()
    payload = json.dumps(data)

    # Replace the two fetch('/api/models') blocks with the embedded data.
    # Pattern 1: const resp = await fetch('/api/models'); ALL_MODELS = await resp.json();
    html = re.sub(
        r"const resp = await fetch\('/api/models'\);\s*ALL_MODELS = await resp\.json\(\);",
        "ALL_MODELS = __AGON_DATA__;",
        html,
    )
    # Pattern 2 (the setInterval refresh): same but inside a try block
    html = re.sub(
        r"const resp = await fetch\('/api/models'\);\s*ALL_MODELS = await resp\.json\(\);",
        "ALL_MODELS = __AGON_DATA__;",
        html,
    )

    # Inject the data right before the initDashboard call / script end.
    # Put it just before the closing </script> that contains initDashboard.
    marker = "// ── Init ──"
    if marker in html:
        html = html.replace(marker, f"const __AGON_DATA__ = {payload};\n\n{marker}", 1)
    else:
        # fallback: inject before </body>
        html = html.replace("</body>", f"<script>const __AGON_DATA__ = {payload};</script>\n</body>", 1)

    # Remove the auto-refresh interval (static data, no point re-fetching)
    html = re.sub(
        r"setInterval\(async \(\) => \{.*?\}, \d+\);",
        "",
        html,
        flags=re.DOTALL,
    )

    with open(out, "w") as f:
        f.write(html)
    print(f"Wrote {out} ({len(html)} bytes, {len(data)} models)")

if __name__ == "__main__":
    main()
