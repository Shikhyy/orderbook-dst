"""tools/list_models.py
List the model IDs each configured provider offers to your key, and check that
every model_id in models.toml exists. Read-only: it calls each provider's
/models endpoint and never runs a completion.

Usage: python tools/list_models.py --models models.toml [--filter coder]
"""
import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    import tomllib as tomli
except ImportError:  # pragma: no cover
    import tomli  # type: ignore


def main() -> None:
    ap = argparse.ArgumentParser(description="List provider model IDs for models.toml.")
    ap.add_argument("--models", default=str(REPO_ROOT / "models.toml"))
    ap.add_argument("--filter", default="", help="Only show IDs containing this text")
    args = ap.parse_args()

    import openai

    cfg = tomli.loads(Path(args.models).read_text(encoding="utf-8")).get("model", [])
    seen: set[tuple[str, str]] = set()
    ok = True
    for m in cfg:
        adapter = m.get("adapter")
        if adapter not in ("openai_compat", "openai"):
            print(f"[{m.get('label')}] adapter {adapter}: listing not supported, skipped")
            continue
        base = m.get("base_url") if adapter == "openai_compat" else None
        key_env = m.get("api_key_env") or (
            "OPENAI_API_KEY" if adapter == "openai" else "OPENAI_COMPAT_API_KEY"
        )
        key = os.environ.get(key_env, "") or ("EMPTY" if base and "localhost" in base else "")
        if not key:
            print(f"[{m.get('label')}] {key_env} is not set; skipped")
            ok = False
            continue
        try:
            client = openai.OpenAI(base_url=base, api_key=key, max_retries=1)
            ids = sorted(x.id for x in client.models.list())
        except Exception as exc:  # noqa: BLE001
            print(f"[{m.get('label')}] could not list models at {base}: {exc}")
            ok = False
            continue
        # Some providers prefix IDs with "models/"; accept either form.
        norm = {i.removeprefix("models/") for i in ids}
        want = m.get("model_id", "")
        found = want in ids or want.removeprefix("models/") in norm
        status = "OK" if found else "NOT FOUND"
        ok = ok and found
        print(f"[{m.get('label')}] model_id = {want!r}: {status}")
        key_pair = (str(base), key_env)
        if key_pair not in seen:
            seen.add(key_pair)
            shown = [i for i in ids if args.filter.lower() in i.lower()]
            print(f"  {len(shown)} models at {base or 'api.openai.com'}:")
            for i in shown:
                print(f"    {i}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
