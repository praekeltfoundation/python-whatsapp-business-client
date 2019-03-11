from limit import limit
import json
import click
import csv
import requests


class RateLimitType(click.ParamType):
    name = "rate_limit"

    def convert(self, value, param, ctx):
        try:
            [rate, seconds] = value.split("/")
            return (int(rate), int(seconds))
        except ValueError:
            self.fail(
                "%s is not a valid rate/seconds rate limit type" % value, param, ctx
            )


@click.group()
def main():
    pass


@main.command()
@click.option("--token", "-t", type=click.STRING, envvar="WABCLIENT_TOKEN")
@click.option("--namespace", "-ns", type=click.STRING)
@click.option("--name", "-n", type=click.STRING)
@click.option("--param", "-p", type=click.STRING, multiple=True)
@click.option("--rate-limit", "-r", default="60/60", type=RateLimitType())
@click.option("--dry-run/--no-dry-run")
@click.option(
    "--base-url",
    "-b",
    default="https://whatsapp.praekelt.org/v1/messages",
    type=click.STRING,
)
@click.option("--csv-file", "-f", type=click.File("r"))
def send(token, namespace, name, param, rate_limit, base_url, dry_run, csv_file):
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "WABClient/CLI",
            "Authorization": "Bearer %s" % (token,),
            "Content-Type": "application/json",
        }
    )

    localizable_params = [{"default": p} for p in param]

    reader = filter(None, csv.reader(csv_file))

    @limit(*rate_limit)
    def send_one(msisdn):
        payload = {
            "to": msisdn,
            "type": "hsm",
            "hsm": {
                "namespace": namespace,
                "element_name": name,
                "language": {"policy": "fallback", "code": "en"},
                "localizable_params": localizable_params,
            },
        }

        if not dry_run:
            try:
                response = session.post(base_url, timeout=5, data=json.dumps(payload))
                response.raise_for_status()
                click.echo(click.style(record, fg="green"))
            except requests.exceptions.HTTPError:
                click.echo(click.style(record, fg="red"))
        else:
            click.echo(click.style(record, fg="green"))

    for (record,) in reader:
        send_one(record)
