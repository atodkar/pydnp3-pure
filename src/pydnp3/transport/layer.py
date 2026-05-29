"""DNP3 Transport Layer: connects link layer frames to application fragments."""

from __future__ import annotations

from collections.abc import Callable

from ..link.constants import PrimaryFunction
from ..link.frame import LinkFrame
from .reassembler import Reassembler
from .segmenter import Segmenter


class TransportLayer:
    """Bidirectional transport layer connecting link frames to application fragments.

    Receive: Extracts transport segments from link frames, reassembles into fragments.
    Transmit: Segments application fragments and wraps in link frames.
    """

    def __init__(
        self,
        on_fragment: Callable[[bytes], None],
        send_frame: Callable[[LinkFrame], None],
        local_address: int,
        remote_address: int,
    ) -> None:
        self._on_fragment = on_fragment
        self._send_frame = send_frame
        self._local_address = local_address
        self._remote_address = remote_address
        self._reassembler = Reassembler()
        self._segmenter = Segmenter()

    def reset(self) -> None:
        self._reassembler.reset()
        self._segmenter.reset()

    def on_frame_received(self, frame: LinkFrame) -> None:
        """Process a received link frame containing transport data."""
        if not frame.user_data:
            return

        fragment = self._reassembler.add_segment(frame.user_data)
        if fragment is not None:
            self._on_fragment(fragment)

    def send_fragment(self, fragment: bytes, direction: bool = False) -> None:
        """Segment and transmit a fragment as one or more link frames."""
        segments = self._segmenter.segment(fragment)
        for segment in segments:
            frame = LinkFrame.create(
                destination=self._remote_address,
                source=self._local_address,
                primary=True,
                function=PrimaryFunction.UNCONFIRMED_USER_DATA,
                user_data=segment,
                direction=direction,
            )
            self._send_frame(frame)
