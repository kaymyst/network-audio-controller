from cleo.commands.command import Command
from cleo.helpers import option

from ._add import SubscriptionAddCommand
from ._fromxml import SubscriptionFromXmlCommand
from ._list import SubscriptionListCommand
from ._remove import SubscriptionRemoveCommand


class SubscriptionCommand(Command):
    name = "subscription"
    description = "Control subscriptions"
    commands = [
        SubscriptionAddCommand(),
        SubscriptionFromXmlCommand(),
        SubscriptionListCommand(),
        SubscriptionRemoveCommand(),
    ]

    def handle(self):
        return self.call("help", self._config.name)
