from app import app
import requests
from urllib.parse import urljoin
import os
import os.path


def download_resource(url, path):
    response = requests.get(urljoin(app.config['SITE_URL'], url),
                            stream=True)

    if response.status_code // 2 == 100:
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        with open(path, 'wb') as f:
            for chunk in response.iter_content(512):
                f.write(chunk)

        return True
    else:
        app.logger.warn("Failed to download resource %s. Got response %s",
                        url, str(response))
