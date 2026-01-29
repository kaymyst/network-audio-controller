import asyncio
import xml.etree.ElementTree as ET

from cleo.commands.command import Command
from cleo.helpers import option

from netaudio.dante.browser import DanteBrowser


class SubscriptionFromXmlCommand(Command):
    name = "fromxml"
    description = "Add subscriptions from XML preset file"

    options = [
        option(
            "xmlfile",
            None,
            "Path to XML preset file containing subscription definitions",
            flag=False,
            value_required=True,
        ),
    ]

    async def subscription_fromxml(self):
        xmlfile = self.option("xmlfile")

        if not xmlfile:
            self.line("<error>--xmlfile is required</error>")
            return

        try:
            tree = ET.parse(xmlfile)
            root = tree.getroot()
        except Exception as e:
            self.line(f"<error>Failed to parse XML file: {e}</error>")
            return

        # Get all devices from the network
        dante_browser = DanteBrowser(mdns_timeout=1.5)
        dante_devices = await dante_browser.get_devices()

        for _, device in dante_devices.items():
            await device.get_controls()

        # Parse XML and find subscriptions
        subscriptions_to_add = []

        for device_elem in root.findall("device"):
            device_name = device_elem.findtext("name")
            
            if not device_name:
                continue

            # Find this device in our network devices
            rx_device = None
            for _, dev in dante_devices.items():
                if dev.name == device_name:
                    rx_device = dev
                    break

            if not rx_device:
                self.line(f"<comment>Device '{device_name}' not found on network, skipping</comment>")
                continue

            # Check each rxchannel for subscriptions
            for rxchannel_elem in device_elem.findall("rxchannel"):
                channel_name = rxchannel_elem.findtext("name")
                subscribed_device = rxchannel_elem.findtext("subscribed_device")
                subscribed_channel = rxchannel_elem.findtext("subscribed_channel")

                # Skip if not fully subscribed
                if not subscribed_device or not subscribed_channel:
                    continue

                subscriptions_to_add.append({
                    "rx_device_name": device_name,
                    "rx_channel_name": channel_name,
                    "tx_device_name": subscribed_device,
                    "tx_channel_name": subscribed_channel,
                })

        # Apply subscriptions
        if not subscriptions_to_add:
            self.line("<info>No subscriptions found in XML file</info>")
            return

        self.line(f"<info>Found {len(subscriptions_to_add)} subscription(s) in XML</info>")

        for sub in subscriptions_to_add:
            try:
                rx_device = None
                tx_device = None
                rx_channel = None
                tx_channel = None

                # Find rx device
                for _, dev in dante_devices.items():
                    if dev.name == sub["rx_device_name"]:
                        rx_device = dev
                        break

                if not rx_device:
                    self.line(
                        f"<error>RX device '{sub['rx_device_name']}' not found</error>"
                    )
                    continue

                # Find tx device
                for _, dev in dante_devices.items():
                    if dev.name == sub["tx_device_name"]:
                        tx_device = dev
                        break

                if not tx_device:
                    self.line(
                        f"<error>TX device '{sub['tx_device_name']}' not found</error>"
                    )
                    continue

                # Find rx channel
                for _, chan in rx_device.rx_channels.items():
                    if chan.name == sub["rx_channel_name"]:
                        rx_channel = chan
                        break

                if not rx_channel:
                    self.line(
                        f"<error>RX channel '{sub['rx_channel_name']}' not found on {sub['rx_device_name']}</error>"
                    )
                    continue

                # Find tx channel
                for _, chan in tx_device.tx_channels.items():
                    if chan.name == sub["tx_channel_name"] or chan.friendly_name == sub["tx_channel_name"]:
                        tx_channel = chan
                        break

                if not tx_channel:
                    self.line(
                        f"<error>TX channel '{sub['tx_channel_name']}' not found on {sub['tx_device_name']}</error>"
                    )
                    continue

                # Add subscription
                self.line(
                    f"<info>Adding: {rx_channel.name}@{rx_device.name} <- {tx_channel.name}@{tx_device.name}</info>"
                )
                await rx_device.add_subscription(rx_channel, tx_channel, tx_device)

            except Exception as e:
                self.line(
                    f"<error>Failed to add subscription {sub}: {e}</error>"
                )

        self.line("<info>Subscriptions applied</info>")

    def handle(self):
        asyncio.run(self.subscription_fromxml())
