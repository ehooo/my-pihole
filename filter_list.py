import sys
from hashlib import sha256
from html.parser import HTMLParser

import requests


class TokenFinder(HTMLParser):
    in_token = False
    token_value = ''

    def reset(self):
        super(TokenFinder, self).reset()
        self.in_token = False
        self.token_value = ''

    def handle_starttag(self, tag, attrs):
        self.in_token = dict(attrs).get('id') == 'token'

    def handle_data(self, data):
        if self.in_token:
            self.token_value += data.replace('\n', '')


class PiHoleAPI(object):
    def __init__(self, host):
        self.host = host
        self.session = requests.Session()
        self.pwhash = ''  # auth GET param
        self.token_value = ''

    def update_token(self, response: requests.Response):
        finder = TokenFinder()
        finder.feed(response.text)
        self.token_value = finder.token_value

    def auth(self, password: str):
        self.pwhash = sha256(sha256(password.encode()).hexdigest().encode()).hexdigest()
        response = self.session.post('{}/admin/index.php'.format(self.host), data={
            'pw': password,
        })
        self.update_token(response)
        return response

    def get_adlist(self):
        data = {
            'action': 'get_adlists',
            'token': self.token_value,
        }
        response = self.session.post(
            '{}/admin/scripts/pi-hole/php/groups.php'.format(self.host),
            data=data
        )
        if response.headers.get('content-type') == 'application/json':
            return response.json()
        return {}

    def add_adlist(self, url: str):
        data = {
            'action': 'add_adlist',
            'address': url,
            'token': self.token_value,
        }
        response = self.session.post(
            '{}/admin/scripts/pi-hole/php/groups.php'.format(self.host),
            data=data
        )
        if response.headers.get('content-type') == 'application/json':
            return response.json()
        self.update_token(response)
        return {}

    def edit_adlist(self, obj_id: int, enabled=1, comment=None, groups=None):
        data = {
            'action': 'edit_adlist',
            'id': obj_id,
            'status': enabled,
            'token': self.token_value,
        }
        if comment is not None:
            data['comment'] = comment
        if groups is not None:
            data['groups'] = groups

        response = self.session.post(
            '{}/admin/scripts/pi-hole/php/groups.php'.format(self.host),
            data=data
        )
        if response.headers.get('content-type') == 'application/json':
            return response.json()
        return {}


class PiHoleAdItem(object):
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.address = kwargs.get('address')
        self.enabled = kwargs.get('enabled')
        self.comment = kwargs.get('comment')
        self.groups = kwargs.get('groups')

    def is_enable(self) -> bool:
        return bool(self.enabled)

    def enable(self, api: PiHoleAPI):
        self.enabled = 1
        self.save(api)

    def disable(self, api: PiHoleAPI):
        self.enabled = 0
        self.save(api)

    def save(self, api: PiHoleAPI):
        api.edit_adlist(self.id, enabled=self.enabled, comment=self.comment, groups=self.groups)


def main():
    err_stream = sys.stderr
    host_stream = sys.stdout

    f = 'secrets.env'
    config = {}
    for line in open(f):
        line = line.replace('\n', '').replace('\r', '')
        if line:
            key, val = line.split('=', 1)
            config[key] = val

    pi = PiHoleAPI(config.get('PIHOLE_HOST', 'http://127.0.0.1'))
    pi.auth(config.get('WEBPASSWORD'))
    ads_items = pi.get_adlist()

    urls = set()
    on_pihole = {}
    for item in ads_items.get('data', []):
        url = item.get('address')
        on_pihole[url] = PiHoleAdItem(**item)
        urls.add(url)

    f = 'pihole.list'
    for line in open(f):
        line = line.replace('\n', '').replace('\r', '')
        if '#' not in line and line:
            urls.add(line)

    valid = set()
    try:
        while urls:
            url = urls.pop()
            response = requests.head(url)
            if response.status_code == 200:
                if url in on_pihole:
                    if not on_pihole[url].is_enable():
                        on_pihole[url].enable(pi)
                else:
                    pi.add_adlist(url)

                valid.add(url)
            elif response.status_code in [301, 302]:
                if url in on_pihole and on_pihole[url].is_enable():
                    on_pihole[url].disable(pi)
                next_loc = response.headers.get('location')
                if next_loc.startswith('http'):
                    urls.add(next_loc)
                else:
                    err_stream.write("!! Invalid redirect ({}): {} -> {}\n".format(response.status_code, url, next))
            else:
                if url in on_pihole and on_pihole[url].is_enable():
                    on_pihole[url].disable(pi)
                err_stream.write("!! Invalid ({}): {}\n".format(response.status_code, url))
    except KeyError:
        pass

    host_stream.write('#########################\n')
    host_stream.write('#   PI HOLE BLACKLIST   #\n')
    host_stream.write('#########################\n')
    for url in sorted(valid):
        host_stream.write(url)
        host_stream.write('\n')


if __name__ == '__main__':
    main()
