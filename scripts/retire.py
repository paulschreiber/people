#!/usr/bin/env python
import os
import glob
import click
from datetime import datetime, timedelta
from utils import load_yaml, dump_obj, role_is_active, get_data_dir
from openstates import metadata


def add_vacancy(person, until):
    with open("settings.yml") as f:
        settings = load_yaml(f)
    last_role = person["roles"][-1]
    abbr = metadata.lookup(jurisdiction_id=last_role["jurisdiction"]).abbr.lower()
    if abbr not in settings:
        settings[abbr] = {"vacancies": []}
    settings[abbr]["vacancies"].append(
        {
            "chamber": last_role["type"],
            "district": last_role["district"],
            "vacant_until": until.date(),
        }
    )
    dump_obj(settings, filename="settings.yml")


def is_inactive(person, date=None):
    active = [role for role in person.get("roles", []) if role_is_active(role, date=date)]
    return len(active) == 0


def autoretire(abbr):
    legislative_filenames = glob.glob(os.path.join(get_data_dir(abbr), "legislature", "*.yml"))
    executive_filenames = glob.glob(os.path.join(get_data_dir(abbr), "executive", "*.yml"))
    municipality_filenames = glob.glob(os.path.join(get_data_dir(abbr), "municipalities", "*.yml"))

    filenames = legislative_filenames + executive_filenames + municipality_filenames
    for filename in filenames:
        with open(filename) as f:
            person = load_yaml(f)

            if is_inactive(person):
                print("retiring ", filename)
                # end_date won't be used since they're already expired
                retire_person(person, None)
                move_file(filename)


def retire_person(person, end_date, reason=None, death=False):
    num = 0
    for role in person["roles"]:
        if role_is_active(role):
            role["end_date"] = end_date
            if reason:
                role["end_reason"] = reason
            num += 1

    if death:
        person["death_date"] = end_date

    # remove old contact details
    person.pop("contact_details", None)

    return person, num


def move_file(filename):  # pragma: no cover
    new_filename = filename.replace("/legislature/", "/retired/").replace(
        "/municipalities/", "/retired/"
    )
    click.secho(f"moved from {filename} to {new_filename}")
    os.renames(filename, new_filename)


def validate_end_date(ctx, param, value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError:
        raise click.BadParameter("END_DATE must be a valid date in the format YYYY-MM-DD")


@click.command()
@click.argument("end_date", callback=validate_end_date)
@click.argument("filenames", nargs=-1)
@click.option("--reason", default=None)
@click.option("--death", is_flag=True)
@click.option("--vacant", is_flag=True)
@click.option("--auto")
def retire(end_date, filenames, reason, death, auto, vacant):
    """
    Retire a legislator, given END_DATE and FILENAME.

    Will set end_date on active roles.
    """
    if auto:
        autoretire(auto)
        return

    for filename in filenames:
        # end the person's active roles & re-save
        with open(filename) as f:
            person = load_yaml(f)
        if death:
            reason = "Deceased"
        person, num = retire_person(person, end_date, reason, death)

        if vacant:
            # default to 60 days for now
            add_vacancy(person, until=datetime.today() + timedelta(days=60))

        dump_obj(person, filename=filename)

        if num == 0:
            click.secho("no active roles to retire", fg="red")
        elif num == 1:
            click.secho("retired person")
        else:
            click.secho(f"retired person from {num} roles")

        move_file(filename)


if __name__ == "__main__":
    retire()
