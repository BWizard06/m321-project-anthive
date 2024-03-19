import io
import json
import selectors
import struct
import sys


class Message:
    """
    constructor for super-class
    """
    def __init__(self, selector, socket, ipaddr):
        self._selector = selector
        self._socket = socket
        self._ipaddr = ipaddr
        self._event = ''
        self._recv_buffer = b''
        self._send_buffer = b''
        self._request = None
        self._jsonheader_len = None
        self._jsonheader = None

    def process_events(self, mask):
        """
        process the events
        :param mask:
        :return:
        """
        if mask & selectors.EVENT_READ:
            self._process_read()
        if mask & selectors.EVENT_WRITE:
            self._process_write()

    def set_selector_events_mask(self, mode):
        """
        Set selector to listen for events: .
        :param mode: mode is 'r', 'w', or 'rw'
        :return:
        """
        if mode == 'r':
            events = selectors.EVENT_READ
        elif mode == 'w':
            events = selectors.EVENT_WRITE
        elif mode == 'rw':
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f'Invalid events mask mode {mode!r}.')
        self._selector.modify(self._socket, events, data=self)

    def _process_headers(self):
        """
        process the protocol and json headers
        :return:
        """
        self._event = 'READ'
        self._read()

        if self._jsonheader_len is None:
            self._process_protoheader()

        if self._jsonheader_len is not None:
            if self._jsonheader is None:
                self._process_jsonheader()

    def _process_read(self):
        """
        dummy implementation must be implemented in the child class
        :return:
        """
        raise NotImplementedError

    def _read(self):
        """
        reads the data from the socket
        :return: None
        """
        try:
            # Should be ready to read
            data = self._socket.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:
            if data:
                self._recv_buffer += data
            else:
                raise RuntimeError('Peer closed.')

    def _create_response_json_content(self):
        content_encoding = 'utf-8'
        content = json_encode(self._response, content_encoding)

        response = {
            'content_bytes': content,
            'content_type': 'text/json',
            'content_encoding': content_encoding,
        }

        return response

    def _create_response_text_content(self):
        response = {
            'content_bytes': bytes(self._response, 'utf-8'),
            'content_type': 'text/plain',
            'content_encoding': 'utf-8',
        }
        return response

    def _process_write(self):
        """
        dummy implementation must be implemented in the child class
        :return:
        """
        raise NotImplementedError

    def _write(self):
        """
        sends the response to the client
        :return:
        """
        if self._send_buffer:
            print(f'Sending {self._send_buffer!r} to {self._ipaddr}')
            try:
                sent = self._socket.send(self._send_buffer)
            except BrokenPipeError:
                print('Failed to send data: broken pipe')
            else:
                self._send_buffer = self._send_buffer[sent:]
                # Close when the buffer is drained. The response has been sent.
                if type(self).__name__ == 'ServerMessage' and \
                        sent and \
                        not self._send_buffer:
                    self.close()

    def _process_protoheader(self):
        """
        process the protocol header
        :return:
        """
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader_len = struct.unpack(
                '>H', self._recv_buffer[:hdrlen]
            )[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def _process_jsonheader(self):
        """
        process the json header
        :return:
        """
        hdrlen = self._jsonheader_len
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader = json_decode(
                self._recv_buffer[:hdrlen], 'utf-8'
            )
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for reqhdr in (
                    'byteorder',
                    'content-length',
                    'content-type',
                    'content-encoding',
            ):
                if reqhdr not in self._jsonheader:
                    raise ValueError(f'Missing required header "{reqhdr}".')

    def _create_message(
            self,
            *,
            content_bytes,
            content_type,
            content_encoding
    ):
        """
        creates the encoded message to send to the client
        :param content_bytes:
        :param content_type:
        :param content_encoding:
        :return:
        """

        jsonheader = {
            'byteorder': sys.byteorder,
            'content-type': content_type,
            'content-encoding': content_encoding,
            'content-length': len(content_bytes),
        }
        jsonheader_bytes = json_encode(jsonheader, 'utf-8')
        message_hdr = struct.pack('>H', len(jsonheader_bytes))

        response_message = message_hdr + jsonheader_bytes + content_bytes
        return response_message

    def close(self):
        print(f'Closing connection to {self._ipaddr}')
        try:
            self._selector.unregister(self._socket)
        except Exception as e:
            print(
                f'Error: selector.unregister() exception for '
                f'{self._ipaddr}: {e!r}'
            )

        try:
            self._socket.close()
        except OSError as e:
            print(f'Error: socket.close() exception for {self._ipaddr}: {e!r}')
        finally:
            # Delete reference to socket object for garbage collection
            self._socket = None

    @property
    def ipaddr(self):
        return self._ipaddr

    @ipaddr.setter
    def ipaddr(self, value):
        self._ipaddr = value

    @property
    def event(self):
        return self._event

    @event.setter
    def event(self, value):
        self._event = value

    @property
    def request(self):
        return self._request

    @property
    def response(self):
        return self._response

    @response.setter
    def response(self, value):
        self._response = value


def json_encode(obj, encoding):
    """
    encodes the object as json
    :param obj: the object to encode
    :param encoding: the codec to use for encoding
    :return: String
    """
    return json.dumps(obj, ensure_ascii=False).encode(encoding)


def json_decode(json_bytes, encoding):
    """
    decodes json data into an object
    :param json_bytes: the json data to be decoded
    :param encoding: the codec to use for decoding
    :return: Object
    """
    text_io_wrap = io.TextIOWrapper(
        io.BytesIO(json_bytes), encoding=encoding, newline=''
    )
    obj = json.load(text_io_wrap)
    text_io_wrap.close()
    return obj
