import logging
import os
from typing import Any, Dict, Optional

import wandb
import wandb.docker as docker
from wandb.errors import DockerError, LaunchError
from wandb.sdk.launch.builder.abstract import AbstractBuilder
from wandb.sdk.launch.runner.aws import aws_ecr_login

from .build import (
    _create_docker_build_ctx,
    construct_local_image_uri,
    generate_dockerfile,
    validate_docker_installation,
)
from .._project_spec import (
    create_metadata_file,
    EntryPoint,
    get_entry_point_command,
    LaunchProject,
)
from ..utils import sanitize_wandb_api_key


_GENERATED_DOCKERFILE_NAME = "Dockerfile.wandb-autogenerated"
_logger = logging.getLogger(__name__)


class DockerBuilder(AbstractBuilder):
    type = "docker"

    def __init__(self, builder_config: Dict[str, Any]):
        super().__init__(builder_config)
        validate_docker_installation()

    def build_image(
        self,
        launch_project: LaunchProject,
        repository: Optional[str],
        entrypoint: EntryPoint,
        docker_args: Dict[str, Any],
    ) -> str:

        if repository:
            image_uri = f"{repository}:{launch_project.run_id}"
        else:
            image_uri = construct_local_image_uri(launch_project)
        entry_cmd = get_entry_point_command(entrypoint, launch_project.override_args)
        dockerfile_str = generate_dockerfile(
            launch_project, entrypoint, launch_project.resource, self.type
        )
        create_metadata_file(
            launch_project,
            image_uri,
            sanitize_wandb_api_key(" ".join(entry_cmd)),
            docker_args,
            dockerfile_str,
        )
        build_ctx_path = _create_docker_build_ctx(launch_project, dockerfile_str)
        dockerfile = os.path.join(build_ctx_path, _GENERATED_DOCKERFILE_NAME)
        try:
            docker.build(tags=[image_uri], file=dockerfile, context_path=build_ctx_path)
        except DockerError as e:
            raise LaunchError(f"Error communicating with docker client: {e}")

        try:
            os.remove(build_ctx_path)
        except Exception:
            _logger.info(
                "Temporary docker context file %s was not deleted.", build_ctx_path
            )

        if repository:
            reg, tag = image_uri.split(":")
            wandb.termlog(f"Pushing image {image_uri}")
            push_resp = docker.push(reg, tag)
            if push_resp is None:
                raise LaunchError("Failed to push image to repository")
            elif (
                launch_project.resource == "sagemaker"
                and f"The push refers to repository [{repository}]" not in push_resp
            ):
                raise LaunchError(f"Unable to push image to ECR, response: {push_resp}")

        return image_uri
