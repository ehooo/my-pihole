import sys

import requests

from pihole import PiHoleAPI, PiHoleAdItem


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
