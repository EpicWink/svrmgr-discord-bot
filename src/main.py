"""Manage EC2 instances as a Discord bot."""

import base64
import dataclasses
import enum
import functools
import json
import logging
import os
import typing as t

import boto3
import botocore.config
import nacl.exceptions
import nacl.signing

PUBLIC_KEY = os.environ.get("SVRMGR_DISCORD_APP_PUBLIC_KEY")
TAG_KEY = "svrmgr-message-id"

logging.root.setLevel(logging.DEBUG)
logging.getLogger("boto3").setLevel(logging.INFO)
logging.getLogger("botocore").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

ec2_client = boto3.client(
    "ec2", config=botocore.config.Config(retries=dict(mode="adaptive"))
)

verify_key: nacl.signing.VerifyKey | None = None
if PUBLIC_KEY:
    verify_key = nacl.signing.VerifyKey(bytes.fromhex(PUBLIC_KEY))


@dataclasses.dataclass(slots=True)
class HTTPRequest:
    """HTTP request details."""

    method: str
    path: str
    query_parameters: t.Dict[str, str] | None
    headers: t.Dict[str, str] = dataclasses.field(repr=False)
    body: bytes | None = dataclasses.field(repr=False)

    @classmethod
    def from_lambda_event(cls, event: t.Dict[str, t.Any]) -> "HTTPRequest":
        body_json = t.cast(str | None, event.get("body"))

        body = None
        if body_json is not None:
            body = body_json.encode(encoding="utf-8")
            if event["isBase64Encoded"]:
                body = base64.b64decode(body)

        return cls(
            method=event["requestContext"]["http"]["method"],
            path=event["rawPath"],
            query_parameters=event.get("queryStringParameters"),
            headers=event["headers"],
            body=body,
        )

    def get_header(self, name: str) -> str | None:
        return next(
            (v for k, v in self.headers.items() if k.lower() == name.lower()), None
        )

    def get_json_body_data(self) -> t.Any:
        if self.body is None:
            return None
        return json.loads(self.body.decode(encoding="utf-8"))


@dataclasses.dataclass(slots=True)
class HTTPResponse:
    """HTTP response details."""

    status_code: int
    headers: t.Dict[str, str] = dataclasses.field(repr=False)
    body: bytes | None = dataclasses.field(repr=False)

    @classmethod
    def from_exception(cls, exception: Exception) -> "HTTPResponse":
        if isinstance(exception, HTTPError):
            return exception.to_response()

        body_text = f"{exception.__class__.__name__}: {exception}"

        return cls(
            status_code=500,
            headers={"Content-Type": "text/plain; charset=utf-8"},
            body=body_text.encode(encoding="utf-8"),
        )

    @classmethod
    def from_json_body_data(cls, status_code: int, data: t.Any) -> "HTTPResponse":
        return cls(
            status_code=status_code,
            headers={"Content-Type": "application/json; charset=utf-8"},
            body=json.dumps(data).encode(encoding="utf-8"),
        )

    def to_lambda_result(self) -> t.Dict[str, t.Any]:
        result = {"statusCode": self.status_code, "headers": self.headers}

        if self.status_code != 204:
            if not self.body:
                raise RuntimeError(
                    f"Response status must be 204 (not {self.status_code}) when body "
                    f"isn't provided"
                )

            content_type_header = next(
                (v for k, v in self.headers.items() if k.lower() == "content-type"), ""
            )
            body_is_binary = not (
                content_type_header.startswith("text/")
                or content_type_header.startswith("application/json")
            )
            result["isBase64Encoded"] = body_is_binary

            body_bytes = self.body
            if body_is_binary:
                body_bytes = base64.b64encode(body_bytes)

            result["body"] = body_bytes.decode(encoding="utf-8")

        return result


@dataclasses.dataclass
class HTTPError(Exception):
    """Exception to convert into an HTTP error response."""

    message: str
    status_code: int

    def __post_init__(self):
        super().__init__()

    def to_response(self) -> HTTPResponse:
        return HTTPResponse(
            status_code=self.status_code,
            headers={"Content-Type": "text/plain; charset=utf-8"},
            body=self.message.encode(encoding="utf-8"),
        )


class NotManaged(Exception):
    """Server is not managed by svrmgr."""


class InstanceState(enum.Enum):
    """EC2 instance running status."""

    pending = "pending"
    running = "running"
    shutting_down = "shutting-down"
    terminated = "terminated"
    stopping = "stopping"
    stopped = "stopped"


