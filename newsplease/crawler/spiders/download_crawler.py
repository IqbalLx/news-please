import logging

import scrapy


class Download(scrapy.Spider):
    name = "Download"
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

        super(Download, self).__init__(*args, **kwargs)

    
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, self.parse, meta={
                'splash': {
                    'endpoint': 'render.html',
                    'args': {'wait': 0.5}
                },
                'original_url': url
            })

    
    def parse(self, response):
        """
        Passes the response to the pipeline.

        :param obj response: The scrapy response
        """
        if not self.helper.parse_crawler.content_type(response):
            return

        # self.log.error(f"Original url: {response.meta.get('original_url')}")
        yield self.helper.parse_crawler.pass_to_pipeline(
            response,
            self.helper.url_extractor.get_allowed_domain(response.meta.get("original_url"))
        )

    @staticmethod
    def supports_site(url):
        """
        As long as the url exists, this crawler will work!

        Determines if this crawler works on the given url.

        :param str url: The url to test
        :return bool: Determines wether this crawler work on the given url
        """
        return True
