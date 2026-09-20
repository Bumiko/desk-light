"""Проверка платы из консоли, без трея.

    python app/cli.py ping
    python app/cli.py on | off | toggle | state
    python app/cli.py set 350
"""

import sys

from link import find


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    command = " ".join(argv)
    board = find()
    print("%s <- %s" % (board.port, command))
    print("%s -> %s" % (board.port, board.send(command)))
    board.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
