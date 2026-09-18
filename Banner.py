from pathlib import Path


def banner(path=None):
    directory = Path(path) if path else Path(__file__).resolve().parent
    with (
        (directory / "banner.txt").open(encoding="utf-8") as art,
        (directory / "banner_text.txt").open(encoding="utf-8") as text,
    ):
        print("\n" + "\n".join(f"\t{a.rstrip()}\t{b.rstrip()}" for a, b in zip(text, art)) + "\n")
