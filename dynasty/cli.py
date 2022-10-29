from __future__ import annotations

import click


@click.command()
def dynasty_cli():
    click.echo('Hello :)')


def main():
    dynasty_cli()


if __name__ == '__main__':
    main()
