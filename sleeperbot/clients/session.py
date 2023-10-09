from requests import Session as _Session
from requests.adapters import (
    HTTPAdapter,
    Retry,
)


class Session(_Session):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        retry = Retry(
            total=5,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504],
        )

        self.mount("http://", HTTPAdapter(max_retries=retry))
        self.mount("https://", HTTPAdapter(max_retries=retry))

        # don't keep connections open - the point of this Session object is to
        # have common retry and error behavior not to maintain long running
        # connections
        self.headers.update({"Connection": "close"})

    def request(self, *args, **kwargs):
        response = super().request(*args, **kwargs)
        response.raise_for_status()

        return response
