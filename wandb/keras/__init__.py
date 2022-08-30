"""
Compatibility keras module.

In the future use:
    from wandb.integration.keras import WandbCallback
"""

from wandb.integration.keras import WandbCallback  # type: ignore
from wandb.integration.keras import WandbModelCheckpoint  # type: ignore


__all__ = [
    "WandbCallback",
    "WandbModelCheckpoint"
]
