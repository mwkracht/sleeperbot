from __future__ import annotations

import click


@click.command()
def cli():
    click.echo('Hello :)')


def main():
    return cli()


if __name__ == '__main__':
    main()
