import logging
from collections.abc import Iterator
from contextlib import contextmanager

from daytona import (
    CreateSandboxFromImageParams,
    Daytona,
    DaytonaConfig,
    DaytonaError,
    Sandbox,
)

from config.constants import LogMessages
from config.settings import DaytonaSettings, SweBenchSettings

logger = logging.getLogger(__name__)


def make_daytona(settings: DaytonaSettings) -> Daytona:
    return Daytona(
        DaytonaConfig(
            api_key=settings.daytona_api_key.get_secret_value(),
            api_url=settings.daytona_api_url,
        )
    )


def task_image(instance_id: str, settings: SweBenchSettings) -> str:
    """The official SWE-bench eval image for one task."""
    instance = instance_id.replace(
        settings.instance_separator, settings.image_separator
    )
    return settings.image_template.format(instance=instance).lower()


@contextmanager
def task_sandbox(
    daytona: Daytona,
    instance_id: str,
    settings: SweBenchSettings,
    block_network: bool = True,
) -> Iterator[Sandbox]:
    """
    One sandbox for one task, deleted when the block ends. The agent gets no
    network; grading needs it because the eval script reinstalls the repo.
    """
    image = task_image(instance_id, settings)
    logger.info(LogMessages.SANDBOX_CREATING, extra={"image": image})
    sandbox = daytona.create(
        CreateSandboxFromImageParams(
            image=image, network_block_all=block_network, ephemeral=True
        ),
        timeout=settings.sandbox_create_timeout_seconds,
    )
    try:
        yield sandbox
    finally:
        try:
            # an ephemeral sandbox is deleted when it stops, so stopping is
            # enough, and it needs only write access, not delete
            sandbox.stop()
        except DaytonaError:
            # Daytona's auto-stop (15 min) still stops, and so deletes, it
            logger.exception(
                LogMessages.SANDBOX_STOP_FAILED, extra={"sandbox": sandbox.id}
            )
