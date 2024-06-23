import json

from asyncio import Future
from dataclasses import dataclass, field
from typing import Dict, Optional

from nats.aio.client import Client
from nats.aio.msg import Msg
from nats.errors import *
from nats.jetstream.api import *
from nats.jetstream.errors import *
from nats.jetstream.message import *

DEFAULT_RETRY_ATTEMPTS = 2

@dataclass
class PubAck:
    """
    PubAck is an ack received after successfully publishing a message.
    """
    stream: str = field(metadata={"json": "stream"})
    """
    The stream name the message was published to.
    """
    sequence: int = field(metadata={"json": "seq"})
    """
    The sequence number of the message.
    """
    duplicate: bool = field(metadata={"json": "duplicate"})
    """
    Indicates whether the message was a duplicate.
    """
    domain: Optional[str] = field(metadata={"json": "domain"})
    """
    The domain the message was published to.
    """

class Publisher:
    def __init__(self, client: Client, timeout: float = 1):
        self._client = client
        self._timeout = timeout

    @property
    def timeout(self) -> float:
        return self._timeout

    @property
    def client(self) -> Client:
        return self._client

    async def publish(
        self,
        subject: str,
        payload: bytes = b'',
        id: Optional[str] = None,
        timeout: Optional[float] = None,
        headers: Optional[Dict] = None,
        expected_last_msg_id: Optional[str] = None,
        expected_stream: Optional[str] = None,
        expected_last_sequence: Optional[int] = None,
        expected_last_subject_sequence: Optional[int] = None,
        retry_attempts: int = 2,
        retry_wait: float = 0.25,
    ) -> PubAck:
        """
        Performs a publish to a stream and waits for ack from server.
        """

        if timeout is None:
            timeout = self.timeout

        extra_headers = {}
        if expected_last_msg_id is not None:
            extra_headers[Header.EXPECTED_LAST_MSG_ID] = str(expected_last_msg_id)

        if expected_stream is not None:
            extra_headers[Header.EXPECTED_STREAM] = str(expected_stream)

        if expected_last_sequence is not None:
            extra_headers[Header.EXPECTED_LAST_SEQ] = str(expected_last_sequence)

        if expected_last_subject_sequence is not None:
            extra_headers[Header.EXPECTED_LAST_SUBJECT_SEQUENCE] = str(expected_last_subject_sequence)

        if len(extra_headers) > 0:
            if headers is not None:
                extra_headers.update(headers)

            headers = extra_headers

        for attempt in range(0, retry_attempts):
            try:
                msg = await self.client.request(
                    subject,
                    payload,
                    timeout=timeout,
                    headers=headers,
                )

                pub_ack = parse_json_response(msg.data, PubAck)
                if pub_ack.stream == None:
                    raise InvalidAckError()

                return pub_ack
            except NoRespondersError:
                if attempt < retry_attempts - 1:
                    await asyncio.sleep(retry_wait)

        raise NoStreamResponseError
