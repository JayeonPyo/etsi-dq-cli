"""CLI entry point."""
from __future__ import annotations
try:
    import typer
    from typing import Optional
except ImportError:
    raise ImportError("Run: pip install etsi-dq[cli]")
from pathlib import Path

app = typer.Typer(name="etsi-dq", help="ETSI Data Quality Framework", no_args_is_help=True)
auth_app = typer.Typer(help="API key management")
app.add_typer(auth_app, name="auth")

# ── Auth ──
@auth_app.command("set-key")
def auth_set_key(api_key: str = typer.Argument(...)):
    """Save API key."""
    from etsidqcli import auth
    auth.set_key(api_key)
    typer.echo("API key saved to ~/.etsi-dq/credentials.json")

@auth_app.command("set-server")
def auth_set_server(url: str = typer.Argument(...)):
    """Set server URL."""
    from etsidqcli import auth
    auth.set_server(url)
    typer.echo(f"Server URL set to {url}")

@auth_app.command("status")
def auth_status():
    """Show auth config."""
    from etsidqcli import auth
    key = auth.get_key()
    typer.echo(f"  API Key:  {key[:6] + '...' + key[-4:] if key else '(not set)'}")
    typer.echo(f"  Server:   {auth.get_server()}")

@auth_app.command("clear")
def auth_clear():
    """Remove credentials."""
    from etsidqcli import auth
    auth.clear()
    typer.echo("Credentials cleared.")

