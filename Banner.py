import os


def banner(path=""):
    print("\n", end="")
    banner = open(os.path.join(path, "banner.txt"), "r", encoding="utf8")
    banner_text = open(os.path.join(path, "banner_text.txt"), "r", encoding="utf8")
    for line1, line2 in zip(banner_text.readlines(), banner.readlines()):
        print("\t" + line1 + "\t" + line2.replace("\n", ""), end="")
    print("\n\n")


if __name__ == "__main__":
    banner()