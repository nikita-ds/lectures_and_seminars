import json
import scrapy


class TgSpider(scrapy.Spider):
    name = 'tg_spider_raw'
    allowed_domains = [
        'rsshub.app'
    ]

    def start_requests(self):
        try:
            with open('/path/to/tg_data/news.json', 'r') as file:
                self.data = json.load(file)
        except FileNotFoundError:
            self.data = []

        self.links = {item['link'] for item in self.data}

        with open('/path/to/tg_data/sources.json', 'r') as file:
            tg_sources = json.load(file)

        print(tg_sources)

        for sources in tg_sources:
            for source, url in sources.items():
                yield scrapy.Request(
                    url = url,
                    callback = self.parse, 
                    meta = {
                        'source': source
                        }
                    )

    def parse(self, 
              response):
        items = response.xpath('//item')

        for item in items:
            link = item.xpath('.//link/text()').get()

            if link not in self.links:
                self.links.add(link)

                row = {
                    'source': response.meta['source'],
                    'title': item.xpath('.//title/text()').get(),
                    'description': item.xpath('.//description/text()').get(),
                    'published_date': item.xpath('.//pubDate/text()').get(),
                    'link': link
                }

                if row['description'] == None:
                    row['description'] = ''

                self.data.append(row)

        with open('/path/to/tg_data/news.json', 'w') as file:
            json.dump(self.data, file)