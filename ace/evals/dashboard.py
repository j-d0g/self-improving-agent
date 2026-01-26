#!/usr/bin/env python3
"""
ACE Training Dashboard

Minimal training visualization with per-batch rolling charts.

Usage:
    python dashboard.py                    # Latest run
    python dashboard.py <run_id>           # Specific run
    python dashboard.py --all              # Compare all runs
"""

import argparse
import json
from pathlib import Path


def get_runs_dir() -> Path:
    return Path(__file__).parent.parent / "logs" / "training"


def get_output_dir() -> Path:
    output_dir = Path(__file__).parent / "dashboards"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def load_run(run_id: str) -> dict | None:
    runs_dir = get_runs_dir()
    for pattern in [f"{run_id}.json", f"run_{run_id}.json"]:
        path = runs_dir / pattern
        if path.exists():
            with open(path) as f:
                return json.load(f)
    return None


def load_all_runs() -> list[dict]:
    runs_dir = get_runs_dir()
    if not runs_dir.exists():
        return []
    runs = []
    for path in sorted(runs_dir.glob("run_*.json")):
        try:
            with open(path) as f:
                runs.append(json.load(f))
        except Exception:
            pass
    return runs


def generate_dashboard(run: dict) -> str:
    run_id = run.get("run_id", "unknown")
    epochs = run.get("epochs", [])
    num_epochs = run.get("num_epochs", len(epochs))
    batch_size = run.get("batch_size", 4)

    # Build per-query data with rolling accuracy
    query_data = []
    cumulative_correct = 0
    cumulative_total = 0
    query_num = 0

    for e in epochs:
        batches = e.get("batches", [])
        for b in batches:
            queries = b.get("queries", [])
            for q in queries:
                query_num += 1
                cumulative_total += 1
                if q.get("correct", False):
                    cumulative_correct += 1
                rolling_acc = cumulative_correct / cumulative_total

                query_data.append({
                    "label": f"Q{query_num}",
                    "correct": q.get("correct", False),
                    "rolling_acc": round(rolling_acc * 100, 1),
                    "tokens": q.get("tokens", 0),
                    "latency": round(q.get("latency", 0), 1),
                    "tool_calls": q.get("tool_calls", 0),
                    "empty_calls": q.get("empty_calls", 0),
                })

    # Validation points (end of each epoch)
    val_data = []
    for e in epochs:
        val_data.append({
            "label": f"E{e.get('epoch', 0)}",
            "accuracy": round(e.get("validation_accuracy", 0) * 100, 1),
        })

    # Totals
    final_train = run.get("final_train_accuracy", 0) * 100
    final_val = run.get("final_validation_accuracy", 0) * 100
    total_tokens = run.get("total_tokens", 0)
    total_latency = run.get("total_latency_seconds", 0)
    total_tool_calls = run.get("total_tool_calls", 0)
    empty_tool_calls = run.get("empty_tool_calls", 0)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{run_id}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa; color: #212529; line-height: 1.5; padding: 2rem; }}
        .dashboard {{ max-width: 1200px; margin: 0 auto; }}
        header {{ margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid #dee2e6; }}
        h1 {{ font-size: 1.5rem; font-weight: 600; margin-bottom: 0.25rem; }}
        .subtitle {{ color: #6c757d; font-size: 0.875rem; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 1rem; margin-bottom: 2rem; }}
        @media (max-width: 900px) {{ .metrics-grid {{ grid-template-columns: repeat(3, 1fr); }} }}
        .metric-card {{ background: #fff; border: 1px solid #dee2e6; border-radius: 6px; padding: 1.25rem; }}
        .metric-label {{ font-size: 0.75rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; color: #6c757d; margin-bottom: 0.5rem; }}
        .metric-value {{ font-size: 1.75rem; font-weight: 600; color: #212529; }}
        .charts-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-bottom: 2rem; }}
        @media (max-width: 900px) {{ .charts-grid {{ grid-template-columns: 1fr; }} }}
        .chart-card {{ background: #fff; border: 1px solid #dee2e6; border-radius: 6px; padding: 1.25rem; }}
        .chart-title {{ font-size: 0.875rem; font-weight: 600; margin-bottom: 1rem; color: #212529; }}
        .chart-container {{ position: relative; height: 220px; }}
        .footer {{ text-align: center; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #dee2e6; color: #6c757d; font-size: 0.75rem; }}
    </style>
</head>
<body>
    <div class="dashboard">
        <header>
            <h1>Training Run</h1>
            <p class="subtitle">{run_id} &middot; {num_epochs} epochs &middot; batch size {batch_size}</p>
        </header>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Train Accuracy</div>
                <div class="metric-value">{final_train:.0f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Val Accuracy</div>
                <div class="metric-value">{final_val:.0f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Tokens</div>
                <div class="metric-value">{total_tokens:,}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Latency</div>
                <div class="metric-value">{total_latency:.0f}s</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Tool Calls</div>
                <div class="metric-value">{total_tool_calls:,}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Empty Calls</div>
                <div class="metric-value">{empty_tool_calls:,}</div>
            </div>
        </div>

        <div class="charts-grid">
            <div class="chart-card">
                <div class="chart-title">Rolling Train Accuracy (per query)</div>
                <div class="chart-container">
                    <canvas id="accuracyChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <div class="chart-title">Validation Accuracy (per epoch)</div>
                <div class="chart-container">
                    <canvas id="valChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <div class="chart-title">Tokens per Query</div>
                <div class="chart-container">
                    <canvas id="tokensChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <div class="chart-title">Latency per Query</div>
                <div class="chart-container">
                    <canvas id="latencyChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <div class="chart-title">Tool Calls per Query</div>
                <div class="chart-container">
                    <canvas id="toolsChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <div class="chart-title">Empty Calls per Query</div>
                <div class="chart-container">
                    <canvas id="emptyChart"></canvas>
                </div>
            </div>
        </div>

        <div class="footer">
            Generated {run.get("end_time", "")[:19].replace("T", " ")}
        </div>
    </div>

    <script>
        const queryData = {json.dumps(query_data)};
        const valData = {json.dumps(val_data)};
        const queryLabels = queryData.map(d => d.label);
        const valLabels = valData.map(d => d.label);

        const chartOptions = {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
                x: {{ grid: {{ color: '#f1f3f4' }}, ticks: {{ color: '#6c757d', font: {{ size: 11 }} }} }},
                y: {{ grid: {{ color: '#f1f3f4' }}, ticks: {{ color: '#6c757d', font: {{ size: 11 }} }}, beginAtZero: true }}
            }}
        }};

        new Chart(document.getElementById('accuracyChart'), {{
            type: 'line',
            data: {{
                labels: queryLabels,
                datasets: [{{
                    data: queryData.map(d => d.rolling_acc),
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.05)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                    borderWidth: 2
                }}]
            }},
            options: {{ ...chartOptions, scales: {{ ...chartOptions.scales, y: {{ ...chartOptions.scales.y, max: 100 }} }} }}
        }});

        new Chart(document.getElementById('valChart'), {{
            type: 'line',
            data: {{
                labels: valLabels,
                datasets: [{{
                    data: valData.map(d => d.accuracy),
                    borderColor: '#198754',
                    backgroundColor: 'rgba(25, 135, 84, 0.05)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    borderWidth: 2
                }}]
            }},
            options: {{ ...chartOptions, scales: {{ ...chartOptions.scales, y: {{ ...chartOptions.scales.y, max: 100 }} }} }}
        }});

        new Chart(document.getElementById('tokensChart'), {{
            type: 'line',
            data: {{
                labels: queryLabels,
                datasets: [{{
                    data: queryData.map(d => d.tokens),
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.05)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                    borderWidth: 2
                }}]
            }},
            options: chartOptions
        }});

        new Chart(document.getElementById('latencyChart'), {{
            type: 'line',
            data: {{
                labels: queryLabels,
                datasets: [{{
                    data: queryData.map(d => d.latency),
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.05)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                    borderWidth: 2
                }}]
            }},
            options: chartOptions
        }});

        new Chart(document.getElementById('toolsChart'), {{
            type: 'line',
            data: {{
                labels: queryLabels,
                datasets: [{{
                    data: queryData.map(d => d.tool_calls),
                    borderColor: '#6c757d',
                    backgroundColor: 'rgba(108, 117, 125, 0.05)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                    borderWidth: 2
                }}]
            }},
            options: chartOptions
        }});

        new Chart(document.getElementById('emptyChart'), {{
            type: 'line',
            data: {{
                labels: queryLabels,
                datasets: [{{
                    data: queryData.map(d => d.empty_calls),
                    borderColor: '#dc3545',
                    backgroundColor: 'rgba(220, 53, 69, 0.05)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                    borderWidth: 2
                }}]
            }},
            options: chartOptions
        }});
    </script>
</body>
</html>
"""


def generate_comparison(runs: list[dict]) -> str:
    runs = sorted(runs, key=lambda r: r.get("start_time", ""))
    data = [{
        "id": r.get("run_id", "")[-15:],
        "train": round(r.get("final_train_accuracy", 0) * 100),
        "val": round(r.get("final_validation_accuracy", 0) * 100),
        "tokens": r.get("total_tokens", 0),
        "latency": round(r.get("total_latency_seconds", 0)),
    } for r in runs]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Run Comparison</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa; color: #212529; line-height: 1.5; padding: 2rem; }}
        .dashboard {{ max-width: 1000px; margin: 0 auto; }}
        header {{ margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid #dee2e6; }}
        h1 {{ font-size: 1.5rem; font-weight: 600; margin-bottom: 0.25rem; }}
        .subtitle {{ color: #6c757d; font-size: 0.875rem; }}
        .chart-card {{ background: #fff; border: 1px solid #dee2e6; border-radius: 6px; padding: 1.25rem; margin-bottom: 1.5rem; }}
        .chart-title {{ font-size: 0.875rem; font-weight: 600; margin-bottom: 1rem; }}
        .chart-container {{ position: relative; height: 250px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; background: #fff; border: 1px solid #dee2e6; border-radius: 6px; }}
        th {{ padding: 0.75rem 1rem; text-align: left; font-weight: 500; color: #6c757d; font-size: 0.75rem; text-transform: uppercase; border-bottom: 1px solid #dee2e6; background: #f8f9fa; }}
        td {{ padding: 0.75rem 1rem; border-bottom: 1px solid #f1f3f4; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover {{ background: #f8f9fa; }}
    </style>
</head>
<body>
    <div class="dashboard">
        <header>
            <h1>Run Comparison</h1>
            <p class="subtitle">{len(runs)} runs</p>
        </header>

        <div class="chart-card">
            <div class="chart-title">Accuracy Comparison</div>
            <div class="chart-container">
                <canvas id="chart"></canvas>
            </div>
        </div>

        <table>
            <thead>
                <tr><th>Run</th><th>Train</th><th>Val</th><th>Tokens</th><th>Latency</th></tr>
            </thead>
            <tbody>
                {"".join(f"<tr><td>{d['id']}</td><td>{d['train']}%</td><td>{d['val']}%</td><td>{d['tokens']:,}</td><td>{d['latency']}s</td></tr>" for d in data)}
            </tbody>
        </table>
    </div>

    <script>
        const data = {json.dumps(data)};
        new Chart(document.getElementById('chart'), {{
            type: 'bar',
            data: {{
                labels: data.map(d => d.id),
                datasets: [
                    {{ label: 'Train %', data: data.map(d => d.train), backgroundColor: '#0d6efd' }},
                    {{ label: 'Val %', data: data.map(d => d.val), backgroundColor: '#198754' }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 12, padding: 16 }} }} }},
                scales: {{ y: {{ beginAtZero: true, max: 100 }} }}
            }}
        }});
    </script>
</body>
</html>
"""


def cmd_dashboard(run_id: str | None = None, compare_all: bool = False, compare_ids: list[str] | None = None):
    output_dir = get_output_dir()

    if compare_all or compare_ids:
        runs = load_all_runs() if compare_all else [r for r in (load_run(rid) for rid in compare_ids) if r]
        if not runs:
            print("No runs found.")
            return
        html = generate_comparison(runs)
        output_path = output_dir / "comparison.html"
    else:
        run = load_run(run_id) if run_id else (load_all_runs() or [None])[-1]
        if not run:
            print("No runs found.")
            return
        html = generate_dashboard(run)
        output_path = output_dir / f"{run.get('run_id', 'run')}.html"

    output_path.write_text(html)
    print(f"Saved: {output_path}")
    print(f"Open: file://{output_path.absolute()}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--compare", nargs="+")
    args = parser.parse_args()
    cmd_dashboard(args.run_id, args.all, args.compare)


if __name__ == "__main__":
    main()