# ── Register (new user) ──
@app.command(name="register")
def register(
    name: str = typer.Option(..., "--name", "-n", prompt="Your name"),
    org: str = typer.Option("", "--org", "-o", prompt="Organization (optional)"),
):
    """Register as a new user on the server and auto-save API key."""
    from etsidqcli import auth
    import urllib.request, json
    server = auth.get_server()
    try:
        req = urllib.request.Request(
            f"{server}/api/users",
            data=json.dumps({"name": name, "org": org}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        auth.set_key(data["api_key"])
        typer.echo(f"\n  ✓ Registered successfully")
        typer.echo(f"    Name:    {name}")
        typer.echo(f"    Org:     {org or '—'}")
        typer.echo(f"    API Key: {data['api_key']}")
        typer.echo(f"    (auto-saved to ~/.etsi-dq/credentials.json)")
    except Exception as e:
        typer.echo(f"  ✗ Failed to register: {e}")
        typer.echo(f"    Is the server running? ({server})")
        raise typer.Exit(1)

# ── Check ──
@app.command()
def check(
    data: Path = typer.Argument(..., help="Dataset file path"),
    reference: Optional[Path] = typer.Option(None, "--reference", "-r"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    metrics: Optional[str] = typer.Option(None, "--metrics", "-m"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    fmt: str = typer.Option("table", "--format", "-f"),
    no_submit: bool = typer.Option(False, "--no-submit"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Configure metrics interactively"),
):
    """Evaluate data quality."""
    from etsidqcli.core.pipeline import check as run_check
    metric_list = [m.strip() for m in metrics.split(",")] if metrics else None
    rules_dict = None
    if interactive:
        from etsidqcli.cli.wizard import run_wizard
        out = config or Path("rules.json")
        rules_dict = run_wizard(data, out)
        if not metric_list:
            metric_list = rules_dict.get("_metrics")
        config = None
    result = run_check(data=data, reference=reference, config=config,
                       metrics=metric_list, rules_dict=rules_dict)

    if output:
        result.to_json(output)
        typer.echo(f"Results saved to {output}")
    elif fmt == "json":
        typer.echo(result.to_json())
    else:
        typer.echo(result.summary())

    if not no_submit:
        from etsidqcli import auth, client
        if auth.get_key():
            typer.echo("Submitting to server...")
            resp = client.submit_result(result, data_source=data)
            if resp and "certificate_key" in resp:
                typer.echo(f"  ✓ Certificate: {resp['certificate_key']}")
                typer.echo(f"    Verify: {auth.get_server()}{resp.get('verify_url', '')}")
                typer.echo(f"    PDF:    {auth.get_server()}/api/certificates/{resp['certificate_key']}/pdf")
            elif resp:
                typer.echo(f"  Server: {resp}")
            else:
                typer.echo("  (server unavailable — result saved locally only)")

# ── Configure (interactive) ──
@app.command(name="configure")
def configure_cmd(
    data: Path = typer.Argument(..., help="Dataset file path"),
    output: Path = typer.Option(Path("rules.json"), "--output", "-o", help="Where to save the rules file"),
    run: bool = typer.Option(False, "--run", help="Run the evaluation right after configuring"),
):
    """Configure metrics interactively (like the dashboard) and save rules.json."""
    from etsidqcli.cli.wizard import run_wizard
    rules = run_wizard(data, output)
    if run:
        typer.echo("")
        check(data=data, reference=None, config=output, metrics=None,
              output=None, fmt="table", no_submit=False, interactive=False)
    else:
        typer.echo(f"\n  Next:  etsi-dq check {data} --config {output}")


# ── Profile ──
@app.command(name="profile")
def profile_cmd(data: Path = typer.Argument(...)):
    """Profile a dataset."""
    from etsidqcli.core.pipeline import profile
    import json
    typer.echo(json.dumps(profile(data).model_dump(), indent=2, ensure_ascii=False))

# ── Metrics list ──
@app.command(name="metrics")
def list_metrics():
    """List available metrics (computed by the shared etsi_dq library)."""
    items = [
        ("completeness", "Proportion of non-missing values"),
        ("accuracy",     "Rule-based validity of values (needs rules)"),
        ("consistency",  "Rule-based logical consistency (needs rules)"),
        ("timeliness",   "Latency vs. system time"),
        ("reliability",  "Coefficient-of-variation stability"),
        ("uniqueness",   "Proportion of unique rows"),
    ]
    for name, desc in items:
        typer.echo(f"  {name:<16s}  {desc}")

# ── Verify ──
@app.command(name="verify")
def verify_cert(key: str = typer.Argument(...)):
    """Verify a certificate."""
    from etsidqcli import client
    r = client.verify_certificate(key)
    if r is None:
        typer.echo("Could not reach server."); raise typer.Exit(1)
    if r.get("valid"):
        typer.echo(f"\n  ✓ Certificate is VALID")
        typer.echo(f"    Key:          {r['certificate_key']}")
        typer.echo(f"    Evaluated by: {r.get('evaluated_by', 'N/A')}")
        typer.echo(f"    Organization: {r.get('organization', 'N/A')}")
        typer.echo(f"    Dataset:      {r.get('dataset', 'N/A')}")
        typer.echo(f"    Score:        {r['overall_score']:.1%} ({r['overall_grade']})")
    else:
        typer.echo(f"\n  ✗ Certificate NOT FOUND")

# ── History ──
@app.command(name="history")
def history():
    """Show past reports."""
    from etsidqcli import auth
    import urllib.request, json
    key = auth.get_key()
    if not key: typer.echo("No API key. Run: etsi-dq register"); raise typer.Exit(1)
    try:
        with urllib.request.urlopen(f"{auth.get_server()}/api/reports/mine?api_key={key}", timeout=10) as resp:
            data = json.loads(resp.read())
    except: typer.echo("Could not reach server."); raise typer.Exit(1)
    typer.echo(f"\n  Reports for {data.get('user', '?')} ({data['total']} total)\n")
    for r in data["reports"]:
        typer.echo(f"  {r['created_at'][:19]}  {r['dataset_name']:<24s}  {r['overall_score']:.1%} ({r['overall_grade']})")

# ── Serve ──
@app.command(name="serve")
def serve(host: str = typer.Option("0.0.0.0", "--host"), port: int = typer.Option(8000, "--port")):
    """Start the tracking server."""
    import uvicorn
    from etsidqcli.server.app import create_app
    typer.echo(f"Starting ETSI-DQ server on {host}:{port}")
    typer.echo(f"  API docs: http://localhost:{port}/docs")
    uvicorn.run(create_app(), host=host, port=port)

if __name__ == "__main__":
    app()
