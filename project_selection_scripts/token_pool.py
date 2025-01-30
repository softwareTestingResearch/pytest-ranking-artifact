import datetime
import json
import time

import requests


def is_corner_case(message):
    if "No commit found for SHA" in message:
        return True
    return False


class TokenPool:
    def __init__(self):
        self.tokens = [
            # INSERT YOUR GITHUB TOKEN STRING HERE.
        ]
        assert len(self.tokens) > 0, "You need to provide GitHub API token."
        self.ptr = 0
        self.refresh_pool()

    def generate_headers(self, token):
        headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 \
                # (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                }
        return headers

    def refresh_pool(self):
        print("refreshing token counter")
        self.counter = {}
        for token in self.tokens:
            headers = self.generate_headers(token)
            html_response = requests.get(url="https://api.github.com/rate_limit", headers=headers)
            html_response = json.loads(html_response.text)
            remaining = html_response["resources"]["core"]["remaining"]
            self.counter[token] = remaining
            print(token, remaining)
        # reset pointer to the current available token
        while self.counter[self.tokens[self.ptr]] == 0:
            self.ptr += 1
            self.ptr %= len(self.tokens)
        print("resetting token pointer to", self.ptr)

    def get_next_token(self):
        if self.counter[self.tokens[self.ptr]] == 0:
            self.refresh_pool()

        token = self.tokens[self.ptr]
        print("using token", token, self.counter[token])
        headers = self.generate_headers(token)
        # update token count
        self.counter[token] -= 1

        return headers

    def check_limits(self):
        for t in self.tokens:
            headers = self.generate_headers(t)
            html_response = requests.get(url="https://api.github.com/rate_limit", headers=headers)
            html_response = json.loads(html_response.text)
            print(html_response["resources"]["core"])
        pass


def query_info(mytokenpool, myurl):
    headers = mytokenpool.get_next_token()
    html_response = requests.get(url=myurl, headers=headers)
    info = json.loads(html_response.text)
    while "state" not in info and "message" in info and not is_corner_case(info["message"]):
        print("message:", info["message"])
        print("API rate limit exceeded, sleep for 60s")
        print("current time:", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        time.sleep(60)
        mytokenpool.refresh_pool()
        headers = mytokenpool.get_next_token()
        html_response = requests.get(url=myurl, headers=headers)
        info = json.loads(html_response.text)
    return info


def query_binary(mytokenpool, myurl):
    headers = mytokenpool.get_next_token()
    html_response = requests.get(url=myurl, headers=headers)
    if html_response.status_code == 404:
        print(f"404 Page Not Found: {myurl}")
    while html_response.status_code in [403, 429]:
        print("API rate limit exceeded, sleep for 60s")
        print("current time:", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        time.sleep(60)
        mytokenpool.refresh_pool()
        headers = mytokenpool.get_next_token()
        html_response = requests.get(url=myurl, headers=headers)
        if html_response.status_code == 404:
            print(f"404 Page Not Found: {myurl}")
    return html_response.content


def post(mytokenpool, myurl):
    headers = mytokenpool.get_next_token()
    requests.post(url=myurl, headers=headers)


if __name__ == "__main__":
    pass
