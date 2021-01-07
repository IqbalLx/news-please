import os
import logging

import scrapy


class HtmlFileCrawler(scrapy.Spider):
    name = "HtmlFileCrawler"
    start_urls = None

    log = None

    config = None
    helper = None

    def __init__(self, helper, url, config, ignore_regex, *args, **kwargs):
        self.log = logging.getLogger(__name__)

        self.config = config
        self.helper = helper

        if isinstance(url, list):
            self.start_urls = url
        else:
            self.start_urls = [url]

        super(HtmlFileCrawler, self).__init__(*args, **kwargs)

    
    def start_requests(self):
        first_item = self.start_urls[0]
        if "root://" in first_item:
            return self._parse_from_root()
        elif "file://" in first_item:
            return self._parse_from_file()
        else:
            raise ValueError(f"format {first_item} is wrong, make sure use either file:// or root://")

    
    def _parse_from_root(self):
        for root in self.start_urls:
            path = root.replace("root://", "")
            for root, _, files in os.walk(path):
                for webfile in files:
                    if webfile.endswith('.html'):
                        htmlpath = f"file://{os.path.join(root, webfile)}"
                        
                        yield scrapy.Request(htmlpath, self.parse)


    def _parse_from_file(self):
        for filepath in self.start_urls:
            yield scrapy.Request(filepath, self.parse)
    
    def parse(self, response):
        """
        Passes the response to the pipeline.

        :param obj response: The scrapy response
        """        
        original_url = response.xpath('//link[@rel="canonical"]/@href').extract_first()
        response.meta['original_url'] = original_url
        yield self.helper.parse_crawler.pass_to_pipeline(
            response,
            self.helper.url_extractor.get_allowed_domain(response.meta.get('original_url', response.url))
        )

    @staticmethod
    def supports_site(urls):
        """
        As long as the url exists, this crawler will work!

        Determines if this crawler works on the given url.

        :param str url: The url to test
        :return bool: Determines wether this crawler work on the given url
        """

        if not isinstance(urls, list):
            urls = [urls]
        
        supported = True
        for url in urls:
            if "root://" in url:
                root_path = url.replace("root://", "")
                supported = supported and os.path.exists(root_path)
            elif "file://" in url:
                file_path = url.replace("file://", "")
                supported = supported and os.path.exists(file_path)
            else:
                raise ValueError(f"format {url} is wrong, make sure use either file:// or root://")
        
        return supported
