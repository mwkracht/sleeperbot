from __future__ import annotations

import click

from sleeperbot import config
from sleeperbot.clients import sleeper
from sleeperbot.league import League


@click.group()
def cli():
    pass


@cli.command()
def clear_cache():
    config.redis.flushdb()
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
        raise click.BadParameter(f"possible owners: {display_names}", param_hint="owner_id")

    optimal_roster = league.optimize_roster(owner.roster)

    def print_roster(players):
        def print_players(players):
            order = ["QB", "RB", "WR", "TE"]
            for player in sorted(players, key=lambda player: order.index(player.position)):
                click.echo(f"    {player.position}: {player.first_name} {player.last_name} - {player.team}")

        print_players([league.players[p_id] for p_id in players])

    click.secho("\n-- Starters Before --", fg="yellow")
    print_roster(owner.roster.starters)
    click.secho("\n-- Starters After --", fg="yellow")
    print_roster(optimal_roster.starters)

    if click.confirm("\nDo you want to apply changes to starters?"):
        sleeper.update_starters(league.settings, league.me.roster)
        click.secho("Starters applied", fg="green")

    click.secho("\n-- IR Before--", fg="yellow")
    print_roster(owner.roster.reserve)
    click.secho("\n-- IR After --", fg="yellow")
    print_roster(optimal_roster.reserve)

    if click.confirm("\nDo you want to apply changes to injured reserve?"):
        sleeper.update_injured_reserve(league.settings, league.me.roster)
        click.secho("Injured reserve applied", fg="green")

    click.secho("\n-- Taxi Before --", fg="yellow")
    print_roster(owner.roster.taxi)
    click.secho("\n-- Taxi After --", fg="yellow")
    print_roster(optimal_roster.taxi)

    if click.confirm("\nDo you want to apply changes to taxi?"):
        sleeper.update_taxi(league.settings, league.me.roster)
        click.secho("Taxi applied", fg="green")


def main():
    return cli()


if __name__ == "__main__":
    main()
