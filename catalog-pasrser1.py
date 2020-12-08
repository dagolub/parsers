import requests
from parsel import Selector
import requests_cache
import xlsxwriter
import os
import shutil
import subprocess


class Parser:
    def __init__(self, login, password):
        requests_cache.install_cache('cache')
        self.shop_url = "https://some-shop.pl/pl/"
        self.catalog_url = "https://some-shop.pl/ajax.php?shopname=1&lang=pl&vid=&lang=pl"
        self.login = login
        self.password = password
        self.r = requests.Session()
        self.headers = {
            'authority': 'some-shop.pl',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) ' +
                          'Chrome/86.0.4240.183 Safari/537.36'
        }

        sess_id = self.auth(login, password)
        if not sess_id:
            print("No auth")
            exit(1)

        self.headers['cookie'] = 'PHPSESSID_MIKE=' + sess_id
        self.products = {}

    def auth(self, login, password):
        self.r.post('https://some-shop.pl/login.html',
                    {'username': login,
                     'password': password,
                     'redir': '',
                     'hredir': ''}, headers=self.headers)

        jwt = self.r.get('https://some-shop.pl/przejdz-do-MIKE.html', headers=self.headers, allow_redirects=False)

        proc = subprocess.Popen(["curl", jwt.headers['Location'], "-I"], stdout=subprocess.PIPE)
        (out, err) = proc.communicate()
        r = str(out).split(";")
        for i in r:
            if 'PHPSESSID_MIKE' in i:
                return i.split("=")[1]

        return False;

    def get_product(self, tr):
        links = Selector(tr).css("td.show_history_tips a::attr(href)").getall();
        if len(links) == 0:
            return False
        link = links[0]
        _art = Selector(tr).css("td.show_history_tips a::text").getall()
        if len(_art) == 0:
            return False
        art = _art[0].replace(".", "")
        name = " ".join(Selector(tr).css("td:nth-child(4) b::text").getall())
        number = " ".join(Selector(tr).css("td:nth-child(5)::text").getall()).strip()
        prices = Selector(tr).css("td:nth-child(6) b::text").re(r'\d+.\d+')
        if len(prices) == 0:
            return False
        price = prices[0]
        ppp = Selector(tr).css("td:nth-child(7) b::text").re(r'\d+.\d+')
        if len(ppp) == 0:
            return False
        price_hurt = ppp[0]
        classes = Selector(tr).css("td:nth-child(1) div").xpath("@class").extract()[0]
        availability = ''
        if 'available' in classes:
            availability = 9
        if 'part_available' in classes:
            availability = 1
        if 'not_available' in classes:
            availability = ''

        # img = Selector(tr).css("td:nth-child(3) img").getall()
        # if len(img) > 0:
        #     self.save_images(link, art)

        return {'link': link,
                'art': art,
                'number': number,
                'name': name,
                'price': price,
                'price_hurt': price_hurt,
                'availability': availability}

    def save_images(self, link, art):
        product_page = self.get(link)
        imgs = Selector(product_page.text).css('a.detail_img-mini::attr(href),a.detail_img::attr(href)').getall()
        images = []
        if len(imgs) > 0:
            for img in imgs:
                if len(img) > 10:
                    img_blob = self.r.get("https:"+img)
                    if img_blob.status_code == 200:
                        img_blob.raw.decode_content = True
                        images.append(img_blob.raw)

        i = 1
        dir_name = "images/"

        if not os.path.isdir(dir_name):
            os.mkdir(dir_name)

        for image in images:
            if i == 1:
                file_name = dir_name + art + ".jpg"
            else:
                file_name = dir_name +art + "_" + str(i) + ".jpg"
            with open(file_name, 'wb') as f:
                shutil.copyfileobj(image, f)
            i += 1

    def get_products_on_page(self, category_page):
        trs = Selector(category_page.text).css("tr.tda,tr.tdb").getall()
        products = []
        for tr in trs:
            product = self.get_product(tr)
            if product:
                products.append(product.copy())

        return products

    def get_categories(self):
        catalog_page = self.get(self.shop_url)

        if catalog_page.status_code != 200:
            print(self.shop_url)
            print(catalog_page.status_code)

        cats = Selector(catalog_page.text).css('.cat-item a::attr(href)').extract()
        for cat in cats:
            category_page = self.get(cat + '?show=table')
            _products = self.get_products_on_page(category_page)
            self._append(_products)
            total = Selector(category_page.text).css('a::attr(href)').re(r'sr=([^0|30]\d+)')[0]
            if total:
                for sr in range(30, int(total), 30):
                    category_page = self.get(cat + '?sr=' + str(sr) + '&show=table')
                    _products = self.get_products_on_page(category_page)
                    self._append(_products)

    def _append(self, products):
        for product in products:
            if product['art'] not in self.products:
                self.products[product['art']] = product

        f = open("process.txt", "w")
        f.write(str(len(Parser.products)))
        f.close()

    def get(self, url):
        page = self.r.get(url, headers=self.headers)
        if page.status_code != 200:
            print(page.status_code, url)
            exit(1)
        return page

    def write_xlsx(self):
        print("Total products", len(self.products))
        workbook = xlsxwriter.Workbook('products.xlsx')
        worksheet = workbook.add_worksheet()

        row = 1

        worksheet.write(0, 0, 'Артикул')
        worksheet.write(0, 1, 'Код производителя')
        worksheet.write(0, 2, 'Цена розница')
        worksheet.write(0, 3, 'Цена вход')
        worksheet.write(0, 4, 'Наличие')
        # Iterate over the data and write it out row by row.
        for art in self.products:
            worksheet.write(row, 0, str(self.products[art]['art']))
            worksheet.write(row, 1, str(self.products[art]['number']))
            worksheet.write(row, 2, str(self.products[art]['price']))
            worksheet.write(row, 3, str(self.products[art]['price_hurt']))
            worksheet.write(row, 4, str(self.products[art]['availability']))
            row += 1

        workbook.close()


if __name__ == '__main__':
    result = {'result': True}

    if os.path.isfile('products.xlsx'):
        print("Remove products.xlsx to run parser")
        exit(1)

    if not os.path.isfile('running'):
        print("Please add running file to run parser")
        exit(1)

    Parser = Parser('096031', 'larsson1231')

    Parser.get_categories()
    Parser.write_xlsx()

