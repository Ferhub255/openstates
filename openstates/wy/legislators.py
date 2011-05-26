from billy.scrape import ScrapeError, NoDataForPeriod
from billy.scrape.legislators import LegislatorScraper, Legislator

import lxml.html
import re

class WYLegislatorScraper(LegislatorScraper):
    state = "wy"

    members = {}
    urls = {
            "old": "http://legisweb.state.wy.us/%s/members/%s.htm",
            "new": "http://legisweb.state.wy.us/LegbyYear/LegislatorList.aspx?House=%s&Year=%s&Number=%s"
    }

    def scrape(self, chamber, term):
        abbr = {"upper": "S", "lower": "H"}
        years = []

        # Each term spans two years, so we need to scrape the 
        # members from both years and eliminate dupes
        for t in self.metadata["terms"]:
            if term == t["name"]:
                years.append(t["start_year"])
                years.append(t["end_year"])
                break

        for year in years: 
            if(year > 2005):
                chamber_indication = "H" if chamber == "lower" else "S"
                url = self.urls["new"] % (chamber_indication, year, term)
                self.scrape_members(url, 2)
            else:
                chamber_indication = "rep" if chamber == "lower" else "sen"
                url = self.urls["old"] % (year, chamber_indication)
                self.scrape_members(url, 1)

        for m in self.members:
            self.log(m)
            m = self.members[m]
            leg = Legislator(term, chamber, m["district"], m["name"], party=m["party"])
            leg.add_source(m["source"])
            self.save_legislator(leg)


    def scrape_members(self, url, version):
        """
        Scrapes legislator information from pages created since 2006
        """
        self.log(url)
        self.log(version)
        with self.urlopen(url) as page:
            page = lxml.html.fromstring(page)

            row_path = '//table[contains(@id,"Members")]/tr' if version == 2 else "//table/tr"
            for row in page.xpath(row_path)[1:]:
                td_path = ".//td" if version == 2 else ".//td/font"
                tds = row.xpath(td_path)
                if(len(tds) < 4):
                    continue
                name = tds[0].text_content().replace("\n"," ").replace("\r"," ")
                name = re.sub("\s+"," ", name)
                # Special case from http://legisweb.state.wy.us/2003/members/sen.htm; need better fix
                name = re.sub("Resigned - \d+/\d+", "", name)
                name = name.strip()

                party = tds[1].text_content().strip()
                district = tds[2].text_content().strip()
                # Only keep if we don't already have member
                if(not self.members.has_key(name)):
                    self.log(name)
                    self.members[name] = { "name": name, "party": party, "district": district, "source": url }
