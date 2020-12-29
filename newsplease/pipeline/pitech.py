import json
from bs4 import BeautifulSoup
from copy import deepcopy
from datetime import timedelta
from dateutil.parser import parse

try:
    import urllib.request as urllib2
except ImportError:
    import urllib2

from .extractor.cleaner import Cleaner

cleaner = Cleaner()

class KompasArticleExtractor:
    def __init__(self):
        pass

    @staticmethod
    def check_if_kompas(authors):
        if isinstance(authors, list):
            for author in authors:
                if 'kompas' in author.lower().strip():
                    return True
        else:
            if 'kompas' in authors.lower().strip():
                return True
        
        return False
    
    def process_item(self, item, spider):
        is_kompas = KompasArticleExtractor.check_if_kompas(item['article_author'])
        if is_kompas and item['article_text'] is None:
            # print(f"{item['source_domain']} is kompas")
            article_text = item['spider_response'].xpath("//*[@class='read__content']").extract()
            article_text = ' '.join(article_text)
            article_text = cleaner.do_cleaning(article_text)
            item['article_text'] = article_text

        return item


class DateModifiedExtractor:
    """By default date_modify is same as download_date, here we try
    to locate original date_modify from news source. But in some case
    the modify date is nonsense, so if the date_modify is more than (10)
    YEARS ago the date_modify is the same as date_publish
    """
    def __init__(self):
        pass
    
    @staticmethod
    def ensure_make_sense(publish_date, modified_date):
        YEARS = 10
        date_limit = timedelta(days=YEARS*365)

        # print(publish_date)
        # print(modified_date)
        # print("="*5)
        # print(type(publish_date))
        # print(type(modified_date))
        
        
        if modified_date < publish_date - date_limit:
            return False
        
        return True
    
    def _extract_from_json(self, html):
        date = None
        try:
            scripts = html.findAll('script', type='application/ld+json')
            if scripts is None:
                return None

            for script in scripts:
                data = json.loads(script.string)

                try:
                    date = data['dateModified']
                    date = parse(date).strftime('%Y-%m-%d %H:%M:%S')
                except (Exception, TypeError):
                    pass

        except (Exception, TypeError):
            return None
        
        return date
    
    def process_item(self, item, spider):
        url = item['url']
        html = deepcopy(item['spider_response'].body)
        modified_date = None

        try:
            if html is None:
                request = urllib2.Request(url)
                # Using a browser user agent, decreases the change of sites blocking this request - just a suggestion
                # request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko)
                # Chrome/41.0.2228.0 Safari/537.36')
                html = urllib2.build_opener().open(request).read()

            html = BeautifulSoup(html, "lxml")

            modified_date = self._extract_from_json(html)
        except Exception as e:
            # print(e)
            pass

        if modified_date is not None:
            parsed_publish_date = parse(item['article_publish_date'])
            parsed_modified_date = parse(modified_date)

            if self.ensure_make_sense(parsed_publish_date, parsed_modified_date):
                item['modified_date'] = modified_date
            else:
                item['modified_date'] = item['article_publish_date']
        
        return item
    
    
