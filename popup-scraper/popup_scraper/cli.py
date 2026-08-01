"""Command-line entrypoint.

Usage:
    python -m popup_scraper.cli <command> [options]

Commands:
    login                       Log into Instagram and cache the session.
    follow                      Follow every artist listed in artists.yaml.
    run                         Do one poll -> analyze -> blast pass.
    watch                       Poll continuously on POLL_INTERVAL_SECONDS.
    subscribers add <phone>     Add/opt-in a subscriber (E.164, e.g. +15551234567).
    subscribers remove <phone>  Opt a subscriber out.
    subscribers list            List active subscribers.
"""
from __future__ import annotations

import argparse
import logging
import sys

from .artists import load_artists
from .config import Config, ConfigError
from .instagram import InstagrapiSource
from .notifier import ConsoleNotifier, TwilioNotifier
from .pipeline import Pipeline
from .store import Store
from .vision import VisionAnalyzer


def _build_source(config: Config) -> InstagrapiSource:
    config.require_instagram()
    return InstagrapiSource(
        config.ig_username, config.ig_password, config.ig_session_file
    )


def _build_notifier(config: Config):
    if config.notifier == "console":
        return ConsoleNotifier()
    config.require_twilio()
    return TwilioNotifier(
        config.twilio_account_sid,
        config.twilio_auth_token,
        config.twilio_from_number,
    )


def _build_pipeline(config: Config, store: Store) -> Pipeline:
    config.require_vision()
    source = _build_source(config)
    source.login()
    analyzer = VisionAnalyzer(config.anthropic_api_key, config.vision_model)
    notifier = _build_notifier(config)
    return Pipeline(config, source, analyzer, notifier, store)


def cmd_login(config: Config, args: argparse.Namespace) -> int:
    source = _build_source(config)
    source.login()
    print("Instagram login OK. Session cached at", config.ig_session_file)
    return 0


def cmd_follow(config: Config, args: argparse.Namespace) -> int:
    source = _build_source(config)
    source.login()
    artists = load_artists(config.artists_file)
    results = source.follow_artists(artists)
    ok = sum(1 for v in results.values() if v)
    print(f"Followed {ok}/{len(results)} artists.")
    for name, success in results.items():
        print(f"  {'✓' if success else '✗'} {name}")
    return 0


def cmd_run(config: Config, args: argparse.Namespace) -> int:
    store = Store(config.database_path)
    try:
        pipeline = _build_pipeline(config, store)
        artists = load_artists(config.artists_file)
        stats = pipeline.run_once(artists)
        print(
            f"Checked {stats.posts_checked}, new {stats.new_posts}, "
            f"pop-ups {stats.popups_found}, blasts {stats.blasts_sent}."
        )
    finally:
        store.close()
    return 0


def cmd_watch(config: Config, args: argparse.Namespace) -> int:
    store = Store(config.database_path)
    try:
        pipeline = _build_pipeline(config, store)
        artists = load_artists(config.artists_file)
        pipeline.watch(artists)
    finally:
        store.close()
    return 0


def cmd_subscribers(config: Config, args: argparse.Namespace) -> int:
    store = Store(config.database_path)
    try:
        if args.action == "add":
            store.add_subscriber(args.phone, args.name)
            print(f"Added/opted-in {args.phone}.")
        elif args.action == "remove":
            store.remove_subscriber(args.phone)
            print(f"Opted out {args.phone}.")
        elif args.action == "list":
            subs = store.list_subscribers(active_only=False)
            active = [s for s in subs if s.active]
            print(f"{len(active)} active subscriber(s):")
            for s in subs:
                flag = "active" if s.active else "opted-out"
                name = f" ({s.name})" if s.name else ""
                print(f"  {s.phone}{name} [{flag}]")
    finally:
        store.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="popup_scraper", description=__doc__)
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Log into Instagram and cache the session.")
    sub.add_parser("follow", help="Follow every artist in artists.yaml.")
    sub.add_parser("run", help="One poll -> analyze -> blast pass.")
    sub.add_parser("watch", help="Poll continuously.")

    subs = sub.add_parser("subscribers", help="Manage SMS subscribers.")
    subs_sub = subs.add_subparsers(dest="action", required=True)
    add = subs_sub.add_parser("add", help="Add/opt-in a subscriber.")
    add.add_argument("phone", help="E.164 number, e.g. +15551234567")
    add.add_argument("--name", default=None)
    rm = subs_sub.add_parser("remove", help="Opt a subscriber out.")
    rm.add_argument("phone")
    subs_sub.add_parser("list", help="List subscribers.")

    return parser


_COMMANDS = {
    "login": cmd_login,
    "follow": cmd_follow,
    "run": cmd_run,
    "watch": cmd_watch,
    "subscribers": cmd_subscribers,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        config = Config.from_env()
        return _COMMANDS[args.command](config, args)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
