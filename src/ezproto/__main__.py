"""Application entry point."""

from ezproto.app import ProtoboardApp


def main() -> None:
    """Run the Textual protoboard generator."""
    ProtoboardApp().run()


if __name__ == "__main__":
    main()
