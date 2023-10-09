from __future__ import annotations

import click

from sleeperbot.config import Config
from sleeperbot.league import League

_config = Config()


@click.group()
def cli():
    pass


@cli.command()
def clear_cache():
    _config.redis.flushdb()
    click.echo("Cache cleared...")


@cli.command()
@click.argument("owner_id")
def optimize_roster(owner_id: str):
    league = League()

    try:
        owner = next(
            owner
            for owner in league.owners.values()
            if owner_id.lower() in (owner.display_name.lower(), owner.guid.lower())
        )
    except StopIteration:
        display_names = [owner.display_name for owner in league.owners.values()]
        raise click.BadParameter(
            f"possible owners: {display_names}",
            param_hint="owner_id",
        )

    optimal_roster = league.optimize_roster(owner.roster)

    def print_players(players):
        order = ["QB", "RB", "WR", "TE"]
        players = sorted(players, key=lambda player: order.index(player.position))

        for player in players:
            click.echo(f"    {player.position}: {player.first_name} {player.last_name} {player.team}")

    click.secho("\nPrevious Lineup:\n", fg="yellow")
    print_players([league.players[guid] for guid in owner.roster.starters])

    click.secho("\nOptimal Lineup:\n", fg="yellow")
    print_players([league.players[guid] for guid in optimal_roster.starters])

    if click.confirm("\nDo you want to apply this new lineup?"):
        click.secho("Lineup applied", fg="green")


def main():
    return cli()


if __name__ == "__main__":
    main()
