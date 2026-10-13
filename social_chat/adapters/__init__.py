"""The platforms this plugin reads, in the order the panel lists them.

To add one, write a module with an `Adapter` subclass and put the class in
ADAPTERS. docs/adapters.md has the whole recipe.
"""
from .youtube import YouTube
from .twitch import Twitch
from .facebook import Facebook
from .webhook import Webhook
from .x_stub import X
from .practice import Practice

ADAPTERS = [YouTube, Twitch, Facebook, Webhook, X, Practice]