@dataclasses.dataclass(slots=True)
class Instance:
    """EC2 instance details."""

    id: str
    tags: t.Dict[str, str]
    state: InstanceState | None = None


def _iter_ec2_response_pages(
    client_fn: t.Callable[..., t.Dict[str, t.Any]],
    items_key: str,
) -> t.Generator[t.Any, None, None]:
    """Iterate over items from EC2 service response pages.

    Args:
        client_fn: EC2 service client method
        items_key: key in response which houses items

    Yields:
        items in all pages
    """

    # Get first page
    response = client_fn()
    yield from response.get(items_key) or []

    # Get subsequent pages
    while response.get("NextToken"):
        logger.debug("Received page token, getting next page")
        response = client_fn(NextToken=response["NextToken"])
        yield from response.get(items_key) or []


def list_instances() -> t.List[Instance]:
    """List managed EC2 instances.

    Discover EC2 instances by listing tags.

    Returns:
        EC2 instance details
    """

    # List EC2 instance tags
    tag_keys = [TAG_KEY, "Name"]
    describe_tags = functools.partial(
        ec2_client.describe_tags,
        Filters=[
            dict(Name="resource-type", Values=["instance"]),
            dict(Name="key", Values=tag_keys),
        ],
    )

    logger.info(f"Listing EC2 instance tags with name on of: {', '.join(tag_keys)}")
    tags = _iter_ec2_response_pages(describe_tags, items_key="Tags")

    # Group tags by instance
    tags_by_instance = {}
    for tag in tags:
        tags_for_instance = tags_by_instance.get(tag["ResourceId"])
        if not tags_for_instance:
            tags_for_instance = tags_by_instance[tag["ResourceId"]] = {}

        tags_for_instance[tag["Key"]] = tag["Value"]

    return [
        Instance(instance_id, tags) for instance_id, tags in tags_by_instance.items()
    ]


def get_instances_state(instances: t.List[Instance]) -> None:
    """Get EC2 instances' running states.

    Args:
        instances: details of EC2 instances to get running states for,
            modified in-place
    """

    # Get instance statuses
    describe_instance_status = functools.partial(
        ec2_client.describe_instance_status,
        InstanceIds=[i.id for i in instances],
        IncludeAllInstances=True,
    )

    logger.info(f"Listing status of {len(instances)} EC2 instances")
    instance_statuses = _iter_ec2_response_pages(
        describe_instance_status, items_key="InstanceStatuses"
    )
    instance_statuses_by_instance_id = {i["InstanceId"]: i for i in instance_statuses}

    # Update with instance stae
    for instance in instances:
        instance.state = InstanceState(
            instance_statuses_by_instance_id[instance.id]["InstanceState"]["Name"],
        )


def get_message_id_for_instance(instance_id: str) -> int:
    """Get Discord message ID managing EC2 instance.

    Gets the value of the tag with key `TAG_KEY` for the instance.

    Args:
        instance_id: EC2 instance ID

    Returns:
        Discord message ID

    Raises:
        NotManaged: if instance is not managed by svrmgr
    """

    logger.info(f"Getting tags of EC2 instance {instance_id!r} with key {TAG_KEY!r}")
    response = ec2_client.describe_tags(
        Filters=[
            dict(Name="resource-id", Values=[instance_id]),
            dict(Name="resource-type", Values=["instance"]),
            dict(Name="key", Values=[TAG_KEY]),
        ],
    )

    tags = response.get("Tags") or []

    if not tags:
        raise NotManaged(
            f"EC2 instance {instance_id!r} is not managed by any Discord message"
        )
    elif len(tags) > 2:
        # impossibru!
        raise RuntimeError(
            f"Found multiple tags on EC2 instance {instance_id!r} with key {TAG_KEY!r}"
        )

    return tags[0]["Value"]


def start_instance(instance_id: str) -> None:
    """Start EC2 instance.

    Args:
        instance_id: ID of instance start
    """

    logger.info(f"Starting EC2 instance {instance_id!r}")
    ec2_client.start_instances(InstanceIds=[instance_id])


def stop_instance(instance_id: str) -> None:
    """Stop EC2 instance.

    Args:
        instance_id: ID of instance stop
    """

    logger.info(f"Stopping EC2 instance {instance_id!r}")
    ec2_client.stop_instances(InstanceIds=[instance_id])


