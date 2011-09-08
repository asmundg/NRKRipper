#!/usr/bin/env python

import cookielib
import logging
import os
import optparse
import re
import stat
import subprocess

from lxml import etree
import mechanize

class NRKRipper(object):
    movie_object_url = 'string(//object[@id="ctl00_ucPlayer_Player"]/@url[1])'
    asx_mms_url = 'string(//entry/ref[1]/@href)'
    program_page_links = '//div[@id="dyn-navigation"]//a[@class="icon-video-black indexPadding"]'
    program_subpage_links = '//div[@id="dyn-navigation"]//a[@class="icon-closed-black"]/@href'

    def __init__(self):
        self.browser = mechanize.Browser()
        self.browser.set_cookiejar(self.make_cookiejar())
        self.visited_program_pages = {}

    def make_cookiejar(self):
        """
         Inject a cookie containing requested speed, avoiding a redirect
         to the speed detection page.
        """
        cookie_jar = cookielib.LWPCookieJar()
        cookie = cookielib.Cookie(
            version=0, name='NetTV2.0Speed',
            value='100000', port=None, port_specified=False, domain='www.nrk.no',
            domain_specified=False, domain_initial_dot=False, path='/',
            path_specified=True, secure=False, expires=None, discard=True,
            comment=None, comment_url=None, rest={'HttpOnly': None},
            rfc2109=False)
        cookie_jar.set_cookie(cookie)
        return cookie_jar

    def rip_program(self, url):
        """
         Given an URL to an NRK Nett-TV page
         (http://www.nrk.no/nett-tv/klipp/[0-9]+/), return the mms url for
         that resource.
        """
        self.browser.open(url)
        response_data = self.browser.response().read()
        response = etree.HTML(response_data)
        # The page contains an object with an url parameter pointing at an
        # ASX file
        source = response.xpath(self.movie_object_url)
        self.browser.open(source)
        asx_data = self.browser.response().read()
        asx = etree.HTML(asx_data)
        # The ASX file contains a list of movie source URLs. Get the
        # one using mms://.
        return asx.xpath(self.asx_mms_url)

    def list_project(self, url):
        logging.info("Looking for clips at %s", url)

        self.browser.open(url)
        response_data = self.browser.response().read()
        response = etree.HTML(response_data)
        links = response.xpath(self.program_page_links)
        sublinks = response.xpath(self.program_subpage_links)
        
        sources = []
        for sublink in sublinks:
            if sublink not in self.visited_program_pages:
                self.visited_program_pages[sublink] = 1
                sources.extend(self.list_project('http://www.nrk.no' + sublink))
            else:
                # Already visited
                pass

        for link in links:
            name = link.xpath('string(./text())')
            href = link.xpath('string(./@href)')
            sources.append((name, href))
        return sources

    def search_and_rip(self, url, output_dir):
        if not os.path.exists(output_dir.encode('utf-8')):
            os.makedirs(output_dir)
        for name, href in self.list_project(url):
            name = self.fix_stupid_dates(name)
            output_name = os.path.join(output_dir, name + '.wmv')
            if not os.path.exists(output_name.encode('utf-8')):
                source = self.rip_program('http://www.nrk.no' + href)
                logging.info(u"Ripping %s => %s", source, output_name)
                proc = subprocess.Popen(['mplayer', '-dumpstream', '-dumpfile',
                                         output_name.encode('utf-8'), source.encode('utf-8')])
                proc.wait()
                os.chmod(output_name.encode('utf-8'),
                         stat.S_IRUSR
                         | stat.S_IWUSR 
                         | stat.S_IRGRP
                         | stat.S_IROTH)

    def fix_stupid_dates(self, name):
        pattern = '(.*)([0-9]{2})\.([0-9]{2})\.([0-9]+)$'
        match = re.match(pattern, name)
        if match is None:
            return name
        prefix, day, month, year = match.groups()
        name = '%s%s-%s-%s' % (prefix, year, month, day)
        return name
        

def rip_all(source):
    ripper = NRKRipper()

    for line in source:
        line = line.decode('utf-8').strip()
        if not line or line.startswith('#'):
            continue

        logging.info("Line: %s", line)
        url, output_dir = line.split(' ', 1)
        logging.info(u"Searching %s", url)
        ripper.search_and_rip(url, output_dir)
   
if __name__ == '__main__':
    logging.basicConfig(
        level = logging.INFO,
        format = "%(asctime)s %(name)s %(levelname)s %(message)s")

    import sys
    rip_all(sys.stdin)
