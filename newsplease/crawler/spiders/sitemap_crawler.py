import logging

import scrapy
from scrapy.spiders.sitemap import iterloc, regex
from scrapy.utils.sitemap import Sitemap, sitemap_urls_from_robots

from ...helper_classes.url_extractor import UrlExtractor


class SitemapCrawler(scrapy.spiders.SitemapSpider):
    name = "SitemapCrawler"
    allowed_domains = None
    sitemap_urls = None
    original_url = None

    log = None

    config = None
    helper = None

    def __init__(self, helper, url, config, ignore_regex, *args, **kwargs):
        self.log = logging.getLogger(__name__)

        self.config = config
        self.helper = helper
        self.original_url = url

        self.allowed_domains = [self.helper.url_extractor
                                    .get_allowed_domain(url, config.section(
            'Crawler')['sitemap_allow_subdomains'])]
        self.sitemap_urls = [self.helper.url_extractor.get_sitemap_url(
            url, config.section('Crawler')['sitemap_allow_subdomains'])]

        self.log.debug(self.sitemap_urls)

        super(SitemapCrawler, self).__init__(*args, **kwargs)

    def _parse_sitemap(self, response):
        if response.url.endswith('/robots.txt'):
            for url in sitemap_urls_from_robots(response.text, base_url=response.url):
                yield scrapy.Request(url, callback=self._parse_sitemap)
        else:
            body = self._get_sitemap_body(response)
            if body is None:
                # logger.warning("Ignoring invalid sitemap: %(response)s",
                            #    {'response': response}, extra={'spider': self})
                return

            s = Sitemap(body)
            it = self.sitemap_filter(s)

            if s.type == 'sitemapindex':
                for loc in iterloc(it, self.sitemap_alternate_links):
                    if any(x.search(loc) for x in self._follow):
                        yield scrapy.Request(loc, callback=self._parse_sitemap)
            elif s.type == 'urlset':
                for loc in iterloc(it, self.sitemap_alternate_links):
                    for r, c in self._cbs:
                        if r.search(loc):
                            yield scrapy.Request(loc, callback=c, meta={
                                'splash': {
                                    'endpoint': 'render.html',
                                    'wait': 0.5
                                },
                                'original_url': loc
                            })
                            break
    
    def parse(self, response):
        """
        Checks any given response on being an article and if positiv,
        passes the response to the pipeline.

        :param obj response: The scrapy response
        """
        if not self.helper.parse_crawler.content_type(response):
            return

        yield self.helper.parse_crawler.pass_to_pipeline_if_article(
            response, self.allowed_domains[0], self.original_url)

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
        Sitemap-Crawler are supported by every site which have a
        Sitemap set in the robots.txt.

        Determines if this crawler works on the given url.

        :param str url: The url to test
        :return bool: Determines wether this crawler work on the given url
        """

        return UrlExtractor.sitemap_check(url)
