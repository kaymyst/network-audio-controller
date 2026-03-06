from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import typer

from netaudio_lib.dante.device_commands import DanteDeviceCommands

from netaudio._common import (
    _command_context,
    _discover,
    _get_arc_port,
    _populate_controls,
    filter_devices,
    find_channel,
    find_device,
    output_table,
    parse_qualified_name,
    sort_devices,
)
from netaudio._exit_codes import ExitCode

app = typer.Typer(help="Manage audio subscriptions.", no_args_is_help=True)


@app.command("list")
def subscription_list():
    """List all active subscriptions."""

    async def _run():
        from netaudio_lib.dante.const import SUBSCRIPTION_STATUS_INFO
        from netaudio_lib.dante.device_serializer import DanteDeviceSerializer

        devices = await _discover()
        await _populate_controls(devices)
        devices = filter_devices(devices)

        all_subscriptions = []

        for server_name, device in sort_devices(devices):
            for subscription in device.subscriptions:
                all_subscriptions.append(subscription)

        if not all_subscriptions:
            typer.echo("No active subscriptions.")
            return

        from netaudio.cli import state

        _STATE_COLORS = {
            "connected": "\033[32m",
            "in_progress": "\033[33m",
            "resolved": "\033[33m",
            "idle": "\033[33m",
            "unresolved": "\033[31m",
            "error": "\033[31m",
            "none": "\033[90m",
        }

        def _status_label(code):
            info = SUBSCRIPTION_STATUS_INFO.get(code)
            if not info:
                return ""
            status_state, label, _ = info
            if state.no_color:
                return label
            color = _STATE_COLORS.get(status_state, "")
            if not color:
                return label
            return f"{color}{label}\033[0m"

        headers = ["RX Channel", "RX Device", "TX Channel", "TX Device", "Status"]
        rows = []
        json_data = [DanteDeviceSerializer.subscription_to_json(s) for s in all_subscriptions]

        for subscription in all_subscriptions:
            rows.append([
                subscription.rx_channel_name or "",
                subscription.rx_device_name or "",
                subscription.tx_channel_name or "",
                subscription.tx_device_name or "",
                _status_label(subscription.status_code),
            ])

        output_table(headers, rows, json_data=json_data)

    asyncio.run(_run())


@app.command()
def add(
    tx: str = typer.Option(..., "--tx", help="TX source as channel@device."),
    rx: str = typer.Option(..., "--rx", help="RX destination as channel@device."),
):
    """Add a subscription (route audio from TX to RX)."""

    commands = DanteDeviceCommands()

    async def _run():
        if not tx or not rx:
            typer.echo("Error: both --tx and --rx required.", err=True)
            raise typer.Exit(code=ExitCode.ERROR)

        tx_channel_id, tx_device_id = parse_qualified_name(tx)
        rx_channel_id, rx_device_id = parse_qualified_name(rx)

        async with _command_context() as (devices, send):
            tx_device = find_device(devices, tx_device_id)
            if tx_device is None:
                typer.echo(f"Error: TX device '{tx_device_id}' not found.", err=True)
                raise typer.Exit(code=ExitCode.ERROR)

            rx_device = find_device(devices, rx_device_id)
            if rx_device is None:
                typer.echo(f"Error: RX device '{rx_device_id}' not found.", err=True)
                raise typer.Exit(code=ExitCode.ERROR)

            tx_channel = find_channel(tx_device, tx_channel_id, "tx")
            if tx_channel is None:
                typer.echo(f"Error: TX channel '{tx_channel_id}' not found on {tx_device.name}.", err=True)
                raise typer.Exit(code=ExitCode.ERROR)

            rx_channel = find_channel(rx_device, rx_channel_id, "rx")
            if rx_channel is None:
                typer.echo(f"Error: RX channel '{rx_channel_id}' not found on {rx_device.name}.", err=True)
                raise typer.Exit(code=ExitCode.ERROR)

            tx_channel_name = tx_channel.friendly_name or tx_channel.name
            packet, _ = commands.command_add_subscription(
                rx_channel.number, tx_channel_name, tx_device.name
            )
            arc_port = _get_arc_port(rx_device)
            await send(packet, rx_device.ipv4, arc_port)
            typer.echo(f"{rx_channel_id}@{rx_device.name} <- {tx_channel_id}@{tx_device.name}")

    asyncio.run(_run())


