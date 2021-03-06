import os
import re
import json
import requests
import importlib.resources
from bs4 import BeautifulSoup
from copy import deepcopy
from datetime import timedelta
from dateutil.parser import parse
from newspaper import Article
import configparser
from boto3 import Session

try:
    import urllib.request as urllib2
except ImportError:
    import urllib2

from .extractor.cleaner import Cleaner

cleaner = Cleaner()

# to improve performance, regex statements are compiled only once per module
re_digits = re.compile(r'\d+')

class MissingArticleExtractor:
    def __init__(self):
        self.possible_sites = {
            "kompas.com": self._extract_kompas,
            "cnbcindonesia.com": self._extract_cnbc,
            "antaranews.com": self._extract_antara,
            "tempo.co": self._extract_tempo,
            "kumparan.com": self._extract_kumparan,
            "liputan6.com": self._extract_liputan6,
        }

    def check_site(self, url):
        for site in self.possible_sites:
            if site in url:
                return True, site
        
        return False, None
    
    @staticmethod
    def _extract_by_xpath(item, xpath, fallback_xpath=None):
        article_text = item['spider_response'].xpath(xpath).extract()
        if not article_text and fallback_xpath is not None:
            article_text = item['spider_response'].xpath(fallback_xpath).extract()
        
        # print(article_text)

        article_text = ' '.join(article_text)
        article_text = cleaner.do_cleaning(article_text)
        item['article_text'] = article_text
        return item
    
    @staticmethod
    def _extract_kompas(item):
        item = MissingArticleExtractor._extract_by_xpath(item, \
            xpath="//*[@class='read__content']", \
            fallback_xpath="//*[@class='artikel-baca']"
            )

        return item
    
    @staticmethod
    def _extract_antara(item):
        item = MissingArticleExtractor._extract_by_xpath(item, xpath="//div[contains(@class, 'post-content')]")
        return item
    
    @staticmethod
    def _extract_tempo(item):
        item = MissingArticleExtractor._extract_by_xpath(item, xpath="//div[@itemprop='articleBody']")
        return item
    
    @staticmethod
    def _extract_kumparan(item):
        item = MissingArticleExtractor._extract_by_xpath(item, xpath="//div[contains(@class, 'mlPYL')]")
        item['article_text'] = item['article_text'].replace('ADVERTISEMENT', ' ')
        return item
    
    @staticmethod
    def _extract_liputan6(item):
        item = MissingArticleExtractor._extract_by_xpath(item, xpath="//div[contains(@class, 'article-content-body__item-page')]")
        return item
    
    @staticmethod
    def _extract_cnbc(item):
        multi_pages_urls = item['spider_response'].xpath("//div[@class='dropdown_menu']/a/@href") \
                                                    .extract()[1:]
        
        if multi_pages_urls:
            all_article_text = item['article_text']
            for multi_pages_url in multi_pages_urls:
                cnbc = Article(multi_pages_url)
                cnbc.download()
                cnbc.parse()
                all_article_text += cnbc.text
            
            item['article_text'] = all_article_text

        return item

    def process_item(self, item, spider):
        is_missing, site = self.check_site(item['url'])
        if is_missing:
            item = self.possible_sites[site](item)

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


class NamedEntityExtractor:
    def __init__(self):
        with importlib.resources.path("newsplease", "prosa_creds.json") as creds_path:
            with open(creds_path, 'r') as creds:
                creds = json.load(creds)
    
        self.headers = {
            **creds,
            'Content-Type': 'application/json'
        }
    
    def request(self, text):
        data = {
            "version": "v2",
            "text": text
        }

        repsonse = requests.post("https://api.prosa.ai/v1/entities",\
                                    headers=self.headers, data=json.dumps(data))
        entities = repsonse.json().get("entities")

        return entities
    
    def process_item(self, item, spider):
        article_title = item.get('article_title')
        if article_title is None:
            article_title = ''
        
        article_text = item.get('article_text')
        if article_text is None:
            article_text = ''
        
        text = article_title + article_text

        entities = None
        try:
            entities = self.request(text)
        except:
            pass

        item['entities'] = entities
        
        return item
        

class BrokenPipeline:
    def __init__(self):
        pass

    def process_item(self, item, spider):
        raise ValueError("This pipeline is mean to be Broken!")

        return item


class CountCommentExtractor:
    def __init__(self):
        pass
    
    @staticmethod
    def _ensure_int(count_comment):
        if isinstance(count_comment, int):
            return count_comment
        else:
            count_comment = re.search(re_digits, count_comment).group(0)
            count_comment = int(count_comment)
            return count_comment

    def _extract_from_div(self, body):
        count_comment = None
        possible_classes = [
            "total_comment",
            "share-box"
        ]

        for class_name in possible_classes:
            comment_div = body.xpath(f"//div[contains(@class, '{class_name}')]").extract_first()
            if comment_div is not None:
                comment_candidate = cleaner.delete_tags(comment_div)
                if comment_candidate:
                    count_comment = comment_candidate
                
                return count_comment
        
        return count_comment


    def process_item(self, item, spider):
        count_comment = self._extract_from_div(item['spider_response'])
        if count_comment is not None:
            count_comment = self._ensure_int(count_comment)
        
            item['count_comment'] = count_comment

        return item

class HtmlS3Storage:
    def __init__(self):
        aws_folder = "/home/ubuntu/.aws"
        if not os.path.exists(aws_folder):
            raise FileNotFoundError(f"AWS folder not found in {aws_folder}")
        
        creds = configparser.ConfigParser()
        creds.read(f"{aws_folder}/credentials")
        creds = creds['default']

        session = Session(aws_access_key_id=creds['aws_access_key_id'],
                    aws_secret_access_key=creds['aws_secret_access_key'])
        s3 = session.resource('s3')
        self.s3_session = s3.Bucket('rri-raw-data-files')

    def process_item(self, item, spider):
        source_domain = item['source_domain'].decode('utf-8')
        filename = item['filename']
        html_obj = item['spider_response'].body
        year, month, day = item['article_publish_date'].split(' ')[0].split('-')
        
        S3_SAVE_DIR = "raw_articles"
        key_object = f"{S3_SAVE_DIR}/{year}/{month}/{day}/{source_domain}/{filename}"

        self.s3_session.put_object(Body=html_obj, Key=key_object, ACL='public-read')

        return item