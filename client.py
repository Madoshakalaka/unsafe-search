import mimetypes
import os
import shutil
import sys
from http.client import HTTPSConnection
from base64 import b64encode
from json import loads
from json import dumps
import time
from pathlib import Path
import requests
from tqdm import tqdm

class RestClient:
    domain = "api.dataforseo.com"

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def request(self, path, method, data=None):
        connection = HTTPSConnection(self.domain)
        try:
            base64_bytes = b64encode(
                ("%s:%s" % (self.username, self.password)).encode("ascii")
            ).decode("ascii")
            headers = {'Authorization': 'Basic %s' % base64_bytes, 'Content-Encoding': 'gzip'}
            connection.request(method, path, headers=headers, body=data)
            response = connection.getresponse()
            return loads(response.read().decode())
        finally:
            connection.close()

    def get(self, path):
        return self.request(path, 'GET')

    def post(self, path, data):
        if isinstance(data, str):
            data_str = data
        else:
            data_str = dumps(data)
        return self.request(path, 'POST', data_str)


client = RestClient(os.environ.get("DFS_USERNAME"), os.environ.get("DFS_PASSWORD"))


class UnsafeSearcher:

    def __init__(self):
        self.safe_id = None
        self.unsafe_id = None
        self.safe_urls = set()
        self.unsafe_urls = set()
        self.funky_urls = set()

    def get_funky(self, keyword):
        x = client.post("https://api.dataforseo.com/v3/serp/google/images/task_post",
                        {0: dict(language_code="en", location_code=2840, keyword=keyword, depth=700,
                                 search_param="&safe=active"),
                         1: dict(language_code="en", location_code=2840, keyword=keyword, depth=300,
                                 search_param="&safe=off")})
        self.safe_id = x["tasks"][0]["id"]
        self.unsafe_id = x["tasks"][1]["id"]
        print("task posted")
        # print("safe_id: ", self.safe_id)
        # print("unsafe_id: ", self.unsafe_id)

        print("waiting for tasks to finish (timeout = 5 minutes)...")
        time.sleep(5)

        time_elapsed = 0
        while 1:
            try:
                safe_response = client.get(f"/v3/serp/google/images/task_get/advanced/{self.safe_id}")
                unsafe_response = client.get(f"/v3/serp/google/images/task_get/advanced/{self.unsafe_id}")

                self.safe_urls = set([item["source_url"] for item in safe_response["tasks"][0]["result"][0]["items"]])
                self.unsafe_urls = set([item["source_url"] for item in unsafe_response["tasks"][0]["result"][0]["items"]])
            except:
                print("polling...")
                time.sleep(5)
                time_elapsed += 5
                if time_elapsed >= 300:
                    print("Timed Out")
                    sys.exit(1)
            else:
                break

        self.funky_urls = self.unsafe_urls - self.safe_urls

        print(f"Successfully harvested {len(self.funky_urls)} funky images")
        os.makedirs(keyword, exist_ok=True)
        print("Downloading...")

        for i, url in tqdm(list(enumerate(self.funky_urls))):
            try:
                resp = requests.get(url, stream=True)
                content_type = resp.headers['content-type']
                extension = mimetypes.guess_extension(content_type)
                local_file = open(Path(keyword) / f"{i}{extension}", "wb")
                resp.raw.decode_content = True
                shutil.copyfileobj(resp.raw, local_file)
                del resp
            except:
                print(f"Failed to download: {url}")
                continue


us = UnsafeSearcher()