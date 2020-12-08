from typing import Dict, List, Any, Union

import requests
from parsel import Selector
import requests_cache
import xlsxwriter
import os
import shutil
import re
import traceback
from sqlite_cache.sqlite_cache import SqliteCache


class Parser:
    def __init__(self, login, password):
        self.cache = SqliteCache("./")
        self.shop_url = "https://shop.com/"
        self.login_url = "https://shop.com/logowanie,7"
        self.login = login
        self.password = password
        self.session_cookie = ".cdneshop"
        self.r = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) ' +
                          'Chrome/86.0.4240.183 Safari/537.36'
        }

        sess_id = self.auth(login, password)
        requests_cache.install_cache('cache')
        if not sess_id:
            print("Wrong session")
            exit(1)

        self.headers['cookie'] = self.session_cookie + '=' + sess_id
        self.products = {}

    def auth(self, login, password):
        r = requests.Session()
        login_page = r.get(self.login_url)
        for header in login_page.headers:
            cookies = re.findall(r'cdneshopsid=([^;]+);', login_page.headers[header])
            if cookies:
                cdneshopsid = cookies[0]
                self.headers['cookie'] = ".cdneshopsid=" + cdneshopsid

        match = re.findall(r"__CSRF='([^']+)'", login_page.text)
        if len(match) < 1:
            print("CSRF not found")
            exit(1)

        csrf = match[0]
        data = {
                        '__action': 'Customer/Login',
                        'email': login,
                        'password': password,
                        '__csrf': csrf
        }
        login_result = r.post(self.login_url, data, allow_redirects=False, headers=self.headers)

        for header in login_result.headers:
            cookies = re.findall(r''+self.session_cookie + '=([^;]+);', login_result.headers[header])
            if cookies:
                return cookies[0]

        return False

    def get_product(self, page):
        name_match = Selector(page).css(".product-name-lq::text").getall()
        if len(name_match) != 1:
            print("bad name")
            return False
        name = name_match[0]

        art_match = Selector(page).css(".product-code-ui::text").getall()
        if len(art_match) != 1:
            print('bad art')
            return False
        art = art_match[0]

        price_netto = Selector(page).css(".price-column-ui .price-ui").re(r'\d+,\d+')
        if len(price_netto) != 1:
            print("bad netto price")
            return False

        price = float(price_netto[0].replace(',', '.'))

        price_brutto = Selector(page).css(".price-column-ui .reg-price-ui").re(r'\d+,\d+')
        if len(price_brutto) != 1:
            print("bad brutto price")
            return False
        price_hurt = float(price_brutto[0].replace(',', '.'))

        availability = ''
        stock_data = Selector(page).css(".stock-level-ui::text").getall()

        if len(stock_data) == 2:
            availability_data = int(stock_data[1].strip().replace(',', '') or 0)
            if availability_data > 0:
                availability = 9

        image_data = Selector(page).css('.image-container-ui img::attr(data-src)').getall()
        if len(image_data) == 1:
            image = self.shop_url + image_data[0]
            self.save_images(image, art)

        return {
            'name': name,
            'art': art,
            'price': price,
            'price_hurt': price_hurt,
            'availability': availability}

    def save_images(self, link, art):
        dir_name = "images/"
        file_name = dir_name + art.replace('/', '_') + ".jpg"

        if not os.path.isdir(dir_name):
            os.mkdir(dir_name)

        if os.path.isfile(file_name):
            return

        img_blob = self.r.get(link,  stream=True)
        if img_blob.status_code == 200:
            img_blob.raw.decode_content = True
            with open(file_name, 'wb') as i:
                shutil.copyfileobj(img_blob.raw, i)

    def get_categories(self):
        catalog_page = self.get(self.shop_url)

        cats = Selector(catalog_page.text).css('.category-content-ui a::attr(href)').extract()
        for cat in cats:
            category_page = self.get(self.shop_url + "/" + cat)
            page_amount = Selector(category_page.text).css('.page-amount-ui::text')
            total = 1
            if page_amount:
                total = page_amount.re(r'z\s(\d+)')[0]

            for page in range(1, int(total)+1):
                category_url = self.shop_url + cat + '?pageId=' + str(page)
                category_page = self.get(category_url)
                _products = self.get_products_on_page(category_page)
                self._append(_products)

    def get_products_on_page(self, category_page):
        products_data = Selector(category_page.text).css(".product-item-ui").getall()

        products: List[Dict[str, Union[Union[float, str, int], Any]]] = []
        for data in products_data:
            product = self.get_product(data)
            if product:
                products.append(product.copy())

        return products

    def _append(self, products):
        for product in products:
            if product['art'] not in self.products:
                self.products[product['art']] = product

        p = open("process.txt", "w")
        p.write(str(len(Parser.products)))
        p.close()

    def get(self, url):
        page = self.cache.get(url)
        if page:
            return page

        page = self.r.get(url, headers=self.headers)
        if page.status_code != 200:
            print(page.status_code, url)
            exit(1)

        self.cache.set(url, page)
        return page

    def write_xlsx(self):
        wb = xlsxwriter.Workbook('products.xlsx')
        ws = wb.add_worksheet()
        ws.write(0, 0, 'Наименоване')
        ws.write(0, 1, 'Артикул')
        ws.write(0, 2, 'Цена розница')
        ws.write(0, 3, 'Цена вход')
        ws.write(0, 4, 'Наличие')
        row = 1

        print("Total products: ", len(self.products))
        for art in self.products:
            ws.write(row, 0, str(self.products[art]['name']))
            ws.write(row, 1, str(self.products[art]['art']))
            ws.write(row, 2, str(self.products[art]['price']))
            ws.write(row, 3, str(self.products[art]['price_hurt']))
            ws.write(row, 4, str(self.products[art]['availability']))
            row += 1
        wb.close()


if __name__ == '__main__':
    result = {'result': True}

    if os.path.isfile('products.xlsx'):
        print("Remove products.xlsx to run parser")
        exit(1)

    if not os.path.isfile('running'):
        print("Please add running file to run parser")
        exit(1)

    try:
        Parser = Parser('max.pamp.rs@gmail.com', 'Moto258963shop')

        Parser.get_categories()
        Parser.write_xlsx()

    except Exception as e:
        raise
    except KeyError:
        f = open("error.txt", "w")
        f.write(traceback.format_exc())
        f.close()
        pass