@app.command()
def remove(
    rx: str = typer.Option(..., "--rx", help="RX channel as channel@device."),
):
    """Remove a subscription from an RX channel."""

    commands = DanteDeviceCommands()

    async def _run():
        if not rx:
            typer.echo("Error: --rx required.", err=True)
            raise typer.Exit(code=ExitCode.ERROR)

        rx_channel_id, rx_device_id = parse_qualified_name(rx)

        async with _command_context() as (devices, send):
            rx_device = find_device(devices, rx_device_id)
            if rx_device is None:
                typer.echo(f"Error: RX device '{rx_device_id}' not found.", err=True)
                raise typer.Exit(code=ExitCode.ERROR)

            rx_channel = find_channel(rx_device, rx_channel_id, "rx")
            if rx_channel is None:
                typer.echo(f"Error: RX channel '{rx_channel_id}' not found on {rx_device.name}.", err=True)
                raise typer.Exit(code=ExitCode.ERROR)

            packet, _ = commands.command_remove_subscription(rx_channel.number)
            arc_port = _get_arc_port(rx_device)
            await send(packet, rx_device.ipv4, arc_port)
            typer.echo(f"Removed: {rx_channel_id}@{rx_device.name}")

    asyncio.run(_run())


@app.command()
def bulk(
    tx_device_id: str = typer.Option(..., "--tx", help="TX device name, IP, or server name."),
    rx_device_id: str = typer.Option(..., "--rx", help="RX device name, IP, or server name."),
    count: int = typer.Option(0, "--count", "-c", help="Number of channels to subscribe (0 = all)."),
    offset_tx: int = typer.Option(0, "--offset-tx", help="Starting TX channel offset (0-based)."),
    offset_rx: int = typer.Option(0, "--offset-rx", help="Starting RX channel offset (0-based)."),
):
    """Subscribe channels 1:1 between two devices."""

    commands = DanteDeviceCommands()

    async def _run():
        if not tx_device_id or not rx_device_id:
            typer.echo("Error: both --tx and --rx required.", err=True)
            raise typer.Exit(code=ExitCode.ERROR)

        async with _command_context() as (devices, send):
            tx_device = find_device(devices, tx_device_id)
            if tx_device is None:
                typer.echo(f"Error: TX device '{tx_device_id}' not found.", err=True)
                raise typer.Exit(code=ExitCode.ERROR)

            rx_device = find_device(devices, rx_device_id)
            if rx_device is None:
                typer.echo(f"Error: RX device '{rx_device_id}' not found.", err=True)
                raise typer.Exit(code=ExitCode.ERROR)

            tx_sorted = sorted(tx_device.tx_channels.values(), key=lambda c: c.number)
            rx_sorted = sorted(rx_device.rx_channels.values(), key=lambda c: c.number)

            if not tx_sorted:
                typer.echo(f"Error: no TX channels on {tx_device.name}.", err=True)
                raise typer.Exit(code=ExitCode.ERROR)

            if not rx_sorted:
                typer.echo(f"Error: no RX channels on {rx_device.name}.", err=True)
                raise typer.Exit(code=ExitCode.ERROR)

            tx_sorted = tx_sorted[offset_tx:]
            rx_sorted = rx_sorted[offset_rx:]

            pairs = list(zip(tx_sorted, rx_sorted))
            if count > 0:
                pairs = pairs[:count]

            if not pairs:
                typer.echo("No channel pairs to subscribe.")
                return

            arc_port = _get_arc_port(rx_device)

            for tx_ch, rx_ch in pairs:
                tx_name = tx_ch.friendly_name or tx_ch.name
                rx_name = rx_ch.friendly_name or rx_ch.name
                try:
                    packet, _ = commands.command_add_subscription(
                        rx_ch.number, tx_name, tx_device.name
                    )
                    await send(packet, rx_device.ipv4, arc_port)
                    typer.echo(f"{rx_name}@{rx_device.name} <- {tx_name}@{tx_device.name}")
                except Exception as e:
                    typer.echo(f"FAILED {rx_name}@{rx_device.name} <- {tx_name}@{tx_device.name}: {e}", err=True)

    asyncio.run(_run())


