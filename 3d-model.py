import io
import requests
import re
import json
from progress.bar import IncrementalBar
import asyncio
import aiohttp
from app import schemas
from app import crud
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from app.api import deps
from fastapi import Depends


class SomeSite:
    def __init__(self):
        self.use_file = True
        self.use_search = False
        self.headers = dict()
        self.bar = None

    def login(self):
        main_page = requests.get('https://site.com')
        result = re.search("https.*?app\.bundle\.js\?[0-9]+", main_page.text)[0] # noqa
        js_content = requests.get(result)
        token = re.search(r"api\.site\.com.*?u=\"(.*?)\"", js_content.text)[1] # noqa
        self.headers['Authorization'] = 'Bearer ' + token

    def parse_items(self):
        f = open("data/items.json", "r")
        items = json.loads(f.read())
        self.bar = IncrementalBar('Items', max=len(items))
        result = []
        for item in items:
            id = item.split(':')[-1].strip()
            url = f"https://api.site.com/things/{id}"
            result.append(asyncio.run(self.parse(requests.get(url, headers=self.headers)))) # noqa
            self.bar.next()
        self.bar.finish()
        return result

    async def parse(self, response):
        data = response.json()
        if 'id' in data:
            result = {
                'source': 'site',
                'reference': data.get('id'),
                'name': data.get('name'),
                'description': data.get('description'),
                'description_html': data.get('description_html'),
                'tags': [tag.get('name') for tag in data.get('tags')],
                "categories": "",
                'images': "",
                'files': "",
                'comments': "",
                'original_link_to_item': data.get('public_url'),
            }
            args = dict()
            args['item'] = result
            if data['categories_url']:
                urls = [data.get('categories_url'),
                        data.get('images_url'),
                        data.get('files_url'),
                        f"https://api.site.com/things/{data['id']}/root-comments"]
                async with aiohttp.ClientSession(headers=self.headers, trust_env=False) as session:
                    async_result = await asyncio.gather(*[self.get_async(url, session) for url in urls])
                    result['categories'] = async_result[0]
                    result['images'] = async_result[1]
                    result['files'] = async_result[2]
                    result['comments'] = async_result[3]
                    return result

    async def get_async(self, url, session):
        try:
            async with session.get(url=url, ssl=False) as response:
                response = await response.read()
                if 'categories' in url:
                    return self.parse_categories(response)
                if 'images' in url:
                    return self.parse_images(response)
                if 'files' in url:
                    return self.parse_files(response)
                if 'comments' in url:
                    return self.parse_comments(response)
        except Exception as e:
            print("Unable to get url {} due to {}.".format(url, e.__class__))

    @staticmethod
    def parse_categories(response):
        categories = []

        for category in json.load(io.BytesIO(response.replace(b"'", b'"'))):
            categories.append(category['name'])

        return list(dict.fromkeys(categories))

    @staticmethod
    def parse_images(response):
        urls = []

        for image in json.load(io.BytesIO(response.replace(b"'", b'"'))):
            for size in image['sizes']:
                if size['type'] == 'display' and size['size'] == 'large':
                    urls.append(size['url'])

        return list(dict.fromkeys(urls))

    def parse_files(self, response):
        files = []

        for file in json.load(io.BytesIO(response.replace(b"'", b'"'))):
            files.append({
                'name': file['name'],
                'size': file['size'],
                'download_url': file['download_url'],
                'headers': self.headers,
            })

        return files

    @staticmethod
    def parse_comments(response):
        comments = []

        for comment in json.load(io.BytesIO(response.replace(b"'", b'"'))):
            user = comment.get('user')
            comments.append({
                'author_nick': user.get('name'),
                'author_name': f"{user['first_name']} {user['last_name']}".strip(),
                'avatar': user.get('thumbnail'),
                'body': comment.get('body'),
                'body_html': comment.get('body_html'),
                'created_at': comment.get('added'),
            })

        return comments