def verify_discord_request_auth(request: HTTPRequest) -> None:
    """Verify authenticity of Discord request.

    Skips verification if `verify_key` isn't set.

    Args:
        request: request to verify
    """

    if verify_key is None:
        logger.warning("Skipping request auth verification: public key no provided")
        return

    signature = bytes.fromhex(request.get_header("X-Signature-Ed25519") or "")
    timestamp = (request.get_header("X-Signature-Timestamp") or "").encode(
        encoding="utf-8",
    )
    message = timestamp + (request.body or b"")

    if not message:
        raise HTTPError("missing request signature", status_code=401) from None

    try:
        verify_key.verify(message, signature)
    except nacl.exceptions.BadSignatureError:
        raise HTTPError("invalid request signature", status_code=401) from None


def handle_request(request: HTTPRequest) -> HTTPResponse:
    """Handle Discord interaction HTTP request.

    Args:
        request: details of request to handle

    Returns:
        HTTP response details
    """

    # Parse request
    verify_discord_request_auth(request)

    request_data = request.get_json_body_data()

    if not isinstance(request_data, dict):
        raise HTTPError("Bad request body: not an object", status_code=400)

    # Get Discord interaction type
    interaction_type = t.cast(int, request_data.get("type"))
    if interaction_type is None:
        raise HTTPError("Bad request body: missing type", status_code=400)

    # Acknowledge a ping
    if interaction_type == 1:  # PING
        response_data = {"type": 1}  # PONG
        return HTTPResponse.from_json_body_data(status_code=200, data=response_data)

    # Only accept message-component interactions
    if interaction_type != 3:  # not MESSAGE_COMPONENT
        raise HTTPError("Unsupported interaction type", status_code=400)

    # Get source Discord message ID
    message_id = t.cast(int, (request_data.get("message") or {}).get("id"))
    if message_id is None:
        raise HTTPError("Bad request body: missing message ID", status_code=400)

    # Get source button
    custom_id = t.cast(str, (request_data.get("data") or {}).get("custom_id"))
    if not custom_id:
        raise HTTPError(
            "Bad request body: missing component custom ID", status_code=400
        )

    # Start/stop EC2 instance
    if custom_id.split(":")[0] in ["start", "stop"]:
        action, instance_id = custom_id.split(":", maxsplit=1)

        try:
            instance_message_id = get_message_id_for_instance(instance_id)
        except NotManaged:
            raise HTTPError(
                "Not allowed: instance doesn't exist or isn't managed by svrmgr",
                status_code=403,
            ) from None

        if instance_message_id != message_id:
            raise HTTPError(
                "Not allowed: instance isn't managed by this message", status_code=403
            ) from None

        if action == "start":
            start_instance(instance_id)
        else:
            assert action == "stop"
            stop_instance(instance_id)
    elif custom_id != "refresh" and custom_id.split(":")[0] != "refresh":
        raise HTTPError("Unknown component custom ID", status_code=400)

    # List EC2 instances
    instances = list_instances()

    instances = [i for i in instances if i.tags.get(TAG_KEY) == message_id]
    instances = sorted(instances, key=lambda x: x.tags.get("Name") or x.id)

    get_instances_state(instances)

    # Build message
    server_components = [
        {"type": 1, "components": [
            {"type": 2, "label": "\u21bb", "style": 2, "custom_id": "refresh"},
        ]},
    ]  # fmt: skip

    for instance in instances:
        name = instance.tags.get("Name") or instance.id
        if instance.state == InstanceState.stopped:
            style = 3
            custom_id = f"start:{instance.id}"
            label = f"Start {name}"
        elif instance.state == InstanceState.running:
            style = 4
            custom_id = f"stop:{instance.id}"
            label = f"Stop {name}"
        else:
            style = 2
            custom_id = f"refresh:{instance.id}"
            label = f"{name} ({instance.state and instance.state.value or 'unknown'})"

        server_components.append(
            {"type": 1, "components": [
                {"type": 2, "label": label, "style": style, "custom_id": custom_id},
            ]},
        )  # fmt: skip

    # Return message-update eresponse
    response_data = {
        "type": 7,  # UPDATE_MESSAGE
        "data": {"content": "Servers", "components": server_components},
    }

    return HTTPResponse.from_json_body_data(status_code=200, data=response_data)


def main(event: t.Dict[str, t.Any], _: t.Any) -> t.Dict[str, t.Any]:
    logger.debug("Parsing input event as HTTP request")
    request = HTTPRequest.from_lambda_event(event)
    logger.info(f"Received HTTP request: {request}")

    try:
        response = handle_request(request)
    except Exception as e:
        logger.error("Request handling failed", exc_info=e)
        response = HTTPResponse.from_exception(e)

    logger.info(f"Returning HTTP response: {response}")
    return response.to_lambda_result()
