from typing import Dict, List, Any

import requests
import re
from parsel import Selector
import sys
import json


class ZenYandex:
    def __init__(self, login, password):
        self.passport_url = "https://passport.yandex.ru/"
        self.zen_url = "https://zen.yandex.ru/"
        self.login = login
        self.password = password
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) ' +
                          'Chrome/83.0.4103.61 Safari/537.36'
        }
        self.r = requests.Session()
        self.accounts = ""
        self.csrf_token = ""

    def login_to_passport_step_start(self):
        login_page = self.r.get(self.passport_url + "auth/add")
        csrf_token = Selector(login_page.text).css("body").attrib['data-csrf']
        if not csrf_token:
            raise Exception('csrf_token not found')

        match = re.search(r'process_uuid=([\w0-9\-]+)', login_page.text)
        if match:
            process_uuid = match[1]
        else:
            raise Exception('Process_uuid not found')

        auth_data = {
            'login': self.login,
            'csrf_token': csrf_token,
            'process_uuid': process_uuid,
            'origin': "zen_pubs"
        }

        start_request = self.r.post(self.passport_url + "registration-validations/auth/multi_step/start",
                                    data=auth_data)
        if start_request.status_code != 200:
            raise Exception('Invalid start step code {} response {}'.format(start_request.status_code,
                                                                            start_request.text))
        else:
            track_id = start_request.json()['track_id']

        return csrf_token, track_id

    def login_to_passport_step_commit(self, csrf_token, track_id):
        commit_password_json = {
            'csrf_token': csrf_token,
            'password': self.password,
            'track_id': track_id
        }
        commit = self.r.post(self.passport_url + "registration-validations/auth/multi_step/commit_password",
                             commit_password_json)

        if commit.json()['status'] != 'ok':
            raise Exception('Commit password problem: ' + commit.text)

        self.accounts = self.r.post(self.passport_url + "registration-validations/auth/accounts")

        account_uid = self.accounts.json()['accounts']['processedAccount']['uid']
        if not account_uid:
            raise Exception('No account uid')

        csrf_token = self.accounts.json()['csrf']
        ask_v2_data = {'csrf_token': csrf_token, 'uid': account_uid}
        ask_v2 = self.r.post(self.passport_url + "registration-validations/auth/additional_data/ask_v2", ask_v2_data)
        if ask_v2.status_code != 200:
            raise Exception("Invalid ask_v2 request, status code: " + str(ask_v2.status_code))

    def login_to_zen(self):
        csrf_token, track_id = self.login_to_passport_step_start()
        self.login_to_passport_step_commit(csrf_token, track_id)

        editor_data = self.r.get(self.zen_url + "media/zen/login")
        match_csrf = re.search(r'_csrfToken\s=\s\'([^\']+)\'', editor_data.text)
        if match_csrf:
            csrf_token = match_csrf[1]
        else:
            raise Exception("CSRF not found")

        self.headers["x-csrf-token"] = csrf_token

    def get_publishers(self):
        publishers_data = self.r.get(self.zen_url + "editor-api/v2/flights/agency/get-clients-list",
                                     headers=self.headers)

        publishers: List[Dict[str, Any]] = []
        for publisher in publishers_data.json()['publishers']:
            publishers.append({'uid': publisher['publisherId'], 'name': publisher['name']})

        return publishers

    def get_stat_by_publisher(self, publisher_id, date):
        url = self.zen_url + "media-api/publisher/{}/publication-stats?from={}&to={}&type=article"
        stats_url = url.format(publisher_id, date, date)
        res = self.r.get(stats_url, headers=self.headers)

        publications = {}
        for publication in res.json()['publications']:
            publications.setdefault(publication['publicationId'], [])
            if publisher_id == publication['publisherId']:
                publications[publication['publicationId']] = {
                    'title': publication['title'],
                    'stats': publication['stats']
                }

        return publications


def validate_args():
    arg_names = ['script', 'login', 'password', 'publisher_id', 'date']
    arguments = dict(zip(arg_names, sys.argv))

    if 'login' and 'password' not in arguments:
        print("usage: " + arguments['script'] + " <login> <password> - return publishers")
        print("usage: " + arguments['script']
                        + " <login> <password> <publisher_id> <date> return publication stats")
        exit()

    return arguments


if __name__ == '__main__':
    result = {'result': True}
    try:
        args = validate_args()

        Zen = ZenYandex(login=args['login'], password=args['password'])
        Zen.login_to_zen()

        if 'publisher_id' and 'date' in args:
            result['data'] = Zen.get_stat_by_publisher(args['publisher_id'], args['date'])
        else:
            result['data'] = Zen.get_publishers()
    except Exception as e:
        result['result'] = False
        result['message'] = str(e) + " on line " + str(sys.exc_info()[-1].tb_lineno)

    print(json.dumps(result, indent=4))
