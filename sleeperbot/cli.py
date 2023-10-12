from __future__ import annotations

import click

from sleeperbot.clients import sleeper
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

    def print_roster(roster):
        def print_players(players):
            order = ["QB", "RB", "WR", "TE"]
            for player in sorted(players, key=lambda player: order.index(player.position)):
                click.echo(f"    {player.position}: {player.first_name} {player.last_name} - {player.team}")

        click.echo("\n-- Starters --")
        print_players([league.players[p_id] for p_id in roster.starters])

        click.echo("\n-- Bench --")
        print_players([league.players[p_id] for p_id in roster.bench])

        click.echo("\n-- Injured Reserve --")
        print_players([league.players[p_id] for p_id in roster.reserve])

        click.echo("\n-- Taxi --")
        print_players([league.players[p_id] for p_id in roster.taxi])

    click.secho("\nPrevious Lineup:", fg="yellow")
    print_roster(owner.roster)

    click.secho("\nOptimal Lineup:", fg="yellow")
    print_roster(optimal_roster)

    if click.confirm("\nDo you want to apply this new lineup?"):
        sleeper.update_roster(league.settings, optimal_roster)
        click.secho("Lineup applied", fg="green")


def main():
    return cli()


if __name__ == "__main__":
    main()
