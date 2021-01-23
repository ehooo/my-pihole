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

    def update_token(self, response: requests.Response) -> None:
        finder = TokenFinder()
        finder.feed(response.text)
        self.token_value = finder.token_value

    def auth(self, password: str) -> requests.Response:
        self.pwhash = sha256(sha256(password.encode()).hexdigest().encode()).hexdigest()
        response = self.session.post('{}/admin/index.php'.format(self.host), data={
            'pw': password,
        })
        self.update_token(response)
        return response

    def get_adlist(self) -> dict:
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

    def add_adlist(self, url: str) -> dict:
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

    def edit_adlist(self, obj_id: int, enabled: int = 1, comment: [str] = None, groups: [str] = None) -> dict:
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

    def get_all_queries(self, client: [str] = None) -> dict:
        params = {
            'getAllQueries': '',
        }
        if client:
            params['client'] = client
        response = self.session.get(
            '{}/admin/api.php'.format(self.host),
            params=params
        )
        if response.headers.get('content-type') == 'application/json':
            return response.json()
        return {}

    def get_unique_non_blocked_queries(self, client: [str] = None) -> set:
        all_queries = self.get_all_queries(client)
        hosts = set()
        for query in all_queries.get('data', []):
            hosts.add(query[2])
        return hosts


class PiHoleAdItem(object):
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.address = kwargs.get('address')
        self.enabled = kwargs.get('enabled')
        self.comment = kwargs.get('comment')
        self.groups = kwargs.get('groups')

    def is_enable(self) -> bool:
        return bool(self.enabled)

    def enable(self, api: PiHoleAPI) -> None:
        self.enabled = 1
        self.save(api)

    def disable(self, api: PiHoleAPI) -> None:
        self.enabled = 0
        self.save(api)

    def save(self, api: PiHoleAPI) -> None:
        api.edit_adlist(self.id, enabled=self.enabled, comment=self.comment, groups=self.groups)