@app.command()
def fromxml(
    xmlfile: Path = typer.Option(..., "--xmlfile", help="Path to XML preset file exported from Dante Controller."),
):
    """Apply subscriptions from a Dante Controller XML preset file.

    Compares the XML desired state against live subscriptions:
    - Matching subscriptions are left untouched (no audio cut)
    - Extra subscriptions not in the XML are removed
    - Missing subscriptions from the XML are added
    """

    commands = DanteDeviceCommands()

    async def _run():
        try:
            tree = ET.parse(xmlfile)
            root = tree.getroot()
        except Exception as e:
            typer.echo(f"Error: failed to parse XML file: {e}", err=True)
            raise typer.Exit(code=ExitCode.ERROR)

        # Build desired state: dict keyed by (rx_device, rx_channel) -> (tx_device, tx_channel)
        desired = {}

        for device_elem in root.findall("device"):
            device_name = device_elem.findtext("name")
            if not device_name:
                continue

            for rxchannel_elem in device_elem.findall("rxchannel"):
                rx_channel_name = rxchannel_elem.findtext("name")
                subscribed_device = rxchannel_elem.findtext("subscribed_device")
                subscribed_channel = rxchannel_elem.findtext("subscribed_channel")

                if not subscribed_device or not subscribed_channel:
                    continue

                desired[(device_name, rx_channel_name)] = (subscribed_device, subscribed_channel)

        if not desired:
            typer.echo("No subscriptions found in XML file.")
            return

        typer.echo(f"Found {len(desired)} subscription(s) in XML.")

        async with _command_context() as (devices, send):
            # Build current state from live subscriptions
            current = {}
            for _, device in sort_devices(devices):
                for sub in device.subscriptions:
                    if sub.tx_channel_name and sub.tx_device_name:
                        current[(sub.rx_device_name, sub.rx_channel_name)] = (
                            sub.tx_device_name,
                            sub.tx_channel_name,
                        )

            # Determine what to skip, remove, and add
            to_skip = []
            to_remove = []
            to_add = []

            # Subscriptions in current but not in desired (or different) -> remove
            for key, cur_tx in current.items():
                if key in desired and desired[key] == cur_tx:
                    to_skip.append(key)
                elif key in desired:
                    # Same RX channel but different TX source -> remove then re-add
                    to_remove.append(key)
                else:
                    to_remove.append(key)

            # Subscriptions in desired but not currently matching -> add
            for key in desired:
                if key not in current or current[key] != desired[key]:
                    to_add.append(key)

            if to_skip:
                typer.echo(f"Keeping {len(to_skip)} already-matching subscription(s).")
            for key in to_skip:
                tx = desired[key]
                typer.echo(f"  KEEP {key[1]}@{key[0]} <- {tx[1]}@{tx[0]}")

            # Remove first to free up RX channels before re-adding
            if to_remove:
                typer.echo(f"Removing {len(to_remove)} subscription(s)...")
            for key in to_remove:
                rx_device = find_device(devices, key[0])
                if rx_device is None:
                    typer.echo(f"Warning: RX device '{key[0]}' not found, skipping removal.", err=True)
                    continue
                rx_channel = find_channel(rx_device, key[1], "rx")
                if rx_channel is None:
                    typer.echo(f"Warning: RX channel '{key[1]}' not found on {rx_device.name}, skipping removal.", err=True)
                    continue
                try:
                    packet, _ = commands.command_remove_subscription(rx_channel.number)
                    arc_port = _get_arc_port(rx_device)
                    await send(packet, rx_device.ipv4, arc_port)
                    cur_tx = current.get(key)
                    tx_label = f" <- {cur_tx[1]}@{cur_tx[0]}" if cur_tx else ""
                    typer.echo(f"  REMOVE {key[1]}@{key[0]}{tx_label}")
                except Exception as e:
                    typer.echo(f"  FAILED removing {key[1]}@{key[0]}: {e}", err=True)

            # Add new subscriptions
            if to_add:
                typer.echo(f"Adding {len(to_add)} subscription(s)...")
            for key in to_add:
                tx = desired[key]
                rx_device = find_device(devices, key[0])
                if rx_device is None:
                    typer.echo(f"Warning: RX device '{key[0]}' not found, skipping.", err=True)
                    continue
                tx_device = find_device(devices, tx[0])
                if tx_device is None:
                    typer.echo(f"Warning: TX device '{tx[0]}' not found, skipping.", err=True)
                    continue
                rx_channel = find_channel(rx_device, key[1], "rx")
                if rx_channel is None:
                    typer.echo(f"Warning: RX channel '{key[1]}' not found on {rx_device.name}, skipping.", err=True)
                    continue
                tx_channel = find_channel(tx_device, tx[1], "tx")
                if tx_channel is None:
                    typer.echo(f"Warning: TX channel '{tx[1]}' not found on {tx_device.name}, skipping.", err=True)
                    continue
                try:
                    tx_channel_name = tx_channel.friendly_name or tx_channel.name
                    packet, _ = commands.command_add_subscription(
                        rx_channel.number, tx_channel_name, tx_device.name
                    )
                    arc_port = _get_arc_port(rx_device)
                    await send(packet, rx_device.ipv4, arc_port)
                    typer.echo(f"  ADD {rx_channel.name}@{rx_device.name} <- {tx_channel.name}@{tx_device.name}")
                except Exception as e:
                    typer.echo(f"  FAILED {key[1]}@{key[0]} <- {tx[1]}@{tx[0]}: {e}", err=True)

            if not to_remove and not to_add:
                typer.echo("All subscriptions already match, nothing to do.")

            typer.echo("Subscriptions applied.")

    asyncio.run(_run())
