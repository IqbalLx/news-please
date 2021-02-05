from newsplease.helper_classes.url_extractor import UrlExtractor

try:
    import urllib2
except ImportError:
    import urllib.request as urllib2
import logging

import scrapy


class KompasDailyCrawler(scrapy.Spider):
    name = "KompasDailyCrawler"
    ignored_allowed_domains = None
    start_urls = None
    original_url = None

    log = None

    config = None
    helper = None

    def __init__(self, helper, url, config, ignore_regex, *args, **kwargs):
        self.log = logging.getLogger(__name__)

        self.config = config
        self.helper = helper

        self.original_url = url

        # self.ignored_allowed_domain = self.helper.url_extractor \
        #     .get_allowed_domain(url)
        self.start_urls = [url] # [self.helper.url_extractor.get_start_url(url)]
        self.pages = int(url.split(':')[1])

        super(KompasDailyCrawler, self).__init__(*args, **kwargs)


    def start_requests(self):
        url = 'https://indeks.kompas.com/?page={}'
        for page in range(1, self.pages+1):
            self.log.info(f'Scraping {page} from {self.pages} pages')
            yield scrapy.Request(url.format(page), self.parse)

    def parse(self, response):
        """
        Extracts all article links and initiates crawling them.

        :param obj response: The scrapy response
        """
        for url in response.xpath('//a[@class="article__link"]/@href').extract():
            url += "?page=all#page"

            yield scrapy.Request(url, self.article_parse)

    def article_parse(self, response, rss_title=None):
        """
        Checks any given response on being an article and if positiv,
        passes the response to the pipeline.

        :param obj response: The scrapy response
        :param str rss_title: Title extracted from the rss feed
        """
        if not self.helper.parse_crawler.content_type(response):
            return

        yield self.helper.parse_crawler.pass_to_pipeline_if_article(
            response,
            self.helper.url_extractor.get_allowed_domain(response.meta.get("original_url", response.url)), 
            self.original_url,
            rss_title
            )

    @staticmethod
    def only_extracts_articles():
        """
        Meta-Method, so if the heuristic "crawler_contains_only_article_alikes"
        is called, the heuristic will return True on this crawler.
        """
        return True

    @staticmethod
    def supports_site(url):
        """
        Rss Crawler are supported if by every site containing an rss feed.
        But if it already an rss feed, immediately say True

        Determines if this crawler works on the given url.

        :param str url: The url to test
        :return bool: Determines wether this crawler work on the given url
        """

        if 'kompas.com' in url:
            return True
        
        return False
