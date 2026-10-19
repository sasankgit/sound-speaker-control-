"""Launch the audio control UI, or use the legacy CLI when arguments are given."""

import sys

from audio_control.cli import main as cli_main


def main():
    if len(sys.argv) > 1:
        cli_main()
        return

    from audio_control.ui import run_app

    run_app()


if __name__ == "__main__":
    main()
