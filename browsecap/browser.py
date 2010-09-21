from ConfigParser import SafeConfigParser as ConfigParser
import re
import os

from django.core.cache import cache

CACHE_KEY = 'browsecap'
CACHE_TIMEOUT = 60*60*2 # 2 hours
BC_PATH = os.path.abspath(os.path.dirname(__file__ or os.getcwd()))

class MobileBrowserParser(object):
    def __new__(cls, *args, **kwargs):
        # Only create one instance of this clas
        if "instance" not in cls.__dict__:
            cls.instance = object.__new__(cls, *args, **kwargs)
        return cls.instance

    def __init__(self):
        self.mobile_cache = {}
        self.mobile_data_cache = {}
        self.crawler_cache = {}
        self.parse()

    def parse(self):
        # try egtting the parsed definitions from cache
        data = cache.get(CACHE_KEY)
        if data:
            self.mobile_browsers = map(re.compile, data['mobile_browsers'])
            self.mobile_browsers_data = data['mobile_browsers_data']
            self.crawlers = map(re.compile, data['crawlers'])
            return

        # parse browscap.ini
        cfg = ConfigParser()
        files = ("browscap.ini", "bupdate.ini")
        read_ok = cfg.read([os.path.join(BC_PATH, name) for name in files])
        if len(read_ok) == 0:
            raise IOError, "Could not read browscap.ini, " + \
                  "please get it from http://www.GaryKeith.com"

        browsers = {}
        parents = set()

        # go through all the browsers and record their parents
        for name in cfg.sections():
            sec = dict(cfg.items(name))
            p = sec.get("parent")
            if p:
                parents.add(p)
            browsers[name] = sec

        self.mobile_browsers = []
        self.mobile_browsers_data = {} 
        self.crawlers = []
        for name, conf in browsers.items():
            # only process those that are not abstract parents
            if name in parents:
                continue

            p = conf.get('parent')
            if p:
                # update config based on parent's settings
                parent = browsers[p]
                conf.update(parent)

            qname = re.escape(name)
            qname = qname.replace("\\?", ".").replace("\\*", ".*?")
            qname = "^%s$" % qname
                        
            self.mobile_browsers.append(qname)
            self.mobile_browsers_data[qname] = conf
            
            self.crawlers.append(qname)

        # store in cache to speed up next load
        cache.set(CACHE_KEY, {
            'mobile_browsers': self.mobile_browsers, 
            'mobile_browsers_data': self.mobile_browsers_data, 
            'crawlers': self.crawlers,
        }, CACHE_TIMEOUT)

        # compile regexps
        self.mobile_browsers = map(re.compile, self.mobile_browsers)
        self.crawlers = map(re.compile, self.crawlers)

    def find_in_list(self, useragent, agent_list, cache):
        'Check useragent against agent_list of regexps.'
        try:
            return cache[useragent]
        except KeyError, e:
            pass

        for sec_pat in agent_list:
            if sec_pat.match(useragent):
                out = True
                break
        else:
            out = False
        cache[useragent] = out
        return out


    def find_in_data(self, useragent, agent_list, agent_list_data, cache):
        try:
            return cache['%s_data' % useragent]
        except KeyError, e:
            pass
        
        for sec_pat in agent_list:
            if sec_pat.match(useragent):
                print useragent
                out = agent_list_data[sec_pat.pattern]
                break
            else:
                out = False
        cache[useragent] = out
        return out


    def is_mobile(self, useragent):
        'Returns True if the given useragent is a known mobile browser, False otherwise.'
        return self.find_in_list(useragent, self.mobile_browsers, self.mobile_cache)

    def is_crawler(self, useragent):
        'Returns True if the given useragent is a known crawler, False otherwise.'
        return self.find_in_list(useragent, self.crawlers, self.crawler_cache)
        
    def get_browser_data(self, useragent):
        return self.find_in_data(useragent, self.mobile_browsers, self.mobile_browsers_data, self.mobile_data_cache)

        
# instantiate the parser
browsers = MobileBrowserParser()

# provide access to methods as functions for convenience
is_mobile = browsers.is_mobile
is_crawler = browsers.is_crawler
get_browser_data = browsers.get_browser_data


def update():
    'Download new version of browsecap.ini'
    import urllib
    urllib.urlretrieve("http://browsers.garykeith.com/stream.asp?BrowsCapINI",
                       "browscap.ini")