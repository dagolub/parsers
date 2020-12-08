import requests
from parsel import Selector
import csv
import traceback


class Parser:
    def __init__(self):
        self.base_url = "https://trade-example.com/"
        self.r = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) ' +
                          'Chrome/86.0.4240.183 Safari/537.36'
        }

    def get_stocks(self):
        portlist = []
        page = self.get(self.base_url)
        trs = Selector(page.text).css('tr').getall()

        for tr in trs:
            symbol_match = Selector(tr).css('td:nth-child(2) div span::text')
            rating_match = Selector(tr).css('td:nth-child(6) div div').re(r'(\d+)%')
            if len(symbol_match) == 1 and len(rating_match) == 1:
                symbol = symbol_match.getall()[0]
                rating = rating_match[0]
                if int(rating_match[0]) >= 80:
                    print(symbol, rating)
                    portlist.append([symbol])

        file = open('result.csv', 'w')
        with file:
            writer = csv.writer(file)
            writer.writerow(['portlist'])
            writer.writerows(portlist)

    def get(self, url):
        page = self.r.get(url, headers=self.headers)
        if page.status_code != 200:
            print(page.status_code, url)
            exit(1)

        return page


if __name__ == '__main__':
    result = {'result': True}

    try:
        Parser = Parser()

        Parser.get_stocks()

    except Exception as e:
        raise
    except KeyError:
        f = open("error.txt", "w")
        f.write(traceback.format_exc())
        f.close()
        pass
