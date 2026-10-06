"""`python -m cbench`: the cbench CLI (the MCP server runs side-effecting
tools this way, with the interpreter it runs under)."""
from cbench.cli.main import cli

if __name__ == "__main__":
    cli(prog_name="cbench")
