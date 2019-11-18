from limit import limit
import json
import click
import csv
import requests


class PhoneNumberType(click.ParamType):
    name = "phone_number"

    def convert(self, value, param, ctx):
        return value.lstrip("+")


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
@click.option("--number", "-nr", type=PhoneNumberType())
@click.option("--token", "-t", type=click.STRING, envvar="WABCLIENT_TOKEN")
@click.option("--name", "-n", type=click.STRING)
@click.option("--language", "-l", type=click.STRING, default="en")
@click.option("--category", "-c", type=click.STRING, default="ALERT_UPDATE")
@click.option("--template", "-m", type=click.STRING)
@click.option("--debug/--no-debug", "-d", default=False)
@click.option(
    "--base-url", "-b", default="https://whatsapp.praekelt.org/v3.3", type=click.STRING
)
def create(number, token, name, language, category, template, debug, base_url):
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "WABClient/CLI",
            "Authorization": "Bearer %s" % (token,),
            "Content-Type": "application/json",
        }
    )

    payload = {
        "category": category,
        "components": json.dumps([{"type": "BODY", "text": template}]),
        "name": name.lower(),
        "language": language,
    }

    response = session.post(
        "%s/%s/message_templates" % (base_url, number),
        timeout=5,
        data=json.dumps(payload),
    )
    try:
        response.raise_for_status()
        data = response.json()
        click.echo(click.style("Template created: %(id)s" % data, fg="green"))
    except requests.exceptions.HTTPError as exception:
        if debug:
            click.echo(
                "%s: %s"
                % (
                    click.style(repr(exception.response), fg="yellow"),
                    click.style(repr(payload), fg="red"),
                ),
                err=True,
            )
        else:
            click.echo(
                click.style(
                    "Failed to create template, response code: %s"
                    % (exception.response.status_code,),
                    fg="yellow",
                ),
                err=True,
            )


@main.command()
@click.option("--token", "-t", type=click.STRING, envvar="WABCLIENT_TOKEN")
@click.option("--namespace", "-ns", type=click.STRING)
@click.option("--name", "-n", type=click.STRING)
@click.option("--language", "-l", type=click.STRING, default="en")
@click.option("--policy", "-pl", type=click.STRING, default="fallback")
@click.option("--param", "-p", type=click.STRING, multiple=True)
@click.option("--rate-limit", "-r", default="60/60", type=RateLimitType())
@click.option("--dry-run/--no-dry-run")
@click.option("--debug/--no-debug", "-d", default=False)
@click.option(
    "--base-url",
    "-b",
    default="https://whatsapp.praekelt.org/v1/messages",
    type=click.STRING,
)
@click.option("--csv-file", "-f", type=click.File("r"))
def send(
    token,
    namespace,
    name,
    language,
    policy,
    param,
    rate_limit,
    debug,
    base_url,
    dry_run,
    csv_file,
):
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
                "language": {"policy": policy, "code": language},
                "localizable_params": localizable_params,
            },
        }

        if not dry_run:
            try:
                response = session.post(base_url, timeout=5, data=json.dumps(payload))
                response.raise_for_status()
                click.echo(click.style(record, fg="green"))
            except requests.exceptions.HTTPError as exception:
                if debug:
                    click.echo(
                        "%s, %s"
                        % (
                            click.style(record, fg="red"),
                            click.style(
                                json.dumps(exception.response.json()), fg="yellow"
                            ),
                        ),
                        err=True,
                    )
                else:
                    click.echo(click.style(record, fg="red"), err=True)
        else:
            click.echo(click.style(record, fg="green"))

    for (record,) in reader:
        send_one(record)
