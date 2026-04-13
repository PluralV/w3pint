#!/usr/bin/env python3
"""
Standalone test harness for analyzer search functions.

Usage:
    python test_analyzer.py                          # run built-in examples
    python test_analyzer.py doc.json                 # analyze a JSON file
    python test_analyzer.py doc.json terms.json      # use custom search terms too

The JSON doc (or array of docs) should have the same shape as your MongoDB documents:
  { "url": "...", "pageSrc": "...", "additionalRequests": [ { "endpoint": "...", "responseBody": "..." }, ... ] }
"""

import json
import sys


# ---------------------------------------------------------------------------
# Core functions (copied verbatim from analyzer.py — zero external deps)
# ---------------------------------------------------------------------------

def load_search_terms(path: str) -> dict:
    """
    Load search_terms.json and validate its structure.
    Lowercases all terms for case-insensitive matching.
    """
    with open(path, 'r') as f:
        terms = json.load(f)
    if not isinstance(terms.get('js_lines'), list):
        raise ValueError("search_terms.json must have a 'js_lines' array")
    if not isinstance(terms.get('domains'), list):
        raise ValueError("search_terms.json must have a 'domains' array")
    terms['js_lines'] = [t.lower() for t in terms['js_lines']]
    terms['domains'] = [t.lower() for t in terms['domains']]
    return terms


def search_page_source(page_src: str, search_tokens: list) -> list:
    if not page_src:
        return []
    found_lines = []
    for line_num, line in enumerate(page_src.split('\n'), start=1):
        line_lower = line.lower()
        for phrase in search_tokens:
            if phrase in line_lower:
                found_lines.append({"line_number": line_num, "line_text": line.strip(), "matched_token":phrase})
                break
    return found_lines


def search_additional_requests(additional_requests: list, search_tokens: list) -> tuple:
    """
    Search additionalRequests for domain matches and response payload matches.

    For each request:
      - If endpoint contains a domain from the list, add it to connected_domains
        and then search its responseBody for js_lines phrases.
      - If no domain match, skip entirely.

    Returns (connected_domains, responses).
    """
    if not additional_requests:
        return [], []
    connected_domains = []
    responses = []
    for idx, req in enumerate(additional_requests):
        endpoint = (req.get('endpoint') or '').lower()
        domain_matched = False
        for token in search_tokens:
            if token in endpoint:
                connected_domains.append(req.get('endpoint', ''))
                domain_matched = True
                break
        if not domain_matched:
            continue

        # Search responseBody for js_lines phrases
        response_body = req.get('responseBody', '')
        if not response_body:
            continue
        # Skip sentinel values from the crawler
        if response_body == '[base64]' or response_body.startswith('ERROR in'):
            continue
        response_body_lower = response_body.lower()
        for token in search_tokens:
            if token in response_body_lower:
                responses.append({"request_index": idx, "matched_phrase": token})
    return connected_domains, responses


def analyze_document(doc: dict, search_tokens: list) -> dict:
    found_lines = search_page_source(doc.get('pageSrc', ''), search_tokens)
    connected_domains, responses = search_additional_requests(
        doc.get('additionalRequests', []), search_tokens
    )
    interest = 1 if (found_lines or connected_domains or responses) else 0
    return {
        'found_lines': found_lines,
        'connected_domains': connected_domains,
        'responses': responses,
        'interest': interest,
    }


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

def print_results(url: str, result: dict):
    print(f"\n{'='*60}")
    print(f"URL: {url}")
    print(f"Interest: {result['interest']}")
    if result['found_lines']:
        print(f"\nPage source matches ({len(result['found_lines'])}):")
        for m in result['found_lines']:
            print(f"  L{m['line_number']}: {m['line_text'][:120]} (matched to {m['matched_token']})")
    if result['connected_domains']:
        print(f"\nConnected domains ({len(result['connected_domains'])}):")
        for d in result['connected_domains']:
            print(f"  {d}")
    if result['responses']:
        print(f"\nResponse body matches ({len(result['responses'])}):")
        for r in result['responses']:
            print(f"  request[{r['request_index']}] matched: {r['matched_phrase']}")
    if not result['interest']:
        print("  (no matches)")
    print('='*60)


# ---------------------------------------------------------------------------
# Built-in demo data
# ---------------------------------------------------------------------------

DEMO_SEARCH_TERMS = {
    "js_lines": ["eval(", "document.write(", "atob(", "fingerprint"],
    "domains": ["tracker.example.com", "cdn.sketchyads.net"],
}

DEMO_DOCS = [
    {
        "url": "https://example.com/page1",
        "pageSrc": (
            "<html>\n"
            "<head><script>var x = eval('something');</script></head>\n"
            "<body>Hello world</body>\n"
            "</html>"
        ),
        "additionalRequests": [
            {"endpoint": "https://tracker.example.com/collect?id=123",
             "responseBody": '{"status":"ok","fingerprint":"abc123"}'},
            {"endpoint": "https://cdn.legit.com/lib.js",
             "responseBody": "normal library code"},
        ],
    },
    {
        "url": "https://example.com/clean-page",
        "pageSrc": """
        
<!DOCTYPE html>
<html class="client-nojs skin-theme-clientpref-day" lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<title>Team Yankee - 1d6chan</title>
<script>document.documentElement.className="client-js skin-theme-clientpref-day";RLCONF={"wgBreakFrames":false,"wgSeparatorTransformTable":["",""],"wgDigitTransformTable":["",""],"wgDefaultDateFormat":"dmy","wgMonthNames":["","January","February","March","April","May","June","July","August","September","October","November","December"],"wgRequestId":"4834b36c2e3ba6672dadbbbe","wgCanonicalNamespace":"","wgCanonicalSpecialPageName":false,"wgNamespaceNumber":0,"wgPageName":"Team_Yankee","wgTitle":"Team Yankee","wgCurRevisionId":1848811,"wgRevisionId":1848811,"wgArticleId":48416,"wgIsArticle":true,"wgIsRedirect":false,"wgAction":"view","wgUserName":null,"wgUserGroups":["*"],"wgCategories":["Team Yankee","France","Wargames","Battlefront Miniatures"],"wgPageViewLanguage":"en","wgPageContentLanguage":"en","wgPageContentModel":"wikitext","wgRelevantPageName":"Team_Yankee","wgRelevantArticleId":48416,"wgIsProbablyEditable":true,"wgRelevantPageIsProbablyEditable":true,"wgRestrictionEdit":[],"wgRestrictionMove":[],"wgNoticeProject":"all","wgMediaViewerOnClick":true,"wgMediaViewerEnabledByDefault":true,"wgMFDisplayWikibaseDescriptions":{"search":false,"nearby":false,"watchlist":false,"tagline":false},"wgCheckUserClientHintsHeadersJsApi":["brands","architecture","bitness","fullVersionList","mobile","model","platform","platformVersion"],"wgIsMobile":false};
RLSTATE={"ext.globalCssJs.user.styles":"ready","site.styles":"ready","user.styles":"ready","ext.globalCssJs.user":"ready","user":"ready","user.options":"loading","mediawiki.page.gallery.styles":"ready","skins.monobook.styles":"ready","jquery.makeCollapsible.styles":"ready","ext.CookieWarning.styles":"ready","oojs-ui-core.styles":"ready","oojs-ui.styles.indicators":"ready","mediawiki.widgets.styles":"ready","oojs-ui-core.icons":"ready","ext.MobileDetect.nomobile":"ready","ext.DarkMode.styles":"ready"};RLPAGEMODULES=["mediawiki.page.media","site","mediawiki.page.ready","jquery.makeCollapsible","mediawiki.toc","skins.monobook.scripts","ext.centralNotice.geoIP","ext.centralNotice.startUp","ext.checkUser.clientHints","ext.CookieWarning","ext.echo.centralauth","ext.eventLogging","ext.DarkMode","ext.urlShortener.toolbar","mmv.bootstrap","ext.centralauth.centralautologin","ext.purge"];</script>
<script>(RLQ=window.RLQ||[]).push(function(){mw.loader.impl(function(){return["user.options@12s5i",function($,jQuery,require,module){mw.user.tokens.set({"patrolToken":"+\\","watchToken":"+\\","csrfToken":"+\\"});
}];});});</script>
<link rel="stylesheet" href="/w/load.php?lang=en&amp;modules=ext.CookieWarning.styles%7Cext.DarkMode.styles%7Cext.MobileDetect.nomobile%7Cjquery.makeCollapsible.styles%7Cmediawiki.page.gallery.styles%7Cmediawiki.widgets.styles%7Coojs-ui-core.icons%2Cstyles%7Coojs-ui.styles.indicators%7Cskins.monobook.styles&amp;only=styles&amp;skin=monobook">
<script async="" src="/w/load.php?lang=en&amp;modules=startup&amp;only=scripts&amp;raw=1&amp;skin=monobook"></script>
<meta name="ResourceLoaderDynamicStyles" content="">
<link rel="stylesheet" href="/w/load.php?lang=en&amp;modules=site.styles&amp;only=styles&amp;skin=monobook">
<meta name="generator" content="MediaWiki 1.45.3">
<meta name="referrer" content="origin">
<meta name="referrer" content="origin-when-cross-origin">
<meta name="robots" content="max-image-preview:standard">
<meta name="format-detection" content="telephone=no">
<meta name="description" content="&quot;Sunday, August 4, 1985 the Warsaw Pact thundered across the Iron Curtain. 6 Soviet Armies, backed up by the forces of Poland, Czechoslovakia, and East Germany,...">
<meta name="twitter:site" content="">
<meta name="twitter:card" content="summary">
<meta property="og:image" content="https://static.wikitide.net/1d6chanwiki/4/43/Team-Yankee-cover.jpg">
<meta property="og:image:width" content="849">
<meta property="og:image:height" content="1200">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes, minimum-scale=0.25, maximum-scale=5.0">
<meta property="og:title" content="Team Yankee - 1d6chan">
<meta property="og:type" content="website">
<link rel="preconnect" href="//upload.wikimedia.org">
<link rel="alternate" type="application/x-wiki" title="Edit" href="/wiki/Team_Yankee?action=edit">
<link rel="icon" href="https://static.miraheze.org/1d6chanwiki/a/ab/1d6_Small_Icon.png">
<link rel="search" type="application/opensearchdescription+xml" href="/w/rest.php/v1/search" title="1d6chan (en)">
<link rel="EditURI" type="application/rsd+xml" href="https://1d6chan.miraheze.org/w/api.php?action=rsd">
<link rel="canonical" href="https://1d6chan.miraheze.org/wiki/Team_Yankee">
<link rel="alternate" type="application/atom+xml" title="1d6chan Atom feed" href="/wiki/Special:RecentChanges?feed=atom">
<link rel="dns-prefetch" href="https://meta.miraheze.org" />
<meta property="og:title" content="Team Yankee">
<meta property="og:site_name" content="1d6chan">
<meta property="og:url" content="https://1d6chan.miraheze.org/wiki/Team_Yankee">
<meta property="og:description" content="&quot;Sunday, August 4, 1985 the Warsaw Pact thundered across the Iron Curtain. 6 Soviet Armies, backed up by the forces of Poland, Czechoslovakia, and East Germany,...">
<meta property="og:image" content="https://static.miraheze.org/1d6chanwiki/1/17/1d6ChanLogo.png">
<meta property="article:modified_time" content="2025-12-20T22:20:00Z">
<meta property="article:published_time" content="2025-12-20T22:20:00Z">
<script type="application/ld+json">{"@context":"http:\/\/schema.org","@type":"Article","name":"Team Yankee - 1d6chan","headline":"Team Yankee - 1d6chan","mainEntityOfPage":"Team Yankee","identifier":"https:\/\/1d6chan.miraheze.org\/wiki\/Team_Yankee","url":"https:\/\/1d6chan.miraheze.org\/wiki\/Team_Yankee","description":"\"Sunday, August 4, 1985 the Warsaw Pact thundered across the Iron Curtain. 6 Soviet Armies, backed up by the forces of Poland, Czechoslovakia, and East Germany,...","dateModified":"2025-12-20T22:20:00Z","datePublished":"2025-12-20T22:20:00Z","image":{"@type":"ImageObject","url":"https:\/\/static.miraheze.org\/1d6chanwiki\/1\/17\/1d6ChanLogo.png"},"author":{"@type":"Organization","name":"1d6chan","url":"https:\/\/1d6chan.miraheze.org","logo":{"@type":"ImageObject","url":"https:\/\/static.miraheze.org\/1d6chanwiki\/1\/17\/1d6ChanLogo.png","caption":"1d6chan"}},"publisher":{"@type":"Organization","name":"1d6chan","url":"https:\/\/1d6chan.miraheze.org","logo":{"@type":"ImageObject","url":"https:\/\/static.miraheze.org\/1d6chanwiki\/1\/17\/1d6ChanLogo.png","caption":"1d6chan"}},"potentialAction":{"@type":"SearchAction","target":"https:\/\/1d6chan.miraheze.org\/wiki\/Special:Search?search={search_term}","query-input":"required name=search_term"}}</script>
<link rel="dns-prefetch" href="auth.miraheze.org">
</head>
<body class="mediawiki ltr sitedir-ltr mw-hide-empty-elt ns-0 ns-subject mw-editable page-Team_Yankee rootpage-Team_Yankee skin-monobook action-view skin--responsive"><div id="globalWrapper">
	<div id="column-content">
		<div id="content" class="mw-body" role="main">
			<a id="top"></a>
			<div id="siteNotice"><!-- CentralNotice --></div>
			<div class="mw-indicators">
			</div>
			<h1 id="firstHeading" class="firstHeading mw-first-heading"><span class="mw-page-title-main">Team Yankee</span></h1>
			<div id="bodyContent" class="monobook-body">
				<div id="siteSub">From 1d6chan</div>
				<div id="contentSub" ><div id="mw-content-subtitle"></div></div>
				
				<div id="jump-to-nav"></div><a href="#column-one" class="mw-jump-link">Jump to navigation</a><a href="#searchInput" class="mw-jump-link">Jump to search</a>
				<!-- start content -->
				<div id="mw-content-text" class="mw-body-content"><div class="mw-content-ltr mw-parser-output" lang="en" dir="ltr"><figure class="mw-halign-right" typeof="mw:File/Thumb"><a href="/wiki/File:Team-Yankee-cover.jpg" class="mw-file-description"><img src="//static.wikitide.net/1d6chanwiki/thumb/4/43/Team-Yankee-cover.jpg/250px-Team-Yankee-cover.jpg" decoding="async" width="250" height="353" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/4/43/Team-Yankee-cover.jpg 1.5x" data-file-width="283" data-file-height="400" /></a><figcaption>FREEDOM, BITCHES!!!</figcaption></figure>
<p><i>"Sunday, August 4, 1985 the Warsaw Pact thundered across the Iron Curtain. 6 Soviet Armies, backed up by the forces of Poland, Czechoslovakia, and East Germany, hammered into the NATO forces guarding the border. The Americans, supported by the armies of West Germany, Britain, and France, are strained to the breaking point at the Soviet Advance. It is 1985, and the Cold War has just gone hot."</i>
</p><p>Welcome, soldier, to <i>Team Yankee</i>, Battlefront Miniatures' alternate history game where World War 3 breaks out on the fields of central Germany. Maybe you're here for the cool tanks, maybe you're here to fight and spread your preferred form of economic system, or maybe you're here to titillate your acronym fetish. Team Yankee is based on the book of the same name by Harold Coyle, the story of <i>Team Yankee</i> follows a unit of the US Army named Team Yankee (of course) as it struggles to hold off those damn Commies, with viewpoints from the other armies added in their respective Army rulebooks.
</p>
<div id="toc" class="toc" role="navigation" aria-labelledby="mw-toc-heading"><input type="checkbox" role="button" id="toctogglecheckbox" class="toctogglecheckbox" style="display:none" /><div class="toctitle" lang="en" dir="ltr"><h2 id="mw-toc-heading">Contents</h2><span class="toctogglespan"><label class="toctogglelabel" for="toctogglecheckbox"></label></span></div>
<ul>
<li class="toclevel-1 tocsection-1"><a href="#The_Story"><span class="tocnumber">1</span> <span class="toctext">The Story</span></a></li>
<li class="toclevel-1 tocsection-2"><a href="#The_Game"><span class="tocnumber">2</span> <span class="toctext">The Game</span></a>
<ul>
<li class="toclevel-2 tocsection-3"><a href="#Playing_the_game"><span class="tocnumber">2.1</span> <span class="toctext">Playing the game</span></a></li>
<li class="toclevel-2 tocsection-4"><a href="#List_Building"><span class="tocnumber">2.2</span> <span class="toctext">List Building</span></a></li>
<li class="toclevel-2 tocsection-5"><a href="#List_Archtypes"><span class="tocnumber">2.3</span> <span class="toctext">List Archtypes</span></a>
<ul>
<li class="toclevel-3 tocsection-6"><a href="#Mechanized_Infantry"><span class="tocnumber">2.3.1</span> <span class="toctext">Mechanized Infantry</span></a></li>
<li class="toclevel-3 tocsection-7"><a href="#Armoured"><span class="tocnumber">2.3.2</span> <span class="toctext">Armoured</span></a></li>
<li class="toclevel-3 tocsection-8"><a href="#Cavalry"><span class="tocnumber">2.3.3</span> <span class="toctext">Cavalry</span></a></li>
<li class="toclevel-3 tocsection-9"><a href="#Air_Assault"><span class="tocnumber">2.3.4</span> <span class="toctext">Air Assault</span></a></li>
<li class="toclevel-3 tocsection-10"><a href="#Air_Cavalry/Leafblower"><span class="tocnumber">2.3.5</span> <span class="toctext">Air Cavalry/Leafblower</span></a></li>
<li class="toclevel-3 tocsection-11"><a href="#Combined_Arms"><span class="tocnumber">2.3.6</span> <span class="toctext">Combined Arms</span></a></li>
</ul>
</li>
</ul>
</li>
<li class="toclevel-1 tocsection-12"><a href="#The_Forces_of_WW3"><span class="tocnumber">3</span> <span class="toctext">The Forces of WW3</span></a>
<ul>
<li class="toclevel-2 tocsection-13"><a href="#NATO-aligned"><span class="tocnumber">3.1</span> <span class="toctext">NATO-aligned</span></a>
<ul>
<li class="toclevel-3 tocsection-14"><a href="#United_States_of_America"><span class="tocnumber">3.1.1</span> <span class="toctext">United States of America</span></a></li>
<li class="toclevel-3 tocsection-15"><a href="#Great_Britain"><span class="tocnumber">3.1.2</span> <span class="toctext">Great Britain</span></a></li>
<li class="toclevel-3 tocsection-16"><a href="#West_Germany"><span class="tocnumber">3.1.3</span> <span class="toctext">West Germany</span></a></li>
<li class="toclevel-3 tocsection-17"><a href="#France"><span class="tocnumber">3.1.4</span> <span class="toctext">France</span></a></li>
<li class="toclevel-3 tocsection-18"><a href="#Canada"><span class="tocnumber">3.1.5</span> <span class="toctext">Canada</span></a></li>
<li class="toclevel-3 tocsection-19"><a href="#The_Netherlands"><span class="tocnumber">3.1.6</span> <span class="toctext">The Netherlands</span></a></li>
<li class="toclevel-3 tocsection-20"><a href="#Belgium"><span class="tocnumber">3.1.7</span> <span class="toctext">Belgium</span></a></li>
<li class="toclevel-3 tocsection-21"><a href="#Denmark"><span class="tocnumber">3.1.8</span> <span class="toctext">Denmark</span></a></li>
<li class="toclevel-3 tocsection-22"><a href="#Norway"><span class="tocnumber">3.1.9</span> <span class="toctext">Norway</span></a></li>
<li class="toclevel-3 tocsection-23"><a href="#ANZAC"><span class="tocnumber">3.1.10</span> <span class="toctext">ANZAC</span></a></li>
</ul>
</li>
<li class="toclevel-2 tocsection-24"><a href="#Warsaw_Pact"><span class="tocnumber">3.2</span> <span class="toctext">Warsaw Pact</span></a>
<ul>
<li class="toclevel-3 tocsection-25"><a href="#Soviet_Union"><span class="tocnumber">3.2.1</span> <span class="toctext">Soviet Union</span></a></li>
<li class="toclevel-3 tocsection-26"><a href="#East_Germany"><span class="tocnumber">3.2.2</span> <span class="toctext">East Germany</span></a></li>
<li class="toclevel-3 tocsection-27"><a href="#Poland"><span class="tocnumber">3.2.3</span> <span class="toctext">Poland</span></a></li>
<li class="toclevel-3 tocsection-28"><a href="#Czechoslovakia"><span class="tocnumber">3.2.4</span> <span class="toctext">Czechoslovakia</span></a></li>
<li class="toclevel-3 tocsection-29"><a href="#Cuba"><span class="tocnumber">3.2.5</span> <span class="toctext">Cuba</span></a></li>
</ul>
</li>
<li class="toclevel-2 tocsection-30"><a href="#Middle_Eastern_Powers"><span class="tocnumber">3.3</span> <span class="toctext">Middle Eastern Powers</span></a>
<ul>
<li class="toclevel-3 tocsection-31"><a href="#Israel"><span class="tocnumber">3.3.1</span> <span class="toctext">Israel</span></a></li>
<li class="toclevel-3 tocsection-32"><a href="#Iraq/Syria"><span class="tocnumber">3.3.2</span> <span class="toctext">Iraq/Syria</span></a></li>
<li class="toclevel-3 tocsection-33"><a href="#Iran"><span class="tocnumber">3.3.3</span> <span class="toctext">Iran</span></a></li>
</ul>
</li>
<li class="toclevel-2 tocsection-34"><a href="#Asian_Powers"><span class="tocnumber">3.4</span> <span class="toctext">Asian Powers</span></a></li>
<li class="toclevel-2 tocsection-35"><a href="#African_Powers"><span class="tocnumber">3.5</span> <span class="toctext">African Powers</span></a></li>
<li class="toclevel-2 tocsection-36"><a href="#Unofficial_Rules_-_Alternative_Nations_and_Special_Forces"><span class="tocnumber">3.6</span> <span class="toctext">Unofficial Rules - Alternative Nations and Special Forces</span></a></li>
<li class="toclevel-2 tocsection-37"><a href="#The_Neutral_Powers"><span class="tocnumber">3.7</span> <span class="toctext">The Neutral Powers</span></a>
<ul>
<li class="toclevel-3 tocsection-38"><a href="#Sweden"><span class="tocnumber">3.7.1</span> <span class="toctext">Sweden</span></a></li>
<li class="toclevel-3 tocsection-39"><a href="#Finland"><span class="tocnumber">3.7.2</span> <span class="toctext">Finland</span></a></li>
</ul>
</li>
</ul>
</li>
<li class="toclevel-1 tocsection-40"><a href="#FAQ/General_Bulletin"><span class="tocnumber">4</span> <span class="toctext">FAQ/General Bulletin</span></a></li>
<li class="toclevel-1 tocsection-41"><a href="#Books"><span class="tocnumber">5</span> <span class="toctext">Books</span></a></li>
<li class="toclevel-1 tocsection-42"><a href="#Gallery"><span class="tocnumber">6</span> <span class="toctext">Gallery</span></a></li>
<li class="toclevel-1 tocsection-43"><a href="#External_Links"><span class="tocnumber">7</span> <span class="toctext">External Links</span></a></li>
</ul>
</div>

<div class="mw-heading mw-heading2"><h2 id="The_Story">The Story</h2><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=1" title="Edit section: The Story">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>So, obviously the story of <i>Team Yankee</i> is a bit unrealistic but bear with us, alright? In 1985, the Soviet Union is dealing with mounting internal issues, and with the death of Leonid Brezhnev, the USSR was faced with a choice between Mikhail Gorbachev or another hardline Communist. In our world, Gorbachev was elected as the Premier of the Soviet Union, which would eventually lead to its collapse, but in the <i>Team Yankee</i> universe an old Stalinist took his place instead.
</p><p>Believing that after the disastrous war in Afghanistan, the best way to reassure the people of the Union's strength would be a victorious war with the West, and any seized resources could be used to immediately shore up the slumping economy (incidentally, this is probably why there was not a nuclear exchange and the subsequent destruction of the world).
</p><p>It was in the Persian Gulf that the USSR found its excuse to begin preparing for war. The Iran-Iraq war had been blazing for four years, and, though it was an active warzone, the trade of oil continued mostly unabated. That was until a pair of Iranian jets attacked and sank a Saudi tanker with huge loss of life. The United States began increasing its naval presence in the Gulf to prevent additional attacks on commercial vessels in international waters. As part of this action, on the 27th of July, the destroyer <i>USS Charles Logan</i> was patrolling off the Strait of Hormuz when it was rammed by a Soviet cruiser, which was ostensibly there to do the same thing. In the confusion, both ships fired on each other before retiring to their respective ports.
</p><p>Claiming that this was a blatant attack on a Soviet warship, the Warsaw Pact issued a statement of solidarity and then began to increase troop movements toward the Iron Curtain. In response, the United States began to react in kind, and over 100,000 National Guardsmen were federalized as frontline combat units started moving to their wartime posts. The Warsaw Pact subsequently invaded West Germany, driving through to part of the Netherlands, but its efforts were met with stiff resistance, and the fortunes of war could soon turn the other way.
</p>
<div class="mw-heading mw-heading2"><h2 id="The_Game">The Game</h2><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=2" title="Edit section: The Game">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p><i>Team Yankee</i> is a 15mm (about 1:100 scale) Table Top Wargame, usually played on a standard 6x4 game table. To play <i>Team Yankee</i>, you will need a tape measure (both inches and centimeters work), a whole bunch of D6 dice, an army of models, and some friends to play with (that one will probably be the toughest, to be honest).
</p>
<div class="mw-heading mw-heading3"><h3 id="Playing_the_game">Playing the game</h3><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=3" title="Edit section: Playing the game">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<dl><dt>Example Turn</dt></dl>
<p>What follows is a basic layout of a standard turn
</p><p><b>1. Starting Step</b><br />
This is where most of the administrative stuff happens. Check the Morale of your formations and units, roll for reserves, rally pinned units, free bogged-down tanks, remount bailed out tanks, remove smoke from the previous turn, etc., etc., etc.
</p><p><b>2. Movement Step</b><br />
Move your units (duh). The amount a unit can move is dictated by the terrain it has to deal with. The majority of orders are given in this phase as well.
</p><p><b>3. Shooting Step</b><br />
No problem cannot be solved through the application of superior fire power. <i>Team Yankee</i> uses abstraction rather than true line of sight, meaning that tanks clearly visible behind slopes may not actually be seen due to terrain height rulings. All shooting and artillery occurs in this phase, with smoke being fired before any other shooting.
</p><p><b>4. Assault Step</b><br />
Time to get up close and personal. Units charge into close quarters to beat the enemy to death with their rifle butts or crush them underneath their treads. Infantry teams don’t get saves in close combat, so be wary.
</p>
<div class="mw-heading mw-heading3"><h3 id="List_Building">List Building</h3><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=4" title="Edit section: List Building">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>Note that all lists are based on historically-based equipment at a specific point in time, even if that equipment was unique or incredibly rare.
</p><p>Army lists in <i>Team Yankee</i> are usually built from a single book or "codex" which tells you what your country has access to. Each nation has different "sub lists" but most follow three types: armoured and mechanized infantry. Armoured companies let you bring several platoons of tanks, while mechanized infantry does the same with infantry that can come in your bog-standard metal boxes or a metal box with an autocannon. Some armies have more unique options, discussed on their respective pages.
</p><p>NATO armies tend to be cheaper thanks to their smaller sizes, while Pact forces have much more units that are identical across the four nations. If you buy an M1 it can only be used for a USA army; paint a T-72 in Soviet green (without national emblems) and it can be used in four armies.
</p><p>Want a cheaper single army? Buy American (or any other NATO power). Want a cheaper collection and several army lists? Buy Soviet.
</p><p>Note: Team Yankee now has dynamic points, rendering point costs on cards and this site potentially obsolete. While the latest points can be found on Battlefront's website or their paywalled listbuilder, there is nothing stopping you from trying games out with points from publicly available sources!
</p><p><b>Force Command</b><br />
Your force will always have an HQ. Your Force Commander and 2nd in Command (also known as the meatshield) represents you in the game, commanding the battle on foot or some vehicle. If the Force commander dies, your army will begin to panic. Lose too many platoons and you will immediately lose the game. At higher point games, you may have two or more force commanders to mitigate this (as you will probably be forced to utilize multiple formations to fill out the points). For NATO Players, the Force Commander is generally a company commander wielding his company and any company-level support the higher-ups have deemed to send his way. For PACT players, the Force Commander is usually at the Battalion level, which is made up of several companies, to balance out the power differential between the average NATO and Pact units.
</p><p>HQS usually DO NOT count as platoons for Company, or even Battalion strength. They function as 40k independent characters do, so you would have four units on the field whether your company commander joined a platoon or ran around on their own.
</p><p><b>Combat Platoons</b><br />
AKA Troops choice: like with 40k, each organization chart will have a minimum requirement of a Company Commander and two platoons of troops, which could be <a href="/wiki/Motor_Rifle_Company" title="Motor Rifle Company">IFV-mounted infantry</a> or a unit of <a href="/wiki/Huey_Rifle_Platoon" title="Huey Rifle Platoon">heliborne infantry</a>. This is where your list building starts, with the size of your unit and taking additional weaponry like anti-tank weapons, medium machine guns, or anti-air missiles.
</p><p><b>Platoon Support</b><br />
Unlike 40k, platoon support is unique to each company. This is the reason you selected the specific Company: access to unique toys that your other companies or nations can't take. Historically, this would be a platoon from the support company of the battalion: infantry companies might have a mortar platoon, while armoured companies might have a platoon of vehicle-mounted ATGMs. Your platoon support may also have platoons of the alternate unit type: tank companies almost always have the option to take a platoon of infantry, and vice versa.
</p><p><b>Division Support</b><br />
These elements are the rarest systems in your army, and often among the most expensive options. Historically, it would be things like air support, heavy artillery or attached helicopter squadrons. This varies from nation to nation: some countries have platforms that serve <a href="/wiki/AMX_Roland" title="AMX Roland">crucial support roles but won't win the war for you</a> to <a href="/wiki/ADATS" title="ADATS">snowflake units that provide the teeth to your force</a>. These options are open to all company types, and should therefore be used to round out the weaknesses of your list. Additionally, platoons for troops like tanks and infantry might be purchasable here.
</p><p><b>Allied Support</b><br />
These are your "Allies of Convenience", to continue the 40k analogy. Generally, only one allied formation (company, battalion, whatever) is allowed. Generally this would mean NATO Allies for NATO countries, and vice versa for the Warsaw Pact (but not the Middle Eastern powers, who all want to kill each other and are much more uncaring in where they get their gear from). Additionally, smaller factions may have allied units that fall under the same lines as Divisional Support, just with a different flag. For example, Canadians have access to the German Leopard 2 and the American Abrams to round out their lack of modern battle tanks.
</p><p>These units do NOT count as platoons which add to your last stand count, so your army may rout if the last Canadian troops have been picked off even if half of your (American Allied) units are on the table. Like Division Support, this is taken to smooth out the rough edges of your list and might be very interesting if you like the idea of a British-French coalition battlegroup, or are a powergamer who just wants the best companies of each nation.
</p><p>As a disclaimer to the young teens reading this wiki and calling themselves a military expert, <i>Team Yankee</i> is a HISTORICAL FANTASY game. The models might represent real weapon systems, but the organization of lists ranges from relatively accurate to outright blasphemous. Pretty much all your tanks and artillery fired across kilometers in real life, but only fire up to several hundred meters on the tabletop (mostly for the same reason as in <a href="/wiki/Warhammer_40k" class="mw-redirect" title="Warhammer 40k">that other game</a>, you don't have an entire football stadium to play in). <a href="/wiki/M247_Sergeant_York" title="M247 Sergeant York">Prototypes that never made it past the testing phase can be found</a>, while organizational details have been simplified for gameplay purposes.
</p><p>For the prospective kommandant who reached this point, consider reading the rulebooks at your FLGS or read on to decide which nation might be for you.
</p>
<div class="mw-heading mw-heading3"><h3 id="List_Archtypes">List Archtypes</h3><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=5" title="Edit section: List Archtypes">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>Like any other tabletop game, each army has its own pros and cons leading to very distinct archetypes: just like the real-life counterparts, an infantry company will have a much happier time holding a town than a bunch of tanks. Here are a few of the many variants, found in the tournament scene and casual table:
</p>
<div class="mw-heading mw-heading4"><h4 id="Mechanized_Infantry">Mechanized Infantry</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=6" title="Edit section: Mechanized Infantry">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>Kings of the tournament scene, mechanized infantry are THE premium choice for players seeking cost efficiency, holding power or firepower in some cases. Over 90% of all infantry in the game arrives in a motorized tin can of some sort, meaning that these lists have an overabundance of machinegun fire. Some lists might use infantry fighting vehicles such as the <a href="/wiki/BMP" title="BMP">BMP</a> or <a href="/wiki/Marder_Zug" title="Marder Zug">Marder</a>, but most are characterized by hordes of cheap infantry in the cheapest transports. Mechanized lists are incredibly split in specialization depending on your faction of choice as well.
</p><p>In tournaments, the French and British are defined by the sheer amount of Milans they can bring to the field. They may lack in firefighting capability, but their ability to destroy armoured lists are second to none. They can be used in urban operations as well, but excel in open fields where their Milans can chew through tank after tank.
</p><p>The Soviet, Iranian and Polish lists are the Communist equivalent of the Milan horde; trading the latest in wargear for the latest in childbearing technology. While these troops lack in weapon systems that can engage armour from a distance, they are characterized by sheer numbers coupled with 3+ morale stats allowing them to keep pushing forward when other armies would fall back.
</p><p>On the other end of the spectrum are the spam lists of Czechs and Iraqis. Characterized by their horrendous morale and basic weaponry, these lists have little to no offensive capability. <a href="/wiki/Imperial_Guard" title="Imperial Guard">However, their low pointage allows you to bring waves of men to the field that will HOLD the line like no other.</a> In an urban setting, these troops can turn all buildings on your side of the field into deathtraps for enemy armour.
</p><p>Somewhere in the middle are Soviet <a href="/wiki/BTR-60" title="BTR-60">BTR</a>/ <a href="/wiki/BMP" title="BMP">BMP</a> and Dutch <a href="/wiki/YPR-765" title="YPR-765">YPR-765</a> lists. Typically, these lists would feature armoured elements and focus more on punching through the weak points of the enemy's line with the superior firepower of infantry fighting vehicles complementing a couple of tanks. A jack-of-all-trades list, these forces are capable of defending and can counterattack on a dime when required.
</p><p>Universally feared by all players and the cheapest unit in any force, the mechanized infantry are the benchmark of every other unit: a platoon only needs to kill 1-3 tanks to make its points back. For tournament players, prepare to build lists that counter infantry. For casual players, expect to see some form of them in every single game.
</p>
<div class="mw-heading mw-heading4"><h4 id="Armoured">Armoured</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=7" title="Edit section: Armoured">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>The poster boys of the game, Armoured forces rely on the overwhelming superiority of tanks to crush virtually any opposition in its path. These units represent the fastest, heaviest units in the army that are not only capable of taking ground, but holding it. Strong in standard games and deadly in larger tables, Armoured forces would be unmatched if not for their Achilles heel: overpriced units.
</p><p>Tank units often cost dozens of points for a single platoon, leaving them as niche choices for the average player. In a tournament setting where every point counts and every wasted unit may cost you the game, tanks are treated as specialized units in different lists. Some may use armour as <a href="/wiki/Chieftain" title="Chieftain">firebases</a>; <a href="/wiki/M1_Abrams" title="M1 Abrams">maneuver elements in a hammer and anvil force</a>, or solely as snipers <a href="/wiki/Leopard_2" title="Leopard 2">to destroy armour</a>. Regardless of their tournament viability, here are the traditional makeups of armoured lists.
</p><p>With unparalleled mobility and firepower, armoured lists excel on the attack. This greatly favors offensive nations such as the West Germans or the Soviet Union who can conduct ‘blitzkrieg’ tactics on the tabletop scale: rather than exploiting strategic weaknesses, these lists employ a mix of tank killers like the <a href="/wiki/T-64" title="T-64">T-64</a> and the <a href="/wiki/Leopard_2" title="Leopard 2">Leopard 2</a> to compliment the firepower of support tanks: outdated models that may not beat the latest metal boxes, but could chew through any other vehicle like a masochist on a sanding belt.
</p><p>Protection against missiles comes in the form of artillery. Other lists may occasionally get away without running artillery, but is not optional in the current meta. Used to protect your tanks from Milan spam or the tank killers of the enemy force, smoke is probably the most important task of the artillery in an armoured list, neutralizing Milans for you to get within their firing range, forcing Chieftains to move or even dividing the force to reduce the amount of return fire.
</p><p>The strongest armoured lists are anachronisms, with no nation having a single tank that does the job of both a tank killer and support. Hence, they are generally defined as lists that run a substantial amount of armour (two platoons or so) with singular platoons of infantry, artillery, reconnaissance, etc. For a competitive player choosing the path of an iron grave, consider using allies for access to ROF 2 brutal tanks to compliment your AT22 tank killers. If you are a Soviet player, rejoice! Your tanks are all-in-one and are countered by any form of missile, tank cannon or bomber. Have fun!
</p>
<div class="mw-heading mw-heading4"><h4 id="Cavalry">Cavalry</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=8" title="Edit section: Cavalry">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>Distinct from the armoured and mechanized archetypes, cavalry forces employ fast, mobile vehicles to outmaneuver the enemy while avoiding head-on engagements with the heaviest elements of the enemy list like tanks or infantry. While WILL be employing their own infantry and tank forces, cavalry forces are defined by their reliance on autocannon-armed vehicles to destroy soft-skinned vehicles like APCs, anti-air and artillery.
</p><p>Generally used for reconnaissance in a combined arms list rather than serving as the frontline troops who fight and die on your behalf, the British are known for having some of the best cavalry units with the Scorpion and Scimitar coming in low, cheap and with both variants having the firepower to take on anything but battle tanks. Hampered by their mediocre moving ROF, their main purpose is to deny spearhead movement to your opponent while threatening their soft skinned vehicles, providing an extremely dangerous (but easily answered) threat that hamper much more expensive units such as infantry and tanks from doing their job on the frontline.
</p><p>The only true Cavalry lists seen in tournaments are US Marine LAV lists, employing hordes of moving ROF 3 LAVs to outmaneuver, threaten, and destroy soft-skinned vehicles. However, it must be noted that cavalry forces still rely on infantry and armour to actually win the game: your cavalry are force multipliers to neutralize the support elements of your opponent, not the ones who will carry the day on their own.
</p>
<div class="mw-heading mw-heading4"><h4 id="Air_Assault">Air Assault</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=9" title="Edit section: Air Assault">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>Rarely seen in the tournament scene aside from Soviet VDV lists, Airborne lists employ helicopter infantry and their superior mobility to win battles. Almost universally worthless in a 6x4 game where the marginal infantry buff and loss of fighting transports can be crippling, air assault forces have a niche of larger team games spanning several maps. Whether used to grab vulnerable objectives or serve as firemen where the line is weakest, air assault troops have greatly different roles among the nations that can field them: the USA, Soviet Union and British.
</p><p>The American air assault list is the archetypical airborne force: lightly equipped, highly trained and absolutely deadly in firefights, these units are barely worth their weight against armour but are almost unparalleled in a firefight. Combining Soviet morale with American firepower, heliborne infantry may not be able to kill a tank to save their life but are best suited to urban warfare or any other setting where dug-in infantry must die.
</p><p>While the US Huey technically has its M60s, consider them as one-time-use guns that cannot be considered fire support, unlike an M113.
</p><p>Soviet VDV lists are THE most accurate depiction of a proper air assault operation: deploying highly trained, versatile troops in highly dangerous environments while supported with helicopter gunships. The most "competitive" of the three nations, VDV troops are equipped not only to win infantry fights, but also carry the heavy weapons that make infantry what they are: unmovable rocks that take a disproportionate amount of firepower to move, while having the tools to destroy armour that strays too close. While your infantry are few, your transports are terror on rotors: enter the Hind.
</p><p>A flying tank unmatched by the West until the development of the Apache, the Hind is one of the only gunships with transport capacity. While nerfed by its lack of stationary ROF and 3+ to hit, Hinds have a weapon for any target. See a Merkava? The Hind can kill it. Unprotected artillery? The Hind can kill it. Infantry hordes in the open? The Hind can fuck them all at the same time.
</p><p>By playing the VDV, you are committing to a list that combines air assault and air cavalry through the investment of points into gunships. Add on some Frogfoots and the VDV becomes a tournament worthy list that preys on any meta without sufficient anti-air. Not to mention, your blue berets are more than a match for the average foot soldier from the capitalist west...
</p><p>The British air assault list are a competitive unit that sees fringe play, albeit as a fever dream that would make the Sergeant York wet. Worthless on their own and pathetic in a firefight, the Gordon Highlanders see their niche as a Milan horde that happen to ride in helicopters.
</p>
<div class="mw-heading mw-heading4"><h4 id="Air_Cavalry/Leafblower"><span id="Air_Cavalry.2FLeafblower"></span>Air Cavalry/Leafblower</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=10" title="Edit section: Air Cavalry/Leafblower">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>Air Cavalry lists, unlike their real-life equivalents, are forces that spam airpower to win battles. Combining strike aircraft with helicopter gunships, these lists aim to destroy air-defence units before destroying the enemy force piece by piece. While most nations have access to bombers and ATGM helicopters, only the USA, Soviets and French have access to true leafblower lists; given their access to gunships like the <a href="/wiki/MI-24_Hind" title="MI-24 Hind">MI-24 Hind</a>, <a href="/wiki/Cobra" title="Cobra">Cobra</a>, and <a href="/wiki/Gazelle_Helicopter" title="Gazelle Helicopter">Gazelle</a>.
</p><p>Prospective commanders should note that these are all-in lists with over 40 points being funneled into airborne units and are easily countered by tournament metas. Essentially, you are praying that your opponent does not aim to counter your lists; given that Air Cavalry aims to outrace a platoon of dedicated air killers like <a href="/wiki/SA-8_Gecko" title="SA-8 Gecko">SA-8 Geckos</a> or <a href="/wiki/Tracked_Rapier" title="Tracked Rapier">Rapier</a>. Uncounterable for the casual player who does not plan ahead, and easily beaten by tournament players who do their homework. They may fulfill your ride of the valkyrie fantasies, but will lead to games which end faster than your opponent's patience.
</p><p>Not recommended if you wish to stay friends with your opponents. Acceptable (but weak) if you want to win games.
</p>
<div class="mw-heading mw-heading4"><h4 id="Combined_Arms">Combined Arms</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=11" title="Edit section: Combined Arms">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>Like most tabletop games, <i>Team Yankee</i> favours players who can mix and match each of the previous components, diluting the strength of each troop type and compensating with the power of diversity (yay!). As implied by the previous articles, building a spam list of infantry or tanks might be acceptable in a multiplayer game, but will lead to your quick and laughable defeat in a competitive 1v1 game. Without artillery, your infantry and tanks can’t attack without taking a million casualties. Without cavalry, your tanks risk being flanked and blown up. Without infantry, your tanks and cavalry will not take objectives.
</p><p>The overwhelming majority of competitive lists feature an infantry or armoured company with support elements to cover all angles. While an infantry list might see itself playing the defensive under ideal circumstances, the counterblow from a tank platoon coming from reserves can decisively swing games in your favour. Similarly, armoured lists require smoke to cover the advance of your tanks or mounted infantry. Experienced players may dabble in ‘all-in’ lists, but you, prospective general, will find the best results when your lists have no clear weakness.
</p><p>Want to muddy the mixture? Consider taking combat troops as allies with your "chosen" nation providing nothing more than combat (and moral) support.
</p><p>Mandatory:
2-6 Combat Troops (2 platoons of tanks or infantry, 1 platoon of infantry/tanks)
1-2 Artillery (for smoke and pinning)
1-4 Recon (for spearheading and/or denying spearheads)
1-2 Air Defence (Multirole air defence acceptable below 26 points, dedicated air defence required above 30 points)
</p><p>Optional:
1-2 Air support (used as suicide units)
1-1 Armoured ATGM carriers (overlaps with combat troops)
</p>
<div class="mw-heading mw-heading2"><h2 id="The_Forces_of_WW3">The Forces of WW3</h2><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=12" title="Edit section: The Forces of WW3">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>With the new Ally rules, take the following with a pinch of salt. Using the combat units of an ally faction as the bulk of your force while keeping your 'actual' faction for its support choices is a totally legal (if cheesy) option. The scores are strictly in relation to one another; and does not account for terrain, list building and other stuff.
</p>
<pre>The Breakdown Scores:
5: Auto-include for competitive lists.
4: Good for the purpose, if overshadowed by other factions.
3: Not terrible, but needs a good reason to be included.
2: Not recommended due to inefficiency.
1: Overshadowed by other options in the same force organisation.
-: Role filled by Allied units within the force organisation. Minor nations only.
</pre>
<div class="mw-heading mw-heading3"><h3 id="NATO-aligned">NATO-aligned</h3><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=13" title="Edit section: NATO-aligned">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div style="margin-top:1em;margin-bottom:1em"><i>"The Parties to this Treaty reaffirm [...] [t]hey are determined to safeguard the freedom, common heritage and civilisation of their peoples, founded on the principles of democracy, individual liberty and the rule of law. They seek to promote stability and well-being in the North Atlantic area. They are resolved to unite their efforts for collective defence and for the preservation of peace and security. They therefore agree to this North Atlantic Treaty"</i>
<dl><dd><small>– The North Atlantic Treaty</small></dd></dl></div>
<p>The free world takes its freedom seriously, and armies operate very differently from one another. Entries for similar units (M113 mortars) will have different roles when used in another nation, while most countries have their own unique units which may similar versions but nothing completely identical. NATO is generally more beginner friendly, but varies between nations when it comes to cost and budgeting.
</p>
<div class="mw-heading mw-heading4"><h4 id="United_States_of_America">United States of America</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=14" title="Edit section: United States of America">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div style="margin-top:1em;margin-bottom:1em"><i>"I can no longer sit back and allow Communist infiltration, Communist indoctrination, Communist subversion and the international Communist conspiracy to sap and impurify all of our precious bodily fluids."</i>
<dl><dd><small>– General Jack D. Ripper</small></dd></dl></div>
<p><u>Difficulty</u>: 1/5 (excellent for beginners!)
</p><p>It may not have shown up on time for the last two world wars, but it sure has brought some firepower into this one. The principal founder of NATO and its strongest military power, the United States moved immediately to bring its full strategic might to bear against the seemingly-endless masses charging west from behind the Iron Curtain.
</p><p>Three of the USA's armed forces feature in this game, primarily its Army; the United States Army is one of the most technologically advanced forces on the Battlefield. An all-volunteer force, the average US soldier is backed up by some of the most advanced weapon systems rumbling into war with him (including the world's most used METUL BOX). Particularly the principal tank of the US forces in Europe, the M1 Abrams is arguably the most influential main battle tank of the '80s, influencing almost every other tank design in the Western world.
</p><p><i>Stripes</i> covers most frontline combat units in the US Armed Forces, from an Amphibious Assault Unit to an Airborne Infantry Company. Their units may not be the best, but you have so many options in your list that you should have a counter for anything your opponent brings up. This versatility makes the US the only faction to rival the Soviets, matching their cost efficiency with incredibly flexible listbuilding.
</p><p>For players concerned with historical accuracy, remember to toss out the Yorks, RDF/LTs and the Hueys (except for Marine Airborne)!
</p><p>Defining Units: <a href="/wiki/M1_Abrams" title="M1 Abrams">M1 Abrams</a>, <a href="/wiki/M163_VADS" title="M163 VADS">M163 VADS</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>Most versatile faction in the game, with options to fill almost all roles.</li>
<li>Ideal for Armored and combined arms playstyles, with the flexibility to attack or defend.</li>
<li>Decently easy to learn, and is rather straightforward.</li>
<li>Ability to upgrade entire force to carry AT23 TOW2s</li>
<li>Capitalism</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Capitalism</li>
<li>Second most expensive faction in-game.</li>
<li>Poor cost efficiency compared to other NATO equivalents.</li>
<li>Limited long-range anti-tank – your TOW tax quickly adds up when combating this.</li>
<li>Healthcare budget was invested in the ACU project.</li></ul>
<pre>The Breakdown:
Infantry: Solid and cost-efficient. 4/5
Transports: The best "free" transports in the game. 3/5
Tanks: All the flavors of M1s. 4/5
Anti-Tank: No longer cost efficient, but packing serious heat. 4/5
Recon: Decent Army options, good Marine options. 3/5
Artillery: Decent, if expensive, mortars. 3/5
Aircraft: Best helicopters, mediocre aircraft. 4/5
Anti-Air: Overpriced. Where's the Air Force?? 2/5
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">US Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/M1_Abrams" title="M1 Abrams">M1 Abrams</a> • <a href="/wiki/M60_Patton" title="M60 Patton">M60 Patton</a> • <a href="/wiki/M551_Sheridan" title="M551 Sheridan">M551 Sheridan</a> • <a href="/wiki/RDF/LT" title="RDF/LT">RDF/LT</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/M113_Armored_Personnel_Carrier" title="M113 Armored Personnel Carrier">M113 Armored Personnel Carrier</a> • <a href="/wiki/UH-1_Huey" title="UH-1 Huey">UH-1 Huey</a> • <a href="/wiki/AAVP7" title="AAVP7">AAVP7</a> • <a href="/wiki/Bradley_Fighting_Vehicle" title="Bradley Fighting Vehicle">Bradley Fighting Vehicle</a> • <a href="/wiki/Pickup_Trucks" title="Pickup Trucks">Pickup Trucks</a> • <a href="/wiki/CH-46_Sea_Knight" title="CH-46 Sea Knight">CH-46 Sea Knight</a> • <a href="/wiki/CH-47_Chinook" title="CH-47 Chinook">CH-47 Chinook</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/US_Mech_Platoon" title="US Mech Platoon">US Mech Platoon</a> • <a href="/wiki/Marine_Rifle_Platoon" title="Marine Rifle Platoon">Marine Rifle Platoon</a> • <a href="/wiki/Huey_Rifle_Platoon" title="Huey Rifle Platoon">Huey Rifle Platoon</a> • <a href="/wiki/HMMWV_Scout_Section" title="HMMWV Scout Section">HMMWV Machine Gun Platoon</a> • <a href="/wiki/Light_Motor_Infantry_Platoon?action=edit&amp;redlink=1" class="new" title="Light Motor Infantry Platoon (page does not exist)">Light Motor Infantry Platoon</a> • <a href="/wiki/Irregular_Militia_Group" title="Irregular Militia Group">Irregular Militia Group</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/M106_Heavy_Mortar_Carrier" title="M106 Heavy Mortar Carrier">M106 Heavy Mortar Carrier</a> • <a href="/wiki/M109_Howitzer" title="M109 Howitzer">M109 Howitzer</a> • <a href="/wiki/LAV-M" title="LAV-M">LAV-M</a> • <a href="/wiki/M270_MLRS" title="M270 MLRS">M270 MLRS</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/M163_VADS" title="M163 VADS">M163 VADS</a> • <a href="/wiki/M48_Chaparral" title="M48 Chaparral">M48 Chaparral</a> • <a href="/wiki/M247_Sergeant_York" title="M247 Sergeant York">M247 Sergeant York</a> • <a href="/wiki/HMMWV_SAM" title="HMMWV SAM">HMMWV SAM</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/M901_ITV" title="M901 ITV">M901 ITV</a> • <a href="/wiki/HMMWV-TOW" title="HMMWV-TOW">HMMWV-TOW</a> • <a href="/wiki/LAV-AT" title="LAV-AT">LAV-AT</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/M113_OP" title="M113 OP">M113 FIST</a> • <a href="/wiki/M113_Recce" title="M113 Recce">M113 Scout Section</a> • <a href="/wiki/HMMWV_Scout_Section" title="HMMWV Scout Section">HMMWV Scout Section</a> • <a href="/wiki/LAV-25" title="LAV-25">LAV-25</a> • <a href="/wiki/Bradley_Fighting_Vehicle" title="Bradley Fighting Vehicle">Bradley Fighting Vehicle</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/A-10_Warthog" title="A-10 Warthog">A-10 Warthog</a> • <a href="/wiki/AV-8_Harrier" title="AV-8 Harrier">AV-8 Harrier</a> • <a href="/wiki/AH-1_Cobra_Attack_Helicopter" title="AH-1 Cobra Attack Helicopter">AH-1 Cobra Attack Helicopter</a> • <a href="/wiki/AH-64_Apache_Attack_Helicopter" title="AH-64 Apache Attack Helicopter">AH-64 Apache Attack Helicopter</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="Great_Britain">Great Britain</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=15" title="Edit section: Great Britain">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div style="margin-top:1em;margin-bottom:1em"><i>"Why do you suppose we went into it?"<br />"To strengthen the brotherhood of free Western nations."<br />"Oh really, we went in to screw the French by splitting them off from the Germans."</i>
<dl><dd><small>– Yes, Minister</small></dd></dl></div>
<p><u>Difficulty</u>: 2/5 (Good for beginners and vets!)
</p><p>Steadfast, courageous, and absolutely devoted to their time-honoured traditions of tea, crumpets, and silly hats, the British Armed Forces became a founding member of NATO after World War II, in which they earned great fame for their many triumphs over impossible odds. Two major commands, British Army of the Rhine and Royal Air Force Germany, were dedicated to stand guard against the threat of Soviet invasion and have dutifully done so for 40 years. The British military is well-known for its discipline, professionalism, actually showing up on time for world wars (not like those louts across the pond), and valiantly holding out until an ally can come and actually win the war (usually those louts across the pond).
</p><p>Thanks to a little disagreement on the far side of the Atlantic in 1982 (not to mention the decades-long Troubles in Northern Ireland), the British military is one of only a few in NATO with combat veterans in its ranks going into the fight. It may not have the numbers or superpower status that it did in the glory days of the Empire, but as Argentina could tell you, it can still fight with the best of them. When the Warsaw Pact barged westward and brought war to Europe for the third time in a century, the British forces in West Germany stubbornly refused to give ground, forcing itsr enemy to bypass it rather than sacrifice the entire invasion's timetable. The rules for these tea-chugging bastards are found in <i>Iron Maiden</i> and updated rules can be found in "WW3: British".
</p><p>The Brits lack the cutting-edge advanced technology of the other NATO forces (Advanced Stabilisers, Thermal Imaging except on the Challenger) but compensate with sheer firepower and ridiculously well-armoured tanks. Thanks to their Assault 3+ Infantry and abundance of units which benefit from staying still and taking potshots like the Chieftain and Milan, the British excel on the defence; sipping tea and destroying anything which strolls into their fields of fire. Should the enemy fix bayonets, you have assault 3+ on most infantry and vehicles, a lynchpin that makes the entrenched British rifleman one of the most resilient units in the game.
</p><p>Also there is one other slight thing to mention with regard to the British during this time period: they are Troubled, the Good Friday Agreement which ended (or at least paused) The Troubles would not be signed for another 13 years (1998). What does that mean for <i>Team Yankee</i>? Well, likely nothing, but in real life you could bet your ass the Soviets would love to pour gasoline on that little fire to try and distract the Brits, so if we ever get a partisan list or something, maybe keep an eye open for that.
</p><p>Defining Units: <a href="/wiki/Chieftain" title="Chieftain">Chieftain</a>, <a href="/wiki/Milan_Section_(Mechanized)" title="Milan Section (Mechanized)">Milan Section</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>One of the strongest factions on the defensive.</li>
<li>Best infantry in the game with plentiful ATGMs on human (and armored) platforms.</li>
<li>Ideal for defensive or infantry players.</li>
<li>Has the almost invincible, if overcosted, Challenger.</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Lacks units that can effectively fight while on the move.</li>
<li>Seriously struggles to damage heavy MBTs.</li>
<li>Vulnerable to smoke and rushes; units rely on staying still to deliver the most firepower.</li>
<li>Commonly seen as the seal clubber's favorite due to superior infantry stats and milan spam, which makes new players ragequit.</li>
<li>Everything, absolutely <i>everything</i> stops for tea at four o'clock.</li></ul>
<pre>The Breakdown: 
Infantry: Excellent defence and long ranged AT, poor offensive abilities. 4/5
Transports: Average APCs and IFVs alike. 3/5
Tanks: Expensive, armoured monsters with deadly firepower but incapable of mobile warfare. 4/5
Anti-Tank: Excellent options for dealing with previous generation tanks, struggles against 20+ armour. 3/5
Recon: Dangerous but squishy. 3/5
Artillery: Good mid-low caliber pieces. 4/5
Aircraft: Best bomber, overcosted helicopters. 3/5
Anti-Air: Excellent Rapier, ludicrously good Marksman, mediocre Spartan Blowpipe. 4/5
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">British Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/Chieftain" title="Chieftain">Chieftain</a> • <a href="/wiki/Challenger_1" title="Challenger 1">Challenger 1</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/CVRT#Spartan_.28APC.29" title="CVRT">Spartan Transport</a> • <a href="/wiki/FV430_Series#FV_432_Armored_Personnel_Carrier" title="FV430 Series">FV432 Transport</a> • <a href="/wiki/FV510_Warrior" title="FV510 Warrior">FV510 Warrior</a> • <a href="/wiki/Lynx_Helicopter#Lynx_AH-1" title="Lynx Helicopter">Lynx Transport</a>
</td></tr>
<tr>
<th nowrap="">Infantry
</th>
<td><a href="/wiki/British_Mechanized_Company" title="British Mechanized Company">Mechanized Company</a> • <a href="/wiki/Milan_Section_(Mechanized)" title="Milan Section (Mechanized)">Milan Section (Mechanized)</a> • <a href="/wiki/Airmobile_Company" title="Airmobile Company">Airmobile Company</a> • <a href="/wiki/Milan_Platoon_(Airmobile)" title="Milan Platoon (Airmobile)">Milan Platoon (Airmobile)</a> • <a href="/wiki/Support_Troop" title="Support Troop">Support Troop</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/FV430_Series#FV_433_Self_Propelled_Artillery" title="FV430 Series">Abbot Field Battery</a> • <a href="/wiki/M109_Howitzer#British_Variant" title="M109 Howitzer">M109 Field Battery</a> • <a href="/wiki/FV430_Series#FV_432_Mortar_Carrier" title="FV430 Series">FV432 Mortar Carrier</a> • <a href="/wiki/M270_MLRS" title="M270 MLRS">M270 MLRS</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/CVRT#Spartan_.28Blowpipe.29" title="CVRT">Spartan Blowpipe</a> • <a href="/wiki/Tracked_Rapier" title="Tracked Rapier">Tracked Rapier</a> • <a href="/wiki/Chieftain_Marksman" title="Chieftain Marksman">Chieftain Marksman</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/CVRT#Striker" title="CVRT">Striker</a> • <a href="/wiki/CVRT#Spartan_MCT" title="CVRT">Spartan MCT</a> • <a href="/wiki/FV430_Series#FV_438_Swingfire" title="FV430 Series">Swingfire</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/FV430_Series" title="FV430 Series">FV432 FOO</a> • <a href="/wiki/CVRT#Spartan_.28Command.29" title="CVRT">Scorpion</a> • <a href="/wiki/CVRT#Scimitar" title="CVRT">Scimitar</a> • <a href="/wiki/FV721_Fox" title="FV721 Fox">FV721 Fox</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/AV-8_Harrier" title="AV-8 Harrier">Harrier Jump Jet</a> • <a href="/wiki/Lynx_Helicopter#Lynx_AH-1_TOW" title="Lynx Helicopter">Lynx HELARM</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="West_Germany">West Germany</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=16" title="Edit section: West Germany">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div style="margin-top:1em;margin-bottom:1em"><i>"Well that certainly doesn't apply to the Germans..."<br />"No no, they went in to cleanse themselves of genocide and apply for readmission to the human race."</i>
<dl><dd><small>– Yes, Minister</small></dd></dl></div>
<p><u>Difficulty</u>: 4/5 (Challenging listbuilding.)
</p><p>Following the complete destruction of Nazi Germany in 1945, about half of the country was occupied by the British, French and Americans, who merged their three occupation zones to form the Federal Republic of Germany. From its capital in Bonn, West Germany's leaders have focused their efforts on redeeming (West) German standing in the world through a restored representative democracy, a careful and conservative foreign and defense policy, and some truly outstanding cars, wurst and beer. And thanks to their longstanding membership in the NATO alliance, (half of) Germany gets to be the <i>good guys</i> this time!
</p><p>West Germany was the first featured expansion in "Team Yankee," centering around the Bundeswehr's Heer, one of two current successors to the legendary German Army of the past. With their homeland invaded for a second time by their enemy from two previous world wars, the West Germans are intensely motivated and have all the tenacity, discipline and professionalism of their fathers and grandfathers. Their former countrymen, the East Germans, are among the leading forces of the Warsaw Pact, making the war especially personal as both German armies do their utmost to see that their cause triumphs. The West Germans are literally battling in their own streets, homes and fields, while the East Germans are leaping at their chance to forge a unified, socialist Germany. The Rules for the West Germans can be found in "West German", which replaced Leopard and Panzertruppen.
</p><p>The West Germans have continued the famous German tradition of quality over quantity and then some: their units rank among the very best (and most expensive) in the entire game. The perfect example is the Leopard 2, a monument to armoured superiority that costs eleven points per tank, as opposed to a mere four per tank for the East Germans' T-72M. One exception is the Leopard 1; your budget tank at 3 points. In addition to Thermal Imaging, they field devastating units like the Gepard Flakpanzer and the Panavia Tornado fighter-bomber, which can make their points back over several times in the hands of an effective commander. A well-balanced army capable of different playstyles, but ultimately held back by its inability to sustain losses. Expect to be outnumbered 2-1 against NATO, or 3-1 or even 4-1 against PACT forces.
</p><p>Defining Units: <a href="/wiki/Leopard_2" title="Leopard 2">Leopard 2</a>, <a href="/wiki/Marder_II_Zug" title="Marder II Zug">Marder II Zug</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>Strongest armoured units in the game.</li>
<li>Soviet-equivalent morale.</li>
<li>Ideal for aggressive or challenge-seeking players.</li>
<li>Hard-hitting units that can punish your opponent's mistakes very harshly.</li>
<li>Ex-Nazis.</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Ex-Nazis.</li>
<li>Small units with some of the game's most expensive models.</li>
<li>Poorly suited to attrition tactics.</li>
<li>Forgot their cold-weather gear AGAIN.</li></ul>
<pre>The Breakdown:
Infantry: Effective, but few and expensive. 2/5
Transports: Strongest transport in the game, but no built-in missile. 4/5
Tanks: Overcosted Leopard 2s, decent Leopard 1s. 2/5
Anti-Tank: ATGMs expensive and few. Role filled by Leopard 2s. 1/5
Recon: Cheap and dangerous. 3/5
Artillery: Solid NATO artillery. 4/5
Aircraft: Good bomber, overcosted helicopters. 2/5
Anti-Air: Versatile, competitive options. 4/5
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">West German Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/Leopard_2" title="Leopard 2">Leopard 2</a> • <a href="/wiki/Leopard_1" title="Leopard 1">Leopard 1</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/Fuchs_Transportpanzer" title="Fuchs Transportpanzer">Fuchs Transportpanzer</a> • <a href="/wiki/Marder_II_Zug" title="Marder II Zug">Marder II Zug</a> • <a href="/wiki/Marder_Zug" title="Marder Zug">Marder Zug</a> • <a href="/wiki/M113_Armored_Personnel_Carrier" title="M113 Armored Personnel Carrier">M113 Armored Personnel Carrier</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/Panzergrenadiers" title="Panzergrenadiers">M113 / Marder Panzergrenadier Zug</a> • <a href="/wiki/Aufkl%C3%A4rungs_Zug?action=edit&amp;redlink=1" class="new" title="Aufklärungs Zug (page does not exist)">Aufklärungs Zug</a> • <a href="/wiki/Fallschirmjager_Zug" title="Fallschirmjager Zug">Fallschirmjager Zug</a> • <a href="/wiki/Gebirgsjager_Zug?action=edit&amp;redlink=1" class="new" title="Gebirgsjager Zug (page does not exist)">Gebirgsjager Zug</a> • <a href="/wiki/Jager_Zug?action=edit&amp;redlink=1" class="new" title="Jager Zug (page does not exist)">Jager Zug</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/Raketenwerfer_Batterie" title="Raketenwerfer Batterie">Raketenwerfer Batterie</a> • <a href="/wiki/M109_Howitzer" title="M109 Howitzer">M109 Howitzer</a> • <a href="/wiki/M106_Heavy_Mortar_Carrier" title="M106 Heavy Mortar Carrier">M113 Panzermörser Zug</a> • <a href="/wiki/M270_MLRS" title="M270 MLRS">M270 MLRS</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/Roland_Flak_Batterie" title="Roland Flak Batterie">Roland Flak Batterie</a> • <a href="/wiki/Gepard_Flakpanzer_Batterie" title="Gepard Flakpanzer Batterie">Gepard Flakpanzer Batterie</a> • <a href="/wiki/Fliegerfaust_Gruppe" title="Fliegerfaust Gruppe">Fliegerfaust Gruppe</a> • <a href="/wiki/Wiesel_Flugabwehr_Zug" title="Wiesel Flugabwehr Zug">Wiesel Flugabwehr Zug</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/Jaguar_Jagdpanzer" title="Jaguar Jagdpanzer">Jaguar Jagdpanzer</a> • <a href="/wiki/Kanonenjagdpanzer" title="Kanonenjagdpanzer">Kanonenjagdpanzer</a> • <a href="/wiki/Wiesel_TOW" title="Wiesel TOW">Wiesel TOW</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/Luchs_Spah_Trupp" title="Luchs Spah Trupp">Luchs Spah Trupp</a> • <a href="/wiki/M113_OP" title="M113 OP">M113 OP</a> • <a href="/wiki/Marder_II_Zug" title="Marder II Zug">Marder II Zug</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/Tornado" title="Tornado">Tornado</a> • <a href="/wiki/BO-105P" title="BO-105P">BO-105P</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="France">France</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=17" title="Edit section: France">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div style="margin-top:1em;margin-bottom:1em"><i>"Going to war without France is like going hunting without an accordion."</i>
<dl><dd><small>– Jed Babben</small></dd></dl></div>
<p><u>Difficulty</u>: 3/5 (Beginner unfriendly, many glass cannons.)
</p><p>The gall of those cultureless, crass Americans! We hate all of them! Our king bankrupted us to save them in their "Revolutionary War," and now they make memes of us on the internet!
</p><p>Despite the many dank memes and jokes about French military incompetence on the internet today, France has a long, long history of kicking ass with one of the largest and most powerful armed forces in human history. It may seem funny to mock them now, but nobody was laughing as Napoleon stomped one opponent after another into the dust, and millions of French soldiers held the line against the Kaiser's armies in the Great War, whereas the Americans couldn't be bothered to show up until 1917. France also <s>let the Germans take everything</s> was one of the major Allied powers in World War II, and French soldiers repeatedly making last stands against the Germans bought badly-needed time for the British evacuations at Dunkirk, saving not only <s>those stupid English</s> their British allies from getting overrun by the Nazis, but maybe also the world.
</p><p>As explained in "Free Nations," France sort-of left NATO under Charles de Gaulle, a... very complicated man whose egomania could well have one-upped Douglas MacArthur if they hadn't been kept on totally separate sides of the planet. To summarize, de Gaulle fought nails and teeth (and all the rest too) to keep <i>his</i> France independent: politically, economically and militarily. This lead to France having its own military industry and designs and also lead to it leaving-but-not-really-leaving NATO and expelling all non-French military forces stationed on French soil. Secret agreements were made, however, and France retained the right to declare its re-integration into the NATO military alliance if it saw fit to do so; i.e. in case of WW3/something grave enough that would threaten France directly. The reasons for de Gaulle's stubbornness are multiple but the two main ones were that he wanted no part in what he fully expected to be "League of Nations II: Incompetence Boogaloo" or being pressured into sending his soldiers into conflicts where France had neither cause to nor interest in participating. Early in the events of "Team Yankee", seeing that a major war in Europe was on the horizon for the third time in a single century, France officially rejoined NATO in full. The Communist hordes will not find us such easy prey <s>as the Germans did</s> as they may expect, <i>mon ami</i>.
</p><p>As of 1985, France is one of the few NATO nations with genuine combat experience after World War II, alongside the United Kingdom and the United States, and it has the third-largest number of atomic weapons in the world - a distant third behind USA and the USSR, mind you, but third-largest nonetheless. The French ORBAT is unlike any of the major military powers, with their early Cold War history covering the first and second Indochinese (Vietnam) wars and their different mission needs. The post-WWII/Indochine French army has a doctrine that can be summarized in one sentence: "Engage the enemy on your own terms; never his!". Lacking a tank capable of trading blows with any modern platform and near-universal <s>cowardice in the ranks</s> 5+ morale among French personnel, a French commander must rely on maneuver and a terrifying abundance of gun platforms with Brutal to cripple an enemy's force before taking significant damage. In fact, among the NATO nations, the French were the only ones to eventually adopt autoloaders for their main battle tanks (starting only with the Leclerc, though), but they also tend to come from the 'speed is armour' school of tank design, which made them a bit glassy both in and out of the game. While similar to the Canadians in their lists naturally countering BMP and infantry spam, they lack the moosemen's balls and require a different playstyle to excel. They do have Milan spam if that's your thing though (you powergaming <i>bâtard</i>).
</p><p>Defining Units: <a href="/wiki/AMX-10_RC" title="AMX-10 RC">AMX-10 RC</a>, <a href="/wiki/Gazelle_Helicopter" title="Gazelle Helicopter">Gazelle 20mm</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>Strong firepower on even the lightest units</li>
<li>Milan AT spam on par with the Brits.</li>
<li>Ideal for aggressive or experienced players.</li></ul>
<p><br />
</p>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Tissue-thin armour made from stale baguettes.</li>
<li><s>Cowards</s> Unreliable (seriously, do NOT expect Morale 5+ troops to stay in the fight.)</li>
<li>Smell like bad cheese.</li></ul>
<pre>The Breakdown:
Infantry: Good firepower but unreliable morale. 3/5
Transports: You get what you pay for: very solid. 4/5
Tanks: Incapable of tanking damage for the army. 3/5
Anti-Tank: Milan spam just got stronger. 5/5
Recon: Deadliest 'recon' units in the game. 5/5
Artillery: Lacking in utility arty. 2/5
Aircraft: Fragile but VERY deadly when played well. 4/5
Anti-Air: Respectable, but expensive. 3/5
</pre>
<p><br />
</p>
<div class="toccolours mw-collapsible mw-collapsed" style="100%">
<p>A Quick Note About the Morale Thing
</p>
<div class="mw-collapsible-content">
<p>Almost universally in Team Yankee, the French have <i>shit</i> morale, and this is a little weird at first glance. After all, the "ha ha, France = surrender monkeys" meme is about as nuanced and accurate as a company of Soviet motor rifles - especially by 1985. The French army has more actual recent combat experience than nearly any other playable nation, and previous morale crises have only improved the <i>Armée de Terre'</i>s ability to deal with such issues. So, what gives?
</p><p>Turns out, much like a few other terms for various Battlefront franchises, "Morale" is a slight misnomer. To be precise, the poor roll value that the French have isn't to represent that they are somehow more cowardly (the parallel 3+ Courage roll indicates as much), but rather to integrate French doctrine into the game, since most nation-specific special rules have been removed in order to streamline the rules. You see, in older FoW versions there used to be a dozen different special rules indicating unique attributes that would modify the two base values for specific traits. Courage, Rally, Assault and Counterattack are all new, and were created so as to whittle down the truly obscene rules clutter that was starting to really drag down games of FoW.
</p><p>But that still doesn't answer the question <i>"Why are my goddamn frogs running away so much?"</i>. The answer is simple: <s>the chemicals in the water turned them gay</s> they're being ordered to retreat: the French just don't stick around for a slugging match they fully know they simply can't win! If the French learned anything from the various wars of the 20th century, it's that they have to be able to give ground for time and that they absolutely do not have the ability to engage in attritional slogs and trade casualties for the same. As they quickly realized going solo meant they would never be able to field armor in the same volumes the Soviets could, the French army doctrine evolved into a very mobile and elastic thing that put their entire emphasis on high mobility with lighter motorized units, creating a 1985 doctrine of maneuver warfare with lightly armoured units. <a href="/wiki/Skub" title="Skub">The more callous say they just mixed Guderian's <i>blitzkrieg</i> with Model's <i>schild und schwert</i></a>, however nobody can deny they are very efficient at what they do best: hit hard, fast and overwhelmingly where the enemy doesn't expect it then redeploy before they can strike back.
</p><p>This is well-represented in-game by the French having good skill but poor morale scores. This is also why the Czechoslovaks, despite being far less motivated than the French in every respect, have a better Morale rating despite literally having worse morale. Such a broad and encompassing term as Morale isn't restricted to the one stat that shares its name, and is technically the collective sum of all the stats on the left half of the base section since it was broken into those three in the first place.
</p>
</div>
</div>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">French Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/AMX-30" title="AMX-30">AMX-30</a> • <a href="/wiki/Leclerc" title="Leclerc">Leclerc</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/AMX-10P" title="AMX-10P">AMX-10P</a> • <a href="/wiki/VAB" title="VAB">VAB</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/Section_d%27infanterie/Chasseurs" title="Section d&#39;infanterie/Chasseurs">Section d'infanterie/Chasseurs</a> • <a href="/wiki/Milan_Section_Antichar" title="Milan Section Antichar">Milan Section Antichar</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/AMX_Auf1" title="AMX Auf1">AMX Auf1</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/AMX-13_DCA" title="AMX-13 DCA">AMX-13 DCA</a> • <a href="/wiki/AMX_Roland" title="AMX Roland">AMX Roland</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/VAB_Mephisto" title="VAB Mephisto">VAB Mephisto</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/AMX-10_RC" title="AMX-10 RC">AMX-10 RC</a> • <a href="/wiki/AMX-10P#AMX-10P_VOA" title="AMX-10P">AMX-10P VOA</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/Gazelle_Helicopter" title="Gazelle Helicopter">Gazelle HOT</a> • <a href="/wiki/Gazelle_Helicopter" title="Gazelle Helicopter">Gazelle 20mm</a> • <a href="/wiki/Mirage_5" title="Mirage 5">Mirage 5</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="Canada">Canada</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=18" title="Edit section: Canada">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div style="margin-top:1em;margin-bottom:1em"><i>"I know a lot of you are going through separation anxiety... but there's nothing I can do about getting a Tim Hortons in Kabul."</i>
<dl><dd><small>– Col. Al Howard (FYI, they did eventually get a Tim Hortons in a trailer)</small></dd></dl></div>
<p><u>Difficulty</u>: 3/5 (Limited unit variety, technical playstyle.)
</p><p><a href="/wiki/Imperial_Guard" title="Imperial Guard">Cadians!</a> Wait. Not quite. Though, they too have an amazing, cost-effective and plentiful tank option. As for their place in Team Yankee, the Canadians took one look at the infantry spam meta, and they decided that they hated it. Where the US brought their meanest guns and the West Germans brought their biggest machines, the <i>4th CMBG</i> showed up to the fight with a <a href="/wiki/Leopard_1#Canada" title="Leopard 1">tree grinder</a>, intending to reenact that scene from Fargo.
</p><p>While suffering from a limited arsenal, the options Canada brings can be versatile and extraordinary. Between a universal +3 skill roll and an abundance of options for laying down smoke, you can acquire the firing positions you require while denying the enemy their own. Agility is essential to Canadian lists, using evasion rather than armour in a naturally offensive force. In essence, the Canucks seem at their best in vehicles and on the move, shadowing the enemy line until it has been withered beneath a barrage of precise and overwhelming fire.
</p><p>The Canadians apologize for borrowing American and German units, such as aircraft and heavy tank platoons.
</p><p><s>Defining Units</s>: <a href="/wiki/ADATS" title="ADATS">ADATS</a>, <a href="/wiki/Leopard_1#Canada" title="Leopard 1">Leopard C1's</a>, <a href="/wiki/LAV-25" title="LAV-25">Coyote</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>Units tend to be agile, multi-purpose or hard-hitting. rarely, all three.</li>
<li>Ideal for offensive and maneuver-minded players.</li>
<li>Invented the Geneva suggestions.</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Glass cannons whose vehicles can cost a pretty pound of points.</li>
<li>No budget options for defeating generation-3 tanks.</li>
<li>The Americans really don't like you.</li></ul>
<p><br />
</p>
<pre>The Breakdown:
Infantry: Jack-of-all-trades, master of none. 3/5
Transports: It's cheap, it's free! 3/5
Tanks: Solid options for defeating the infantry and generation-3 tanks of the 2025 meta. 4/5
Anti-Tank: Enough TOW platforms to do damage, plus the spillover from AA. 3/5
Recon: Well-rounded, but nothing overpowered. 4/5
Artillery: Some mortars, some howitzers. Nothing special. 3/5
Aircraft: Grounded by lack of parts. -/5
Anti-Air: Your primary AA platform also cracks open heavy tanks... for a price. 4/5
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Canadian Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/Leopard_1#Canadian" title="Leopard 1">Leopard C1</a> • <a href="/wiki/Leopard_2#Canadian" title="Leopard 2">Leopard 2 CAN</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/M113_Armored_Personnel_Carrier" title="M113 Armored Personnel Carrier">M113 APC</a>
</td></tr>
<tr>
<th nowrap="">Infantry
</th>
<td><a href="/wiki/Canadian_Mechanized_Platoon" title="Canadian Mechanized Platoon">Canadian Mechanized Platoon</a> • <a href="/wiki/Canadian_Airborne_Platoon" title="Canadian Airborne Platoon">Canadian Airborne Platoon</a> • <a href="/wiki/Airborne_HMG_Platoon?action=edit&amp;redlink=1" class="new" title="Airborne HMG Platoon (page does not exist)">Airborne HMG Platoon</a> • <a href="/wiki/Airborne_81mm_Mortar_Platoon?action=edit&amp;redlink=1" class="new" title="Airborne 81mm Mortar Platoon (page does not exist)">Airborne 81mm Mortar Platoon</a>
</td></tr>

<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/M109_Howitzer#Canadian_Variant" title="M109 Howitzer">M109 Field Battery</a> • <a href="/wiki/M125_81mm" title="M125 81mm">M125 81mm</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/ADATS" title="ADATS">ADATS</a> • <a href="/wiki/M113_Blowpipe" title="M113 Blowpipe">M113 Blowpipe</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/M150_TOW" title="M150 TOW">M150 TOW</a> •  <a href="/wiki/ILTIS_TOW_Section?action=edit&amp;redlink=1" class="new" title="ILTIS TOW Section (page does not exist)">ILTIS TOW Section</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/Lynx_Reconnaissance_Patrol" title="Lynx Reconnaissance Patrol">Lynx RECCE Patrol</a> • <a href="/wiki/M113_OP" title="M113 OP">M113 OP</a> • <a href="/wiki/LAV-25" title="LAV-25">Coyote (Reconnaissance Vehicle)</a> •  <a href="/wiki/ILTIS_Recce_Jeep?action=edit&amp;redlink=1" class="new" title="ILTIS Recce Jeep (page does not exist)">ILTIS Recce Jeep</a>
</td></tr>
<tr>
<th nowrap="">US Support
</th>
<td><a href="/wiki/M1_Abrams" title="M1 Abrams">M1 Abrams</a> • <a href="/wiki/M60_Patton" title="M60 Patton">M60 Patton</a> • <a href="/wiki/US_Mech_Platoon" title="US Mech Platoon">US Mech Platoon</a> • <a href="/wiki/A-10_Warthog" title="A-10 Warthog">A-10 Warthog</a>
</td></tr>
<tr>
<th nowrap="">WG Support
</th>
<td><a href="/wiki/Leopard_2" title="Leopard 2">Leopard 2</a> • <a href="/wiki/Panzergrenadiers" title="Panzergrenadiers">Marder Panzergrenadiers</a> • <a href="/wiki/BO-105P" title="BO-105P">BO-105P</a> • <a href="/wiki/Tornado" title="Tornado">Tornado</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="The_Netherlands">The Netherlands</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=19" title="Edit section: The Netherlands">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p><i>"Lucas, get out of the lingerie!"</i>
</p><p><u>Difficulty</u>: 2/5 (Versatile units with some drawbacks. Beginner viable.)
</p><p>The Netherlands! A country so friendly and fun to visit that when World War III finally kicked off in August 1985, the Warsaw Pact drove a spear right through West Germany and brought the party to them. High on weed and hookah, the Dutch wade blindly into battle with a combination of dated equipment from the early 60s and the cutting edge of modern weaponry.
</p><p>Clearly influenced by the Wehrmacht of yesteryear, the Royal Netherlands Army boasts one of the toughest mechanized lists around. With the holy trifecta of Leopard 2s, IFVs and Carl Gustavs, Dutch lists have few weaknesses, with numbers and the ability to deal with armour from just about any range and IFV hordes.
</p><p>They are less advanced than their alcoholic West German brothers (infrared), but are considerably cheaper.
</p><p>The Dutch share many similarities with the Americans and the West Germans, playing as a middle ground between the two. Much of their equipment is West German in origin, from the terribly pricy Leopard 2 (with a 1 point discount, no less) to the terrifyingly effective Pantserluchtdoel PRTL, or "Dutch Gepard". Your units have training similar to the Americans rather than the underequipped West Germans.
</p><p>The strength of the Dutch lies in their mechanized forces. While their tanks are mediocre compared to other NATO nations, they are unique in their ability to pump out infantry fighting vehicles while carrying full-sized platoons with some very scary firepower, unlike their French and German counterparts. The West Germans have also granted support units to your Dutch band of (definitely straight) brothers.
</p><p>Defining Units: <a href="/wiki/Leopard_2" title="Leopard 2">Leopard 2</a>, <a href="/wiki/YPR-765" title="YPR-765">YPR-765</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>Able to spam IFVs with infantry to boot.</li>
<li>Ideal for mechanized players or jacks of all trades.</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Long ranged anti-tank capability only from Leopard 2s.</li>
<li>Jack-of-all-trades faction without any overpowered units.</li>
<li>Drug peddlers.</li></ul>
<pre>The Breakdown:
Infantry: decent, but made deadly by virtue of their transports. 4/5
Transports: It's cheap, and also the best NATO IFV. 4/5
Tanks: Not great, but you don't have any other AT options. 3/5
Anti-Tank: Expensive, fragile and mediocre. 2/5
Recon: Does the job, but nothing more. 3/5
Artillery: Below-average, but still passable. 3/5
Aircraft: Our pilots are still in rehab. -/5
Anti-Air: Weaker than the West Germans, but still very strong. 4/5
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Dutch Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/Leopard_1" title="Leopard 1">Leopard 1</a> • <a href="/wiki/Leopard_2" title="Leopard 2">Leopard 2</a> • <a href="/wiki/Leopard_2#Leopard_2A5" title="Leopard 2">Leopard2A5</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/YPR-765#YPR-765_Infantry_Fighting_Vehicle" title="YPR-765">YPR-765 IFV</a> • <a href="/wiki/M113_Armored_Personnel_Carrier" title="M113 Armored Personnel Carrier">M113 Armored Personnel Carrier</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/M113_Tirailleur_Peleton/YPR_765_Pantserinfanterie_Peloton" title="M113 Tirailleur Peleton/YPR 765 Pantserinfanterie Peloton">M113 Tirailleur Peleton/YPR 765 Pantserinfanterie Peloton</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/M106_Heavy_Mortar_Carrier" title="M106 Heavy Mortar Carrier">107mm/120mm Mortier Peloton</a> • <a href="/wiki/M109_Howitzer#Dutch_Variant" title="M109 Howitzer">M109 Veldartillerie Batterij</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/Gepard_Flakpanzer_Batterie" title="Gepard Flakpanzer Batterie">PRTL</a> • <a href="/wiki/Stinger_Peloton" title="Stinger Peloton">Stinger Peloton</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/YPR-765_PRAT" title="YPR-765 PRAT">YPR-765 PRAT</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/M113_C%26V_Ploeg" title="M113 C&amp;V Ploeg">M113 C&amp;V Ploeg</a> • <a href="/wiki/YPR-765#YPR-765_Observation_Post" title="YPR-765">YPR-765 OP</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/AH-64?action=edit&amp;redlink=1" class="new" title="AH-64 (page does not exist)">AH-64</a>
</td></tr>
<tr>
<th nowrap="">WG Support
</th>
<td><a href="/wiki/Roland_Flak_Batterie" title="Roland Flak Batterie">Roland Flak Batterie</a> • <a href="/wiki/Raketenwerfer_Batterie" title="Raketenwerfer Batterie">Raketenwerfer Batterie</a> • <a href="/wiki/BO-105P" title="BO-105P">BO-105P</a> • <a href="/wiki/Tornado" title="Tornado">Tornado</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="Belgium">Belgium</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=20" title="Edit section: Belgium">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>Once a poster child for European Neutrality and non-alignment along with the Swiss, Belgium paid the price for this in two World Wars. In no mood for a third occupation, Belgium became a founding member of NATO which itself became headquartered in the Belgian capital city of Brussels. In the event of a Third World War, Belgium would not be found wanting as it did in the previous two.
</p><p>The Belgians play much like their Dutch neighbors.
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>'Waffles.</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Bureaucracy.</li></ul>
<pre>The Breakdown:
Infantry:
Transports:
Tanks:
Anti-Tank:
Recon:
Artillery:
Aircraft:
Anti-Air:
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Belgian Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/Leopard_1" title="Leopard 1">Leopard 1</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/M113_Armored_Personnel_Carrier" title="M113 Armored Personnel Carrier">M113 Armored Personnel Carrier</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td>TBA
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td>TBA
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td>TBA
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td>TBA
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td>TBA
</td></tr>
<tr>
<th nowrap="">NATO Support
</th>
<td>TBA
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="Denmark">Denmark</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=21" title="Edit section: Denmark">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>Denmark had bad luck in the Second World War, invaded by Nazi Germany and conquered within two hours. After the war Denmark took the lessons of the war to heart, being part of the foundation of NATO and fully integrated itself into working with West German forces to the point where the West Germans had Luftwaffe units stationed in Denmark. In the event of war NATO considered it vital to defend Denmark as a strategic part of their overall defense with the primary objective of blocking the Danish Straits to prevent the Soviet Baltic Fleet from breaking out to the North Sea. Thus the Danish forces, though small, would find themselves right at the forefront of the fight from the outset.
</p><p>The Danes play like neutered Canadians with worse skill ratings. They get access to both Leopard 1 and Centurion tank formations.
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>LEGO</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Nobody understands them.</li></ul>
<pre>The Breakdown:
Infantry:
Transports:
Tanks:
Anti-Tank:
Recon:
Artillery:
Aircraft:
Anti-Air:
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Danish Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/Centurion" title="Centurion">Centurion</a> • <a href="/wiki/Leopard_1" title="Leopard 1">Leopard 1</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/M113_Armored_Personnel_Carrier" title="M113 Armored Personnel Carrier">M113 Armored Personnel Carrier</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/Armored_Infantry_Platoon" title="Armored Infantry Platoon">Armored Infantry Platoon</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/M109_Howitzer" title="M109 Howitzer">M109 Howitzer</a> • <a href="/wiki/M106_Heavy_Mortar_Carrier" title="M106 Heavy Mortar Carrier">M106 Heavy Mortar Carrier</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/Redeye_SAM_Platoon" title="Redeye SAM Platoon">Redeye SAM Platoon</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td>TBA
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/Feltvogn_Recon_Troop?action=edit&amp;redlink=1" class="new" title="Feltvogn Recon Troop (page does not exist)">Feltvogn Recon Troop</a> • <a href="/wiki/M113_OP" title="M113 OP">M113 OP</a>
</td></tr>
<tr>
<th nowrap="">NATO Support
</th>
<td><a href="/wiki/AV-8_Harrier" title="AV-8 Harrier">AV-8 Harrier</a> • <a href="/wiki/Tornado" title="Tornado">Tornado</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="Norway">Norway</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=22" title="Edit section: Norway">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>Norway tried neutrality in WWII and ended up under German occupation for the duration of the war, and now sharing a border with the principal Soviet naval base of Murmansk that contained around two-thirds of all the Soviet Navy’s nuclear forces made the threat of a Soviet thrust into Norway to protect their vital nuclear submarine bases a very real possibility. Norway therefore became one of the signatory parties to NATO’s formation in 1949 and an active member from then on. Northern Norway became part of the first Western defense line in the event of war with the Soviet Union and the whole of Norwegian society was prepared for a war of 'total defense' in the case of a Soviet invasion.
</p><p>Norway in Team Yankee is principally an infantry force but their infantry is powerful and they have access to some of the best US equipment in the form of allied formations.
</p>
<dl><dt>Strengths</dt></dl>
<p>Black Metal
</p>
<dl><dt>Weaknesses</dt></dl>
<p>Terrible caravan drivers
</p>
<pre>The Breakdown:
Infantry:
Transports:
Tanks:
Anti-Tank:
Recon:
Artillery:
Aircraft:
Anti-Air:
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Norwegian Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/Leopard_1" title="Leopard 1">Leopard 1</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/M113_Armored_Personnel_Carrier" title="M113 Armored Personnel Carrier">M113 Armored Personnel Carrier</a> • <a href="/wiki/NM135?action=edit&amp;redlink=1" class="new" title="NM135 (page does not exist)">NM135</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/Storm_Platoon?action=edit&amp;redlink=1" class="new" title="Storm Platoon (page does not exist)">Storm Platoon</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/M109_Howitzer" title="M109 Howitzer">M109 Howitzer</a> • <a href="/wiki/M106_Heavy_Mortar_Carrier" title="M106 Heavy Mortar Carrier">M106 Heavy Mortar Carrier</a> • <a href="/wiki/M125_81mm" title="M125 81mm">M125 81mm</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/NM195?action=edit&amp;redlink=1" class="new" title="NM195 (page does not exist)">NM195</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/Feltvogn_Anti-Tank_Section?action=edit&amp;redlink=1" class="new" title="Feltvogn Anti-Tank Section (page does not exist)">Feltvogn Anti-Tank Section</a> • <a href="/wiki/NM142?action=edit&amp;redlink=1" class="new" title="NM142 (page does not exist)">NM142</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/Feltvogn_Recon_Troop?action=edit&amp;redlink=1" class="new" title="Feltvogn Recon Troop (page does not exist)">Feltvogn Recon Troop</a> • <a href="/wiki/M113_OP" title="M113 OP">M113 OP</a>
</td></tr>
<tr>
<th nowrap="">NATO Support
</th>
<td><a href="/wiki/AV-8_Harrier" title="AV-8 Harrier">AV-8 Harrier</a> • <a href="/wiki/AJ_37_Viggen" title="AJ 37 Viggen">AJ 37 Viggen</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="ANZAC">ANZAC</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=23" title="Edit section: ANZAC">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p><i>"Oi! Mate! Get off the fekkin' gun and stab the bloody cunt!"</i>
</p><p><u>Difficulty</u>: 4/5 (Beginner unfriendly. Vet recommended.)
</p><p>Legendary for their daring, elan and professionalism, the armed forces of Australia have a long record of making somebody <i>very</i> sorry that they picked a fight with the Empire. Or with Australia. Or that there was a fight going on, and the Australians heard about it and showed up. Where Canada runs in circles around the enemy and France runs away from the enemy, the Aussies and Kiwis run <i>at</i> the enemy. By all accounts they really shouldn't be present, they aren't even officially part of NATO (due to that whole "North Atlantic" thing), yet here they are in 1980's Germany. Down-under magic? Down-under magic. The Queen calling for aid? Or maybe has something to do with the complicated system of alliances in the pacific that were thrown around very early on in the cold war. The Aussies and Kiwis both had actually signed a treaty referred to as the ANZUS with the US in the 50's guaranteeing defensive cooperation if any hostilities were launched against them or a number of allied states, hence their military presence in Vietnam and now, in Germany. Though historically ANZUS was dead in the water at the time due to New Zealand's Nuclear-Free stance putting it at odds with the United States, leading to the two countries parting ways as 'friends, not allies'. Technically New Zealand shouldn't even be here and it should just be the Australians. But Battlefront are a New Zealand company and so Kiwi favoritism keeps them around following in the Australians footsteps. Clearly in this alternate 1985 David Lange was never elected as New Zealand's Prime Minister.
</p><p>Your PACT players are going to be wondering: "Wait, aren't <i>we</i> supposed to be ones who're invading?". This will occur just as several packs of foul-mouthed Bogans roll around the corner, firing on the move and charging into melee from their tanks to show the Gopniks how it’s really done. Keep in mind, this is during an era whereby that shit should <b>not</b> fly. But looking at their stats, that's specifically what they're here to do. Skilled, courageous, all while packing lots of tools designed for staring the dirty communist in the eyes as you kill him. Your infantry may not be amazing, but your scorpions and leopards can literally roll over the communists with assault 3+. The Australians may not actually be in NATO at all, but having decided to show up anyway, they're polite, they're efficient, and they have a plan to kill everyone they meet.
</p><p>The ANZACS have British support units such as the Tracked Rapier and Harrier, thanks to their plea deal with the crown.
</p><p>Defining Units: <a href="/wiki/CVRT#Kiwi_Variant" title="CVRT">Scorpion</a>, <a href="/wiki/AT_Land_Rover" title="AT Land Rover">AT Land Rover</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>'Tank' units are nearly unmatched in close quarters, and set to win damn near <i>every</i> melee they enter.</li>
<li>Ideal for you melee junkies out there.</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Suffers from yet another serious lack of organic support.</li>
<li>Units are few as is, but a lack of variety can seriously limit flexibility.</li>
<li>Can't handle cold.</li></ul>
<pre>The Breakdown:
Infantry: Average NATO infantry, but essential in any list. 3/5
Transports: It's free I guess.... 3/5
Tanks: Your tanks can shred light armor on the move while running infantry over. 4/5
Anti-Tank: Good against light armor, terrible against high-end tanks. 3/5
Recon: Kiwis go <i>hard</i>. 2/5
Artillery: Mortars only, but the Brits can help you out! 2/5
Aircraft: <s>Every one knows that Kiwi's are flightless birds</s> The RNZAF is here! 2/5
Anti-Air: It's bad. It's REALLY bad. 1/5
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">ANZAC Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/Leopard_1#ANZAC" title="Leopard 1">Leopard AS1</a> • <a href="/wiki/M1_Abrams" title="M1 Abrams">M1 Abrams</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/M113_Armored_Personnel_Carrier" title="M113 Armored Personnel Carrier">M113 (T50)</a>
</td></tr>
<tr>
<th nowrap="">Infantry
</th>
<td><a href="/wiki/ANZAC_Mechanized_Platoon" title="ANZAC Mechanized Platoon">ANZAC Mechanized Platoon</a> • <a href="/wiki/Milan_AT_Section" title="Milan AT Section">Milan AT Section</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/M106_Heavy_Mortar_Carrier" title="M106 Heavy Mortar Carrier">M125 Mortar Platoon</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/M113_Redeye_SAM_section" title="M113 Redeye SAM section">M113 Redeye SAM section</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/AT_Land_Rover" title="AT Land Rover">AT Land Rover</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/CVRT#Scorpion" title="CVRT">Scorpion</a> • <a href="/wiki/M113_Cavalry_Troop" title="M113 Cavalry Troop">M113 MRV</a> • <a href="/wiki/M113_Cavalry_Troop" title="M113 Cavalry Troop">M113 LRV</a> • <a href="/wiki/LAV-25" title="LAV-25">LAV-25</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/A4_Skyhawk" title="A4 Skyhawk">A4 Skyhawk</a>
</td></tr>
<tr>
<th nowrap="">British Support
</th>
<td><a href="/wiki/FV430_Series#FV_433_Self_Propelled_Artillery" title="FV430 Series">Abbot Field Battery</a> • <a href="/wiki/M109_Howitzer#British_Variant" title="M109 Howitzer">M109 Field Battery</a> • <a href="/wiki/FV430_Series" title="FV430 Series">FV432 FOO</a> • <a href="/wiki/AV-8_Harrier" title="AV-8 Harrier">Harrier Jump Jet</a> • <a href="/wiki/Lynx_Helicopter#Lynx_AH-1_TOW" title="Lynx Helicopter">Lynx HELARM</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading3"><h3 id="Warsaw_Pact">Warsaw Pact</h3><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=24" title="Edit section: Warsaw Pact">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div style="margin-top:1em;margin-bottom:1em"><i>"The Communists disdain to conceal their views and aims. They openly declare that their ends can be attained only by the forcible overthrow of all existing social conditions. Let the ruling classes tremble at a Communistic revolution. The proletarians have nothing to lose but their chains. They have a world to win.</i>
<p><b><i>Working Men of All Countries, Unite!</i></b>
'<i>"</i>
</p>
<dl><dd><small>– Karl Marx, The Communist Manifesto</small></dd></dl></div>
<p>Unlike NATO, standardization was enforced in the Warsaw Pact at most levels of the military. From the caliber of firearms to the strategies used by commanders, each country only made the slightest of adjustments. Expect little variation in equipment compared to NATO. Tactics do vary of course, but always rely on numerical superiority to win the day. Most Pact nations have inferior equipment to the Soviet Union which was historically accurate: Soviet Union entries can generally be used for your own faction. The playstyles vary more on your army list than individual factions: an infantry list is going to play very similarly, whether there are Russians or Poles in their ranks. For budget players without care for bling and army decals, consider leaving all units in the standard Russian green and they can be Russians, Czechs or Russians disguised as <s>Ukrainians</s> Poles.
</p>
<div class="mw-heading mw-heading4"><h4 id="Soviet_Union">Soviet Union</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=25" title="Edit section: Soviet Union">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>-<i>What should a Soviet soldier do if he finds himself in an immediate vicinity of a nuclear explosion?</i>
</p><p>-<i>Stretch out his arms and hold his assault rifle in such a way that no molten metal get on state-issued boots.</i>
</p><p>- Soviet army joke
</p><p><u>Difficulty</u>: 3.5/5 (Tough to learn, easier to master.)
</p><p>Massive, heavily armed, and with a record of Nazi-stomping in World War II that makes the whole Western front pale in comparison, the Soviet Armed Forces were a force to be reckoned with through the entire Cold War. Far outnumbering their adversaries and their own voluntold allies, the Soviet military possessed enough tanks, artillery, aircraft, automatic rifles and machine guns to make all of NATO's vaunted quality-over-quantity ideas count for absolutely nothing in a real war. Rules for the Soviet Hordes can be found in the Team Yankee Rulebook, “Red Thunder”, and, most recently, the "Soviet" book.
</p><p>In addition to the mechanized forces of the Red Army, Red Thunder gives you the rules for running an Air Assault Battalion from the VDV. They have a totally different list from other PACT factions and were the best infantry that the PACT can buy.
</p><p>With the release of the new book, the Soviets gained access to the T-80 Shock Company formation. This elite formation is closer to a NATO force than other WarPac formations. Platoons of 2-3 tanks hit on 4+ with 3+ skill break the traditional horde structure and come with a hefty points cost to boot. They can also take a platoon of 2-3 recon BMP-3s with the same stats AND a company of BMP-3 mechanised infantry (with the option to downgrade to shock BMP-2s). Expensive as hell with the usual low ROF of Soviet armour, expect to be heavily outnumbered.
</p><p>As a Soviet player, you are the proud owner of the most advanced army among REDFOR, rivalled only by the US (in games without allies, that is). Point for point, few armies can equal your ability to bring reliable firepower. Near universal 3+ Remount and Morale ensures that your glorious Communists will (probably) never falter against the Capitalist pigs. While their 3+ to hit ensures that they suffer losses at a far greater rate, the USSR has viable units in almost every archetype. Whether it's a tank battalion, an air assault list, artillery spam or half of a motor rifle brigade, the USSR is cost-effective enough to make most archetypes work. An ideal army for the experienced or the powergamer, although you must be prepared to counter your low skill ratings.
</p><p>Defining Units: <a href="/wiki/Motor_Rifle_Company" title="Motor Rifle Company">Motor Rifle Company</a>, <a href="/wiki/2S1_Carnation" title="2S1 Carnation">2S1 Gvozdika</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>Cheap, cost-effective units for all roles but tanks. Excellent morale.</li>
<li>Ideal for veterans to Flames Of War, horde and powergamers.</li>
<li>Communism.</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Reliant on effective combined arms tactics.</li>
<li>Units will lose 1-on-1 confrontations against most NATO counterparts.</li>
<li>Communism.</li></ul>
<pre>The Breakdown:
Infantry: Cheap and insanely cost-efficient. 5/5
Transports: Meta defined by BMP parking lots. 5/5
Tanks: Cheap but mediocre. 3/5
Anti-Tank: Cheap, but tiny unit sizes. 2/5
Recon: Acceptable, but not amazing. 3/5
Artillery: Unreliable, weakest PACT artillery. 2/5
Aircraft: Good; only competitor to the US. 4/5
Anti-Air: Cheap but deadly. 5/5
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Soviet Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/T55AM2" title="T55AM2">T55AM2</a> • <a href="/wiki/T-62M" title="T-62M">T-62M</a> • <a href="/wiki/T-64" title="T-64">T-64</a> • <a href="/wiki/T-72" title="T-72">T-72</a> • <a href="/wiki/T-80" title="T-80">T-80</a> • <a href="/wiki/T-72B" title="T-72B">T-72B</a> • <a href="/wiki/T-64BV" title="T-64BV">T-64BV</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/BTR-60" title="BTR-60">BTR-60</a> • <a href="/wiki/BMP" title="BMP">BMP-1</a> • <a href="/wiki/BMP" title="BMP">BMP-2</a> • <a href="/wiki/BMP-3" title="BMP-3">BMP-3</a> • <a href="/wiki/BMD" title="BMD">BMD-1</a> • <a href="/wiki/BMD#BMD-2" title="BMD">BMD-2</a> • <a href="/wiki/BTR-D" title="BTR-D">BTR-D</a> • <a href="/wiki/MI-8_Hip" title="MI-8 Hip">MI-8 Hip</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/Motor_Rifle_Company" title="Motor Rifle Company">Motor Rifle Company</a> • <a href="/wiki/Hind_Assault_Landing_Company" title="Hind Assault Landing Company">Hind Assault Landing Company</a> • <a href="/wiki/Afghansty_Air_Assault_Company" title="Afghansty Air Assault Company">Afghansty  Air Assault Company</a> • <a href="/wiki/BMP_Shock_Motor_Rifle_Company" class="mw-redirect" title="BMP Shock Motor Rifle Company">BMP Shock Motor Rifle Company</a> • <a href="/wiki/BMD_Air_Assault_Company" title="BMD Air Assault Company">BMD Air Assault Company</a> • <a href="/wiki/Afghansty_BMD_Air_Assault_Platoon" title="Afghansty BMD Air Assault Platoon">Afghansty BMD Air Assault Platoon</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/2S1_Carnation" title="2S1 Carnation">2S1 Carnation</a> • <a href="/wiki/2S3_Acacia" title="2S3 Acacia">2S3 Acacia</a> • <a href="/wiki/BM-21_Hail" title="BM-21 Hail">BM-21 Hail</a> • <a href="/wiki/TOS-1_Buratino" title="TOS-1 Buratino">TOS-1 Buratino</a> • <a href="/wiki/BM-27_Uragan" title="BM-27 Uragan">BM-27 Uragan</a> • <a href="/wiki/2S9_Nona" title="2S9 Nona">2S9 Nona</a> • <a href="/wiki/BM-37_82mm_mortar_platoon" title="BM-37 82mm mortar platoon">BM-37 82mm mortar platoon</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/ZSU_23-4_Shilka" title="ZSU 23-4 Shilka">ZSU 23-4 Shilka</a> • <a href="/wiki/SA-13_Gopher" title="SA-13 Gopher">SA-13 Gopher</a> • <a href="/wiki/SA-9_Gaskin" class="mw-redirect" title="SA-9 Gaskin">SA-9 Gaskin</a> • <a href="/wiki/SA-8_Gecko" title="SA-8 Gecko">SA-8 Gecko</a> • <a href="/wiki/SA-19_Grison" title="SA-19 Grison">2S6 Tunguska</a> • <a href="/wiki/BTR-D#BTR-ZD" title="BTR-D">BTR-ZD</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/Spandrel" title="Spandrel">Spandrel</a> • <a href="/wiki/Storm" title="Storm">Storm</a> • <a href="/wiki/BTR-D#BTR-RD" title="BTR-D">BTR-RD</a> • <a href="/wiki/ASU-85" title="ASU-85">ASU-85</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/BMP#BMP-1_OP_(Observation_Post)" title="BMP">BMP-1 OP</a> • <a href="/wiki/BMD#BMD-1_OP_(Observation_Post)" title="BMD">BMD-1 OP</a> • <a href="/wiki/BRDM-2" title="BRDM-2">BRDM-2</a> • <a href="/wiki/BMP#BMP-1_Recon" title="BMP">BMP-1 Recon</a> • <a href="/wiki/BMP#BMP-2_Recon" title="BMP">BMP-2 Recon</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/SU-22_Fitter" title="SU-22 Fitter">SU-22 Fitter</a> • <a href="/wiki/SU-25_Frogfoot" title="SU-25 Frogfoot">SU-25 Frogfoot</a> • <a href="/wiki/MI-24_Hind" title="MI-24 Hind">MI-24 Hind</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="East_Germany">East Germany</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=26" title="Edit section: East Germany">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p><i>"For the protection of the workers' and the peasants' power" </i>
-Motto of the Volksarmee
</p><p><u>Difficulty</u>: 4.5/5 (Weak units and weak list. Vets only.)
</p><p>After getting stomped into oblivion by the Soviets during World War II, half of Germany has been rebuilt in the Soviet image. Founded in the mid-1950s, the armed forces of the German Democratic Republic, known as the Nationale Volksarmee (National People's Army), <a href="/wiki/Mordian_Iron_Guard" title="Mordian Iron Guard">combine Prussian heritage, iconic German military discipline, and Soviet mass-unit doctrine</a> to forge one of the most formidable enemies NATO will ever face on the battlefield. Even though they must make do with downgraded Soviet export equipment, they fight with a tenacity that rivals that of their forefathers. NATO military officers have consistently rated the NVA as the best force in the Warsaw Pact based on its discipline, thoroughness of training, and the leadership ability of its commissioned officers. Following Soviet tradition, the Volksarmee lends the names of various Communist heroes to regimental-sized units and above, such as Panzerregiment 23 "Julian Marchlewski", one of the three armored regiments of the 9th Panzer Division. Rules for the East Germans are found in “Volksarmee.”
</p><p>As the Volksarmee you stare enviously at USSR-Sempai and employ 30-year-old tanks with such reckless ambition that an Imperial Guardsman would question your value for human life. Your soldiers are as zealous as your Soviet counterparts and have more skill than <s>the illiterate peasants in the Red Army</s> your honored Soviet allies. The downside you might ask? You are using whatever even the <i>Soviet Union</i> thinks is too unsafe for their soldiers, using all the hand me downs with gusto. The majority of the Volksarmee gets the T-55AM2, which is great at exploding, and the first-rate armored regiments get the T-72M, which is also great at exploding but shoots better. You may be (mostly) bringing tanks from the mid-50s, but you can bring 30 of them for a little less than the cost of 2 West German tanks. Hell, even if you fight against the Soviets, you will outnumber them more than 2 to 1 (Even with both of you bringing T-72s). If you want the discount of non-Soviet PACT nations without the lopsided characteristics of the Poles or the Czechs, the National People's Army stands ready to invade capitalist-occupied West Germany at your order.
</p><p>Defining Units: <a href="/wiki/Motor_Rifle_Company#Mot-Schützen_Kompanie" title="Motor Rifle Company">Motorschützen</a>, <a href="/wiki/T55AM2" title="T55AM2">T55AM2</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>Second cheapest units in the game, with rather decent stat lines.</li>
<li>Ideal for horde players with too much money, or tactical geniuses.</li>
<li>Sweet spot between the elite Poles and the conscript Czechs.</li>
<li>Communist Prussians</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Units outmatched by most NATO equivalents; West Germany has much, <i>much</i> better Panzers.</li>
<li>Players must rely on superior planning to win games due to the VAST technological gap.</li>
<li>Nazbol fetishists</li></ul>
<pre>The Breakdown
Infantry: Soviet numbers with low-end NATO stats. 3/5
Transports: Like the Soviets, but slightly worse. 3/5
Tanks: Useless in head-on engagements, good as flanking units. 3/5
Anti-Tank: Tanks do it better than these pieces of crap. 1/5
Recon: On par with Soviet Recce (AKA pretty bad). 3/5
Artillery: NATO skill and Soviet arty? Pretty good! 4/5
Aircraft: Decent air force. 3/5
Anti-Air: Cheap but lacks high-end anti-air missiles. 3/5
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">East German Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/T-55" class="mw-redirect" title="T-55">T-55</a> • <a href="/wiki/T55AM2" title="T55AM2">T55AM2</a> • <a href="/wiki/T-72M" title="T-72M">T-72M</a> • <a href="/wiki/T-72B" title="T-72B">T-72B</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/BTR-60" title="BTR-60">BTR-60</a> • <a href="/wiki/BMP" title="BMP">BMP-1</a> • <a href="/wiki/BMP" title="BMP">BMP-2</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/Motor_Rifle_Company#Mot-Schützen_Kompanie" title="Motor Rifle Company">Mot-Schützen Kompanie</a> • <a href="/wiki/Hind_Assault_Landing_Company" title="Hind Assault Landing Company">Hind Assault Landing Company</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/2S1_Carnation" title="2S1 Carnation">2S1 Carnation</a> • <a href="/wiki/BM-21_Hail" title="BM-21 Hail">BM-21 Hail</a> • <a href="/wiki/RM-70" title="RM-70">RM-70</a> • <a href="/wiki/2S3_Acacia" title="2S3 Acacia">2S3 Acacia</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/ZSU_23-4_Shilka" title="ZSU 23-4 Shilka">ZSU 23-4 Shilka</a> • <a href="/wiki/SA-13_Gopher" title="SA-13 Gopher">SA-13 Gopher</a> • <a href="/wiki/SA9_Gaskin" title="SA9 Gaskin">SA9 Gaskin</a> • <a href="/wiki/SA-8_Gecko" title="SA-8 Gecko">SA-8 Gecko</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/Spandrel" title="Spandrel">Spandrel</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/BMP#BMP-1_OP_(Observation_Post)" title="BMP">BMP-1 OP</a> • <a href="/wiki/BRDM-2" title="BRDM-2">BRDM-2</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/MI-24_Hind" title="MI-24 Hind">MI-24 Hind</a> • <a href="/wiki/SU-22_Fitter" title="SU-22 Fitter">SU-22 Fitter</a>
</td></tr>
<tr>
<th nowrap="">Soviet Support
</th>
<td><a href="/wiki/SU-25_Frogfoot" title="SU-25 Frogfoot">SU-25 Frogfoot</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="Poland">Poland</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=27" title="Edit section: Poland">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p><i>"When the Red Army makes a mess, why do we always have to clean it up?"</i>
</p><p><u>Difficulty</u>: 4.25/5 (Mix of decent units but nothing to write home about, with a cost that suggests more. Vets only.)
</p><p>Coming from a background of militarism, Poland has had a fairly shitty history in the 20th century. They've been stuck in wars since the Great War (despite not being a nation), and Poland has become a plaything for the powers of Europe. Poland was the first country the Nazis occupied (as opposed to annexing), and thanks to the Soviets "liberating" them 40 years ago, by 1985 the original Polish government has been waiting to return home for nearly half a century. Yay. There's some division on that, however, as the Polish People's Army was first organized in 1943 and fought well on the Eastern Front against the Germans before establishing themselves as Poland's official armed forces for the next 40-plus years. Florian Siwicki, the Minister of Defence under the Polish People's Republic in 1985, first joined up in 1942 and has thus shot at (West) Germans before.
</p><p>The Polish People's Republic has one of the largest and strongest armies in Eastern Europe short of the Soviets (complete with their own 6th Airborne Division and a specialized amphibious landing division), and possesses its own arms industry, manufacturing more cheap tanks and guns than anybody except the USSR. Their foreign customers include the East Germans (a lot of those commie Panzers are, ironically, from a Polish factory) and those fun guys in North Korea. They've kept the old Polish national anthem, and, bizarrely for a Soviet bloc state, the Polish People's Army provided chaplains to its troops throughout its existence. The Polish People's Army is large, well-armed, and well-trained; going into World War III, they can dish out and take plenty as the Warsaw Pact and NATO have a frank exchange of ideas over the fate of Europe and the world.
</p><p>In Team Yankee, the Poles are troops with 4+ skill, 3+ courage and 3+ rally, giving them the determination of Soviets with the skill of the NVA. Second only to the Afgantsy VDV veterans, the Poles are some of the best-trained forces of the Warsaw Pact. Despite costing almost as much as the Soviets, they have even less equipment than the East Germans with the same downgrades by PACT forces, except for a handful of special units to even the balance. Boasting the best trained motorized infantry of the PACT armies, Polish battlegroups rely on the superiority of their infantry to win the day, while vehicles serve in support roles.
</p><p>Defining Units: <a href="/wiki/Motor_Rifle_Company" title="Motor Rifle Company">Zmotory Kompania</a>, <a href="/wiki/T-72B" title="T-72B">T-72B</a>
</p><p><br />
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>Reliable units unlikely to get pinned or bailed.</li>
<li>Best PACT infantry at firefighting and attacking.</li>
<li>Ideal for players who want a horde of morale-resistant units.</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Poor anti-tank capability.</li>
<li>2nd tier equipment with near-Soviet costs.</li>
<li>Will carjack your vehicle wrecks.</li></ul>
<pre>Infantry: The best PACT infantry in firefights, at a cost... 3/5
Transports: Like the Soviets, but slightly worse. Few BMP-2s. 3/5
Tanks: Good at flanking, bad at tanking/killing tanks. 3/5
Anti-Tank: Your tanks do the job better than these things. 1/5
Recon: Cheap but bad. 3/5
Artillery: It kills, it's reliable! 4/5
Aircraft: Passable. 3/5
Anti-Air: Pretty solid, actually. 4/5
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Polish Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/T-55" class="mw-redirect" title="T-55">T-55</a> • <a href="/wiki/T55AM2" title="T55AM2">T55AM2</a> • <a href="/wiki/T-72M" title="T-72M">T-72M</a> • <a href="/wiki/T-72B" title="T-72B">T-72B</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/OT-64" title="OT-64">SKOT-2A</a> • <a href="/wiki/BMP" title="BMP">BMP-1</a> • <a href="/wiki/BMP" title="BMP">BMP-2</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/Motor_Rifle_Company#Zmotory_Kompania" title="Motor Rifle Company">Zmotory Kompania</a> • <a href="/wiki/Hind_Assault_Landing_Company" title="Hind Assault Landing Company">Hind Assault Landing Company</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/Dana_SpGH" title="Dana SpGH">Dana SpGH</a> • <a href="/wiki/BM-21_Hail" title="BM-21 Hail">BM-21 Hail</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/ZSU_23-4_Shilka" title="ZSU 23-4 Shilka">ZSU 23-4 Shilka</a> • <a href="/wiki/SA-13_Gopher" title="SA-13 Gopher">SA-13 Gopher</a> • <a href="/wiki/SA-8_Gecko" title="SA-8 Gecko">SA-8 Gecko</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/Spandrel" title="Spandrel">Spandrel</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/BMP#BMP-1_OP_(Observation_Post)" title="BMP">BMP-1 OP</a> • <a href="/wiki/BRDM-2" title="BRDM-2">BRDM-2</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/MI-24_Hind" title="MI-24 Hind">MI-24 Hind</a> • <a href="/wiki/SU-22_Fitter" title="SU-22 Fitter">SU-22 Fitter</a>
</td></tr>
<tr>
<th nowrap="">Soviet Support
</th>
<td><a href="/wiki/SU-25_Frogfoot" title="SU-25 Frogfoot">SU-25 Frogfoot</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="Czechoslovakia">Czechoslovakia</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=28" title="Edit section: Czechoslovakia">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p><i>"To be honest, I'd rather fight for NATO. <small>please don't kill us</small>"</i>
</p><p><u>Difficulty</u>: 5/5 (For hardened vets only.)
</p><p>Ah, yes, Czechoslovakia, the Reluctant Conscript of the Warsaw Pact. Lied to and annexed by the Nazis, then brutally occupied for years, then "liberated" and forced to join the Soviet Union in the Warsaw Pact. What fun! A year ago, someone wrote (rather accurately) that the NVA were the enthusiastic conscripts taking the equipment that the Soviets were afraid of using. Now, imagine these same conscripts, but terrified of death and shivering in their boots. As of October 20, the German goblin hordes have been dethroned by the Czechs! Second-line, underequipped, cowering Slavs being shoved into battle by the Soviets and marching in hordes that would make the Chinese blush (seriously, you'll outnumber the damn East Germans in most scenarios.)
</p><p>The Czechs take the hordes concept to the next level, with their armies outnumbering the other PACT armies. As the least willing participants of the conflict, virtually all their stats are 5+ apart from 4+ skill and 4+ morale. They might have the least trustworthy men in the game, but their discounts allow you to bring enough 125mm cannons and RPGs that a pinned/bailed unit won't save your opponent from the wall of firepower you can produce. The Czechs favour two playstyles: an aggressive list with enough T-72Ms to ignore losses or a defensive list that literally buries your side of the table with men.
</p><p>Defining Units: <a href="/wiki/T-72M" title="T-72M">T-72M</a>, <a href="/wiki/Dana_SpGH" title="Dana SpGH">Dana SpGH</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>Units are 20-33% cheaper than Soviet counterparts.</li>
<li>4+ skill for aggressive tank pushes and artillery spammers.</li>
<li>Ideal for horde players and rich blokes.</li></ul>
<p><br />
</p>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Least reliable units in the game, vulnerable to pinning and morale shock. They <i>really</i> don't want to be there.</li>
<li>Units without support are almost guaranteed to lose any engagements.</li>
<li>Constantly hungover.</li></ul>
<pre>Infantry: You get a horde...but they won't listen to your orders. 2/5
Transports: Like the Poles, with untrained crews. 2/5
Tanks: THE cheapest tank hordes in the game. Good for alpha strikes. 4/5
Anti-Tank: No missiles that can reliably beat heavy tanks, but your T-72s fill the gap. 1/5
Recon: Cheap but bad. 3/5
Artillery: Cheaper, but just as deadly! 4/5
Aircraft: Passable. 3/5
Anti-Air: Cheaper and scarier. 4/5
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Czech Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/T-55" class="mw-redirect" title="T-55">T-55</a> • <a href="/wiki/T55AM2" title="T55AM2">T55AM2</a> • <a href="/wiki/T-72M" title="T-72M">T-72M</a> • <a href="/wiki/T-72B" title="T-72B">T-72B</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/OT-64" title="OT-64">OT-64</a> • <a href="/wiki/BMP" title="BMP">BMP-1</a> • <a href="/wiki/BMP" title="BMP">BMP-2</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/Motor_Rifle_Company#Motorizovaná_Pěchota" title="Motor Rifle Company">Motostrelci</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/2S1_Carnation" title="2S1 Carnation">2S1 Carnation</a> • <a href="/wiki/Dana_SpGH" title="Dana SpGH">Dana SpGH</a> • <a href="/wiki/RM-70" title="RM-70">RM-70</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/ZSU_23-4_Shilka" title="ZSU 23-4 Shilka">ZSU 23-4 Shilka</a> • <a href="/wiki/SA-8_Gecko" title="SA-8 Gecko">SA-8 Gecko</a> • <a href="/wiki/SA9_Gaskin" title="SA9 Gaskin">SA9 Gaskin</a> • <a href="/wiki/SA-13_Gopher" title="SA-13 Gopher">SA-13 Gopher</a> • <a href="/wiki/M53/59_Praga" title="M53/59 Praga">M53/59 Praga</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/Spandrel" title="Spandrel">Spandrel</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/BMP#BMP-1_OP_(Observation_Post)" title="BMP">BMP-1 OP</a> • <a href="/wiki/BRDM-2" title="BRDM-2">BRDM-2</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/MI-24_Hind" title="MI-24 Hind">MI-24 Hind</a> • <a href="/wiki/SU-25_Frogfoot" title="SU-25 Frogfoot">SU-25 Frogfoot</a> • <a href="/wiki/SU-22_Fitter" title="SU-22 Fitter">SU-22 Fitter</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="Cuba">Cuba</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=29" title="Edit section: Cuba">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>-<i> Hasta la victoria Siempre; always until victory&#160;!</i>
</p><p>- Ernesto "CHE" Guevara
</p><p>Cuba is a rather interesting subject when it comes to the Cold War. In 1959, Castro and his forces overthrew the Batista government and established a Communist government right in America's backyard. 2 years later, the US tried and failed to topple the government through the Bay of Pigs Invasion. Then we get the missile crisis where Russia began stationing Nukes on Cuban Soil. And lets not forget the countless assassination attempts on Castro's life. For most countries, this is where the story would end, as a footnote in history. Not Cuba. Throughout the Cold War (and even today) Cuba was something of an abnormality For starters Cuba had a tendency to get involved in foreign conflicts, offering medical and military aid. In 1973 they joined the Yom Kippur War against Israel, and so far as they're concerned (both in 1985 and 2022) that war never actually ended. Cuban forces were very prominent in Africa, and even fought directly against the South African Defense Forces in Angola. This is turn meant that compared to their Communist Allies, Cuba had a substantial amount of military experience. Despite this and their close ties to the Soviet Bloc, Cuba never officially joined the Warsaw Pact, probably because they didn't want to so visibly poke the superpower next door. Despite this, Cuba was something of a well-regarded ally for the Soviets.
</p><p>What Cuba had (and still has) going for them was that while the country was poor as shit and constantly being hit by hurricanes, it didn't suffer for lack of food or people.  Growing tropical foods year round and churning out lots of conscripts eager to be sent LITERALLY ANYWHERE ELSE was their strength; they were basically North Korea in winter-less paradise.  
</p><p><b>The Cubans are what you want to play if the Czechs aren't cheap enough and the Iraqis aren't skilled enough.</b> Armed with weaponry straight from the Arab-Israeli wars of the 1960s and 70s, they fight bravely (if suicidally) for the liberation of American working peoples. To help them in their quest, they have the skill and motivation of the East Germans, making pulling off movement orders and using artillery less incredibly frustrating thanks to their combat experience in Angola. Their best tank is the base model T-62, roughly equivalent to East German T-55AM2s, and their worst is the SU-100, a vintage WW2 tank destroyer with absolutely no redeeming qualities in this era, other than that it costs less than a point per tank. If you like large amounts of subpar equipment, lots of painting, and killing communists, Cubans are just the army for you!
</p><p>Cuba is present in the new Red Dawn book as a Warsaw Pact force. The justification for Cuba's presence is twofold. The first is that as a Communist nation right next to the US, Cuba would have been seen as an asset during any invasion of the Americas. The second is due to their presence in the movie as something of a Rear-Guard force and leader of the Spanish speaking allies.
</p><p>Defining Units: <a href="/wiki/SU-100" title="SU-100">SU-100</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li class="mw-empty-elt"></li>
<li class="mw-empty-elt"></li>
<li class="mw-empty-elt"></li></ul>
<p><br />
</p>
<dl><dt>Weaknesses</dt></dl>
<ul><li class="mw-empty-elt"></li>
<li class="mw-empty-elt"></li>
<li class="mw-empty-elt"></li></ul>
<pre>Infantry:
Transports:
Tanks:
Anti-Tank:
Recon:
Artillery:
Aircraft:
Anti-Air:
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Cuban Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/T55AM2" title="T55AM2">T-55</a> • <a href="/wiki/T-62M" title="T-62M">T-62</a> • <a href="/wiki/SU-100" title="SU-100">SU-100</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/BTR-60" title="BTR-60">BTR-60</a> • <a href="/wiki/BMP" title="BMP">BMP-1</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/Motor_Rifle_Company#Batallón_de_Infantería" title="Motor Rifle Company">Batallón de Infantería</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/2S1_Carnation" title="2S1 Carnation">2S1 Carnation</a> • <a href="/wiki/2S3_Acacia" title="2S3 Acacia">2S3 Acacia</a> • <a href="/wiki/BM-21_Hail" title="BM-21 Hail">BM-21 Hail</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/SA-13_Gopher" title="SA-13 Gopher">SA-13 Gopher</a> • <a href="/wiki/SA-9_Gaskin" class="mw-redirect" title="SA-9 Gaskin">SA-9 Gaskin</a> • <a href="/wiki/SA-8_Gecko" title="SA-8 Gecko">SA-8 Gecko</a> • <a href="/wiki/ZSU-57-2" title="ZSU-57-2">ZSU-57-2</a> • <a href="/wiki/M53/59_Praga" title="M53/59 Praga">M53/59 Praga</a> • <a href="/wiki/ZSU_23-4_Shilka" title="ZSU 23-4 Shilka">ZSU 23-4 Shilka</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/Spandrel" title="Spandrel">Spandrel</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/BMP" title="BMP">BMP-1 OP</a> • <a href="/wiki/BRDM-2" title="BRDM-2">BRDM-2</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/MI-24_Hind" title="MI-24 Hind">MI-24 Hind</a> • <a href="/wiki/SU-25_Frogfoot" title="SU-25 Frogfoot">SU-25 Frogfoot</a> • <a href="/wiki/SU-22_Fitter" title="SU-22 Fitter">SU-22 Fitter</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading3"><h3 id="Middle_Eastern_Powers">Middle Eastern Powers</h3><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=30" title="Edit section: Middle Eastern Powers">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div style="margin-top:1em;margin-bottom:1em"><i>"The whole melodrama of the Middle East would be improved if amnesia were as common here as it is in melodramatic plots."</i>
<dl><dd><small>– P. J. O'Rourke</small></dd></dl></div>
<p>What's that, the folks in Europe are shooting each other again? The War To End All Wars ended up getting another sequel?! Time for a renewed surge of violence in the Middle East! 
</p><p>Apart from Turkey, which did join NATO, nobody anywhere near the Middle East (except maybe the various Soviet "Stans" depending on where exactly your draw the middle east's borders) ever actually joined NATO or the Warsaw Pact. Both of those coalitions made overtures to the various nations in that region, partly because they knew the other was going to, and partly because some of those Middle Eastern countries are absolutely loaded with oil. Iran, Iraq, and Israel are the three major players as World War III in Europe inevitably spreads into the Middle East, and the one thing they agree on is they all hate each other with pretty much equal intensity. 
</p><p>In 1985, Iran is a theocratic Islamic republic that was westernizing until a few years ago when they decided to tell America to get rekd. Their neighbor is Iraq, a one party authoritarian dictatorship enjoying the benefits of America's new "Fuck Iran" policy. The two have been at war since 1980, and to pour gas on the fire they follow different branches of Islam.
</p><p>Meanwhile on the coast, Israel is at war with... well pretty much everyone. The Yom Kippur War broke out in 1973, pitting Israel against Egypt, Syria, Saudi Arabia, Algeria, Jordan, Iraq, Libya, Kuwait, Tunisia, Morocco, Sudan, Pakistan, Lebanon, and <a href="/wiki/What" title="What">Cuba because why the fuck not</a>. Officially most of these countries are still technically at war with Israel in 1985 <i>(and Cuba still is 2024, because why the fuck not)</i>, although the fighting is mostly confined to Lebanon.
</p><p>When WWIII winds its way into the desert, it finds two wars in full swing and a mess of complex backroom deals for arms and oil. The easiest case to understand is Israel. Israel in the 80's is the west's BFF, but they're regarded as a loose cannon for their tendency to <a href="/wiki/That_Guy" class="mw-redirect" title="That Guy">start shit and assassinate people</a> seemingly just to remind the world that they exist. They're also known for not throwing ANYTHING away; in a serious fight their reservists would be using WW2 vintage hardware if they had to.
</p><p>The Soviets best friend in the region is Iran, although this loyalty is only skin deep. The Ayatollah is no communist, he simply hates the decadent, heretical westerners. Right up until 1978 the Iranians had been getting the best hardware the west was willing to sell them. America wanted to make Iran a big fortress of freedom keeping the Soviets away from all the oil, but the revolution threw those plans out the window.
</p><p>Iraq for their part had never really been anyone's friend. The Ba'athist party came to power in 1967 basically because the army was really mad at Israel. The Soviets were willing to sell them weapons but not the best stuff. But after Iran flipped off America, the CIA and the Saudis got really interested in propping up Iraq as an angry puppet against Iran.
</p><p>Which brings us to the most notable non-participants in WWIII, Saudi Arabia, Egypt and Turkey. The Saudis in 1985 are disgustingly rich, chummy with NATO but not vocal about it, and very vocal about hating Israel but talk is cheap. Meanwhile, Egypt in the 80's is under the leadership of a reformer who is less interested in war and more interested in using the Suez as an economic engine to rebuild Egypt (of course, even if Egypt were to not take sides in WW3, the Suez is just too strategically important to ignore...). Then there's Turkey. Turkey joined NATO in 1952, so it would very much be in this fight, and with it's location keeping the Black Sea fleet in the Black Sea and not causing trouble in the mediterranean, they very quickly be a front the Soviet would open to uncork that fleet and let it cause some real chaos, yet the Turk's lack an army list. . .yet.
</p><p>In summary, the Middle East of the 80's is a mess of ambiguous allegiances colored by both extremely old and very new animosities. But in practical gameplay terms what it means is the opportunity to wield PACT hordes with the support of the latest western airbrrrrrrt (Iraq), or field older NATO tanks at Soviet discount prices (Iran), or shred <strike>goyim</strike> BMP and Milan spam with equal efficiently (Israel).
</p>
<div class="mw-heading mw-heading4"><h4 id="Israel">Israel</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=31" title="Edit section: Israel">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div style="margin-top:1em;margin-bottom:1em"><i>"Let me tell you something that we Israelis have against Moses: He took us 40 years through the desert in order to bring us to the one spot in the Middle East that has no oil."</i>
<dl><dd><small>– Golda Meir</small></dd></dl></div>
<p><u>Difficulty</u>: 3/5 (Effective against other Oil War armies, struggles against v2 armies)
</p><p>Forged by near-constant war since State of Israel declared its independence in 1948 (instantly starting a war as its enraged Muslim neighbors all attacked), the Israel Defence Forces stand as one of most effective armies in 20th-century history. They are an army of Jews, sworn to act as the sword and shield of the long-dreamt-of Jewish homeland, and they are both well-trained, battle-hardened, and fiercely motivated. The IDF have lived with a "backs to the wall" mentality since the beginning; they know that losing once in the wrong time and wrong place could well mean losing Israel. But they also know that they're safer being feared; eighteen years before Team Yankee, Israel fought the Six Day War against all its neighbors and won, virtually obliterating the Egyptian and Jordanian air forces while taking the Sinai, and six years later held their gains in the Yom Kippur War.
</p><p>Driven by constant pressure and the endless threat of danger and defeat, the IDF has been extremely innovative and adaptable with their equipment right from the start. They deliberately use literally <i>anything</i> they can get their hands on, with an array of weaponry ranging from World War II-vintage Sten SMG's, Soviet-made Shilkas captured from their not-so-friendly Muslim neighbors, purchased American tanks and a handful of home-grown items. While the WW2 tech has been passed to the reservists by now, Team Yankee's IDF options largely ignore this ramshackle history beyond a few looted wagons, which is a shame because M50 "Super Shermans" would be fun to use. You could, if you really wanted, use "Flames of War" and "Fate of a Nation" units to put together an IDF reservist force, but that would require extra work. The IDF in any format are well-trained and well-motivated. No matter what they're driving, flying or shooting, they are skilled and brave, making them a formidable enemy to anyone who goes up against them.
</p><p>Israeli battlegroups have one of the deadliest anti-infantry arsenals with napalm bombers, tanks with Brutal and ROF 2 on the move, and infantry that could outfight the Americans' legendary 82nd Airborne. Anti-armour is a clear weakness, you only have a handful of units able to punch through previous generation tanks and <s>nothing</s> some American-style AT upgrades capable of hurting the latest tanks from the front. IDF units have nearly identical stats to the West Germans: 3+ stats across the board, except for 4+ assault and courage.
</p><p>The Israelis may take allied NATO formations in their battlegroups.
</p><p>Defining Units:
<a href="/wiki/Merkava" title="Merkava">Merkava</a>, <a href="/wiki/Pereh" title="Pereh">Pereh</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>Deadliest anti-infantry weapons currently in the game.</li>
<li>Infantry platoons which can beat tanks, and excel at firefights.</li>
<li>Ideal for combined arms players with some experience.</li>
<li>The closest thing IRL has to Cadians.</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Extremely few units which can penetrate 3rd generation tanks.</li>
<li>Mediocre anti-air arsenal.</li>
<li>Literally everyone else expects you to stab them in the back at some point.</li>
<li>Terrified of shellfish.</li></ul>
<pre>The Breakdown:
Infantry: Good at firefighting with strong stats but not much else. 3/5
Transports: The metal box of the free world...again. 3/5
Tanks: Great fire support, terrible tank killer. 3/5
Anti-Tank: Seriously lacks tools to deal with heavy tanks. 2/5
Recon: Mediocre, but cheap. 3/5
Artillery: 3+ skill, and you have an artillery piece for every mission. 4/5
Aircraft: Slightly weaker anti-armour, excellent anti-infantry. 4/5
Anti-Air: Solid SPAAGs, but suffers against NATO aircraft. 3/5
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Israeli Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/Merkava" title="Merkava">Merkava</a> • <a href="/wiki/M60_Patton" title="M60 Patton">M60 Patton</a> • <a href="/wiki/Centurion_Tank" title="Centurion Tank">Centurion</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/M113_Armored_Personnel_Carrier" title="M113 Armored Personnel Carrier">M113 Armored Personnel Carrier</a> • <a href="/wiki/Nagmasho%E2%80%99t" title="Nagmasho’t">Nagmasho’t</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/IDF_Infantry_Platoon" title="IDF Infantry Platoon">IDF Infantry Platoon</a> • <a href="/wiki/IDF_Reserve_Infantry_Platoon?action=edit&amp;redlink=1" class="new" title="IDF Reserve Infantry Platoon (page does not exist)">IDF Reserve Infantry Platoon</a> • <a href="/wiki/IDF_Paratrooper_Platoon?action=edit&amp;redlink=1" class="new" title="IDF Paratrooper Platoon (page does not exist)">IDF Paratrooper Platoon</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/M109_Howitzer" title="M109 Howitzer">M109 Howitzer</a> • <a href="/wiki/M106_Heavy_Mortar_Carrier" title="M106 Heavy Mortar Carrier">M106 Heavy Mortar Carrier</a> • <a href="/wiki/M106_Heavy_Mortar_Carrier" title="M106 Heavy Mortar Carrier">M125 Mortar Carrier</a> • <a href="/wiki/M270_MLRS" title="M270 MLRS">M270 MLRS</a> • <a href="/wiki/BM-21_Hail" title="BM-21 Hail">BM-21 Hail</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/M163_VADS" title="M163 VADS">M163 VADS</a> • <a href="/wiki/ZSU_23-4_Shilka" title="ZSU 23-4 Shilka">ZSU 23-4 Shilka</a> • <a href="/wiki/M48_Chaparral" title="M48 Chaparral">M48 Chaparral</a> • <a href="/wiki/Redeye_SAM_Platoon" title="Redeye SAM Platoon">Redeye SAM Platoon</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/Pereh" title="Pereh">Pereh</a> • <a href="/wiki/M150_TOW" title="M150 TOW">M150 TOW</a> • <a href="/wiki/Jeep" title="Jeep">Jeep TOW</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/M113_Recce" title="M113 Recce">M113 Recce</a> • <a href="/wiki/Jeep" title="Jeep">Jeep Recce</a> • <a href="/wiki/Rabbi_Recce?action=edit&amp;redlink=1" class="new" title="Rabbi Recce (page does not exist)">Rabbi Recce</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/AH-1_Cobra_Attack_Helicopter" title="AH-1 Cobra Attack Helicopter">AH-1 Cobra Attack Helicopter</a> • <a href="/wiki/AH-64_Apache_Attack_Helicopter" title="AH-64 Apache Attack Helicopter">AH-64 Apache Attack Helicopter</a> • <a href="/wiki/A4_Skyhawk" title="A4 Skyhawk">A4 Skyhawk</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="Iraq/Syria"><span id="Iraq.2FSyria"></span>Iraq/Syria</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=32" title="Edit section: Iraq/Syria">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p><i>Why are we on the same side as Israel?...and why are those Abrams giving me Déjà vu?"</i>
</p><p><u>Difficulty</u>: 4/5 (The challenge of a WARPAC list, made easier with NATO allies)
</p><p>Universally feared in the Middle East as the strongest conventional military force in numbers and technology, the Iraqi Armed Forces boast a mix of Western and Soviet equipment and the largest military in the region. Despite being bested by the Israelis during the Six-Days War, the 80s Iraqis were a very respectable force in the context of a head-on conventional war. By 1990, they were the 4th largest army in the world with over 900,000 troops in the military with one of the largest tank fleets in the Middle East, though take that statement with a grain of salt about their effectiveness since by <a rel="nofollow" class="external text" href="https://en.wikipedia.org/wiki/Gulf_War">1991 they had the second largest army in Iraq</a>. That being said, this all took place well after 1985, when back in 1979, despite Iraq being in the Soviet sphere of influence, the US gave some material support to Iraq during the Iraq-Iran war. You can make an argument for Iraq being on either NATO's or PACT's side in this conflict.
</p><p>Iraqi lists are 'constructed' at the Division level, meaning that you have access to support units that would usually be found at the company level in other armies. While you do have a few French units, your combat troops have Soviet equipment and can be expected to perform like poorly trained PACT troops. Iraqis have 4+ stats across the board, except for 5+ assault and 5+ skill. They also operate at the company level like other PACT armies.
</p><p>Uniquely for a faction with as much soviet gear as they do, Iraqis may take NATO allied formations in their battlegroups, if you've ever fantasized about a functional Iraqi-US coalition force. In game terms, this lets you have cheap conscript horde working alongside the best of the West. If you want a tarpit of conscripts protecting objectives while your Leopard 2s or Merkavas tear things up, this is the faction for you. You also have the USAF providing air cover with Warthogs and Harriers.
</p><p>The Syrians are an official modification to the Iraqi list, losing the AMX AuF1, VCR/TH, AMX Roland, AMX-10P, US air support and all NATO allies. In exchange, they get access to the SU-25 and PACT allied formations.
</p><p>Defining Units: <a href="/wiki/T-62M" title="T-62M">T-62</a>, <a href="/wiki/Motor_Rifle_Company" title="Motor Rifle Company">Motor Rifle Company</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>Large unit sizes with a point cost between East Germans and Czechs.</li>
<li>Access to NATO tools like the AMX-AuF1 and the Gazelle HOT.</li>
<li>Ideal for WARPAC commanders dabbling in NATO equipment and allies.</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Almost all support units at the divisional level.</li>
<li><a href="/wiki/Planetary_Defense_Force" class="mw-redirect" title="Planetary Defense Force">Units have the morale of WARPAC troops and the training of Russian conscripts.</a></li>
<li>Addicted to nerve agents.</li></ul>
<pre>The Breakdown:
Infantry: Tanned Pact troops with Ruskie training videos. 3/5
Transports: Many mediocre options for versatility. 3/5 
Tanks: Inferior to Pact tanks, in training and tech. 2/5
Anti-Tank: Very fragile, but you can beat 3rd-gen tanks. 3/5
Recon: Cheap scout that can't kill anything. 2/5
Artillery: High-tech, average cost, low skill. 2/5
Aircraft: Nothing overpowered, but you have a solution for every problem. 4/5
Anti-Air: Plenty of options for the perfect AA net! 5/5
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Iraqi Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/T55AM2" title="T55AM2">T-55</a> • <a href="/wiki/T-62M" title="T-62M">T-62</a> • <a href="/wiki/T-72M" title="T-72M">T-72M</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/BTR-60" title="BTR-60">BTR-60</a> • <a href="/wiki/OT-64" title="OT-64">OT-64</a> • <a href="/wiki/AMX-10P" title="AMX-10P">AMX-10P</a> • <a href="/wiki/BMP" title="BMP">BMP-1</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/Motor_Rifle_Company" title="Motor Rifle Company">Motor Rifle Company</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/2S1_Carnation" title="2S1 Carnation">2S1 Carnation</a> • <a href="/wiki/2S3_Acacia" title="2S3 Acacia">2S3 Acacia</a> • <a href="/wiki/AMX_Auf1" title="AMX Auf1">AMX Auf1</a> • <a href="/wiki/BM-21_Hail" title="BM-21 Hail">BM-21 Hail</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/ZSU_23-4_Shilka" title="ZSU 23-4 Shilka">ZSU 23-4 Shilka</a> • <a href="/wiki/SA-13_Gopher" title="SA-13 Gopher">SA-13 Gopher</a> • <a href="/wiki/SA9_Gaskin" title="SA9 Gaskin">SA9 Gaskin</a> • <a href="/wiki/SA-8_Gecko" title="SA-8 Gecko">SA-8 Gecko</a> • <a href="/wiki/AMX_Roland" title="AMX Roland">Roland AA</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/Spandrel" title="Spandrel">Spandrel</a> • <a href="/wiki/VCR/TH" title="VCR/TH">VCR/TH</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/BRDM-2" title="BRDM-2">BRDM-2</a> • <a href="/wiki/BTR-60" title="BTR-60">BTR-60 OP</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/MI-24_Hind" title="MI-24 Hind">MI-24 Hind</a> • <a href="/wiki/Gazelle_Helicopter" title="Gazelle Helicopter">Gazelle HOT</a>
</td></tr>
<tr>
<th nowrap="">US Support
</th>
<td><a href="/wiki/A-10_Warthog" title="A-10 Warthog">A-10 Warthog</a> • <a href="/wiki/AV-8_Harrier" title="AV-8 Harrier">AV-8 Harrier</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="Iran">Iran</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=33" title="Edit section: Iran">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div style="margin-top:1em;margin-bottom:1em"><i>"Throw away your prayer chain and buy yourself a gun. For prayer chains keep you in stillness while guns silence the enemies of Islam."</i>
<dl><dd><small>– Ayatollah Khamenei</small></dd></dl></div>
<p><u>Difficulty</u>: 4/5 (Excels in the hands of veterans, unfriendly to beginners.)
</p><p>Formerly an American ally of convenience, and already at war with Iraq before World War III started in August 1985, the Islamic Republic of Iran has wound up as a de-facto ally of the atheistic Warsaw Pact. The underdogs of the Middle East, the Iranian military lack the generations of combat experience of the Israelis or the raw numbers of the Iraqis but compensate through sheer fanaticism. By the Iran-Iraq War, the Iranian military was only able to repel invading Iraqi forces thanks to foreign equipment and local militias slowing the initial Iraq advance.
</p><p>Iranian armies featured iconic Soviet platforms but typically used Western vehicles - without the latest upgrades, of course. It’s strange to see Iran side with the Soviet Union in this scenario, if only because they were one of the major backers of the Mujahideen in the Soviet-Afghan War. But politics can make for strange bedfellows indeed, and this fiercely religious state's alliance with the explicitly atheist USSR and its client states in Eastern Europe is far from the only unusual partnership of the 20th century.
</p><p>The Iranians play with NATO vehicles using PACT doctrine (holdovers from the last regime, when the Americans propped up Iran as a buffer state against the Soviet Union), operating M113s and Chieftains as the backbone of their force. The Americans and British are obviously no longer supplying spare parts, but the Iranians manage somehow, running their bizarre mishmash of NATO and WarPac machines and weapons, some of which are still in service today. Statwise, the Iranians are more fanatical than Soviets with 3+ across the board, but with 5+ assault and skill. Your illiterate hajis won't understand orders but are guaranteed to outlast nearly any foe on the battlefield in a contest of attrition.
</p><p>Iranian armies operate at the platoon level much like NATO's forces except for the Basij, and may take allied formations from the Warsaw Pact despite the communist hatred of all things religious. If you like NATO tanks, painting desert camo and <s>unironically saying Allahu Akbar </s> getting placed on FBI watchlists, boy do I have the army for you.
</p><p>Defining Units:
<a href="/wiki/Chieftain" title="Chieftain">Chieftain</a>, <a href="/wiki/Basij_Infantry_Company" title="Basij Infantry Company">Basij Infantry Company</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>Insanely cheap platoons that let you bring several companies easily.</li>
<li>High morale means units can practically disregard pinning/bails/losses.</li>
<li>Beige.</li>
<li>Literal jihadists.</li></ul>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Extremely squishy armour formations capped at 3 tank platoons.</li>
<li>Atrocious anti-armour capability.</li>
<li>I hope you like painting beige.</li>
<li>Literal jihadists.</li></ul>
<pre>The Breakdown:
Infantry: Good balance between infantry spam and mediocre infantry. 4/5
Transports: Average transports with quite a bit of choice. 3/5
Tanks: Soviet tanks and outdated Chieftains. 2/5
Anti-Tank: Your strongest AT platoons can't penetrate an M1IP. 1/5
Recon: Passable: not bad, but not great. 3/5
Artillery: A calibre for every target and every list. 4/5
Aircraft: Passable anti-tank, lacks a bomber. 3/5
Anti-Air: Nearly identical to PACT anti-air. 4/5
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Iranian Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/T55AM2" title="T55AM2">T-55</a> • <a href="/wiki/T-62M" title="T-62M">T-62</a> • <a href="/wiki/M60_Patton" title="M60 Patton">M60 Patton</a> • <a href="/wiki/Chieftain" title="Chieftain">Chieftain</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/M113_Armored_Personnel_Carrier" title="M113 Armored Personnel Carrier">M113 Armored Personnel Carrier</a> • <a href="/wiki/BTR-60" title="BTR-60">BTR-60</a> • <a href="/wiki/BMP" title="BMP">BMP-1</a>
</td></tr>
<tr>
<th nowrap="">Troops
</th>
<td><a href="/wiki/Iranian_Mechanized_Platoon" title="Iranian Mechanized Platoon">Iranian Mechanized Platoon</a> • <a href="/wiki/Basij_Infantry_Company" title="Basij Infantry Company">Basij Infantry Company</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/M109_Howitzer" title="M109 Howitzer">M109 Howitzer</a> • <a href="/wiki/BM-21_Hail" title="BM-21 Hail">BM-21 Hail</a> • <a href="/wiki/M125_81mm" title="M125 81mm">M125 81mm</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/ZSU_23-4_Shilka" title="ZSU 23-4 Shilka">ZSU 23-4 Shilka</a> • <a href="/wiki/ZSU-57-2" title="ZSU-57-2">ZSU-57-2</a> • <a href="/wiki/SA-8_Gecko" title="SA-8 Gecko">SA-8 Gecko</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/Jeep" title="Jeep">Jeep TOW</a> • <a href="/wiki/Jeep_106mm_Recoilless" title="Jeep 106mm Recoilless">Jeep 106mm Recoilless</a> • <a href="/wiki/M113_106mm_Recoilless" title="M113 106mm Recoilless">M113 106mm Recoilless</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/CVRT#Scorpion" title="CVRT">Scorpion</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/AH-1_Cobra_Attack_Helicopter" title="AH-1 Cobra Attack Helicopter">AH-1 Cobra Attack Helicopter</a>
</td></tr>
<tr>
<th nowrap="">Soviet Support
</th>
<td><a href="/wiki/SU-25_Frogfoot" title="SU-25 Frogfoot">SU-25 Frogfoot</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading3"><h3 id="Asian_Powers">Asian Powers</h3><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=34" title="Edit section: Asian Powers">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div style="margin-top:1em;margin-bottom:1em"><i>"I don't want to know what happened in the past. All I want to know is who are my commanders, where are the Chinese, and how much ammunition have I got."</i>
<dl><dd><small>– Indian Field Marshal Sam Manekshaw</small></dd></dl></div>
<p>You may have noticed that this may be a "world war," but there is one notable part of the world currently left out of the fighting: Asia, and by "Asia" we mean China, and to a much lesser degree Japan and Korea. Korea is an easy one: that is a situation that would almost 100% pop off in a World-War-Three situation. In our world, the Soviet Union reduced aid to North Korea in 1985 under Mikhail Gorbachev, but in Team Yankee we got a military hawk which is what set all this off. So, this is a fight the USSR would be stoking if for no other reason than the USSR would love to draw US troops away from Europe and really put America's claim of being able to fight "two-and-a-half wars" to the test. North Korea with heavy support from the USSR would also likely go for it. Japan, meanwhile, is still technically barred from waging offensive wars, but in 1960 it signed a defensive treaty with the USA that also is the legal justification for US military bases. Thus in a WW3 situation, USSR declares war on Europe, NATO triggers so America is at war, then the Treaty of Mutual Cooperation and Security between the United States and Japan triggers and Japan is also at war with the USSR, and presumably North Korea in the aforementioned situation in which the USSR starts that up. So USA, Japan and South Korea vs. the USSR and North Korea—there you go, Battlefront, I just wrote the plot of an entire expansion for you. This does have the awkward result of putting Japan and South Korea on the same side and...those two nations HATE each other thanks to the legacy of Japan's colonial rule over Korea. It's so bad that during joint exercises the Americans physically put their ships between the Japanese and South Koreans. It's so bad, in fact, that if you put Japan and South Korean models on the same side of a game board you might cause blow back from South Koreans and Japanese players. So this is perhaps a reason why this very obvious trigger has not been pulled.
</p><p>And now to address the Dragon in the room: China. China is...complicated. It is 100% a communist power, and had this game been set during the late 1950s-60s, China would be in this fight as well on the USSR side since the USSR helped the early Chinese Communist Party (CCP) in one of the Cold War's first proxy conflicts, with the USA supporting the Nationalists who would later be reduced to Taiwan. But the two nations would drift apart, and by the time of Team Yankee the two communists governments are very much split. Nowadays China is seen as a super power and by 1985 it's very much a regional "big dog" just starting to flex its international muscles in ways that it's still doing to this day. The big question, of course, is if WW3 started between the USSR and NATO, would China get involved?
</p><p>That scenario is very hard to predict. You could say the Chinese join, reluctantly, with the Soviets to prevent the USA from taking all of North Korea and putting a unfriendly power on their border. You could also say that the USA could preemptively strike China, expecting it to join a war and wanting to get a cheap shot before it's ready, which would make it join the USSR that way. You could make the argument they would join the American/NATO side in order to get territory grabs from the USSR and resolve some territorial disputes while it is distracted. You could also argue the same from the other side: join the USSR to get territory protected by the USA that it claims (COUGH-Taiwan-COUGH) You could even reasonably expect China simply to do the opposite of whatever India does (which would also mean it ends up on the same side as Pakistan). Really, it's a crap shoot with China. And despite how logical it is for Asian action in this WW3 alternate history Battlefront is using, it's an open question it even shows up at all given how touchy the CCP is about depictions of China and how tense things are between China and the West currently.
</p><p>And then finally there's India. India during the Cold War was the poster child for non-interventionism and leading "the third way", which was a convenient foil for its actual motivation of really hating China. At first, India wanted to just distance itself from Great Britain, although its relations with the Communists were hardly any better as the Soviets had a hand in Pakistan. The real turning point came when Nixon went to China. To India, this meeting was a startling turn for the worse, and in response it started hedging its bets by buying weapons from the Soviets. In any Cold War scenario, the only constant about India is its loathing of China; all other interactions pivot around that relationship.
</p><p>As of the 2025 Christmas video, an Asian Front expansion for Team Yankee has finally been announced, including the People's Republic of China, Taiwan and the two Koreas. Japan has been currently left out, which makes sense given the amount of unique, locally-produced equipment used by the JSDF.
</p>
<div class="mw-heading mw-heading3"><h3 id="African_Powers">African Powers</h3><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=35" title="Edit section: African Powers">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>Though it might have been called the 'Cold War' it was anything but in the patchwork of states formed in the wake of colonial rule across the continent of Africa. Africa was a key front in the global ideological conflict between the United States and the Soviet Union as both sought to woo newly-independent African nations to support one side or the other.
</p><p>First thing to note is that Cuba is a surprisingly active player in Africa sending troops to at least 17 African nations and three insurgencies, in fact introducing Cuba as a Faction in an African expansion rather then a Silly "Red Dawn" movie themed expansion would make more sense, Wolverines be darned. This is largely due to Cuba looking at the American's big,girthy,overwhelming,defense budget and deciding it was easier to spread communism away from where it would scare there neighborhood's 300lb gorilla, with a secondary reason that <a href="/wiki//pol/" title="/pol/">Che's views on black people would horrify cotton plantation owners.</a>
</p><p>As far as native African powers there are a couple of note: first is the Union of South Africa. They were a major military power in Sub-Saharan Africa and a state built upon Apartheid, a system where the black majority were disempowered, disenfranchised and brutally oppressed by the ruling white minority (Look up the Sharpeville massacre). Apartheid was extremely unpopular outside South Africa and a sense of global outrage and opposition to this system of government saw South Africa develop a siege mentality of standing alone against a sea of foes within and without. With its fellow Apartheid state of Rhodesia consigned to the dustbin of history by 1985 after its own long and bloody war with internal guerillas, South Africa found itself in a tight spot by 1985 as it clashed with African and allied Cuban forces in Namibia (then South West Africa), Zambia, and Angola. To this end South Africa had invested heavily in its armed forces, including the indigenous Olifant Tank (An upgrade of the Centurion) and the Eland and Ratel-90 armoured cars. Though considered morally repugnant, in a WWIII scenario it's likely the Union of South Africa would have become an unwelcome part of the 'free world' forces in their global struggle with Communism. There is a fan supplement for the SADF that you can find here: <a rel="nofollow" class="external autonumber" href="http://downunderwargames.blogspot.com/2023/12/savannah-storm-sadf-in-team-yankee-and.html">[1]</a>
</p><p>From there though there are not a lot of good options. There was plenty of conflict across the continent of Africa but militarily the many states involved were a bit interchangeable. Very few African nations made there own patterns of military equipment, and oftentimes what they did have they didn't have a lot of. Rwanda for example has T55's...34 of them in fact. Additionally for the scale Team Yankee works at you really want vehicles to be unique to set the factions apart, but the reality of war in Africa is the ones who weren't buying weapons from Russia were buying weapons from France (and nowadays they all buy from China). In fact you could probably cobble a list for most African nations out of existing gear and adjust the various skill values depending on what you thought was fair for that nation.
</p>
<div class="mw-heading mw-heading3"><h3 id="Unofficial_Rules_-_Alternative_Nations_and_Special_Forces">Unofficial Rules - Alternative Nations and Special Forces</h3><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=36" title="Edit section: Unofficial Rules - Alternative Nations and Special Forces">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p>Unlike the Swedish, who will undoubtedly get their own rules in years to come, you can follow the link below to play as one of the following nations: Spain (which actually joined NATO in 1982), Greece (joined NATO in 1952), Ireland, Yugoslavia, Albania, Denmark, Belgium, Romania, Switzerland, Finland, <a href="/wiki/Italy" title="Italy">Italy</a>, Austria, Norway, Sweden, Turkey, Hungary, Bulgaria, Portugal, Mexico, Kuwait, Luxembourg, Malta, and Cuba.
</p><p>You can also find unofficial rules for US Army Rangers, British Royal Marines, ANZAC SAS, Polish Spec Forces, Canadian Airborne, Iranian Spec Forces, East German Paratroops, Czech Airborne, French Foreign Legion, Soviet Naval Infantry, Iraqi and Syrian Republic Guard, Israeli Commandos and West German and Dutch Marines. You can even play now as Terrorists/ Guerrillas!
</p><p><a rel="nofollow" class="external free" href="https://www.researchgate.net/publication/344587741_TEAM_YANKEE_UNOFFICIAL_RULES_COMPENDIUM_-_NATIONAL_AND_SPECIAL_FORCES_RULES">https://www.researchgate.net/publication/344587741_TEAM_YANKEE_UNOFFICIAL_RULES_COMPENDIUM_-_NATIONAL_AND_SPECIAL_FORCES_RULES</a>
</p><p>Also it's not been done <i>yet</i> (and probably in bad taste to do so just yet, not to mention <a href="/wiki/Skub" title="Skub">you'll get arguments as to how good the balance is</a>) but you could easily cobble together a pair of army lists to represent the Ukraine and Russian in there ongoing War given that most of the vehicles involved are already stated. The only thing you'd have to figure out would be how the hell to represent drones and it be a relatively easy project.
</p>
<div class="mw-heading mw-heading3"><h3 id="The_Neutral_Powers">The Neutral Powers</h3><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=37" title="Edit section: The Neutral Powers">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div class="mw-heading mw-heading4"><h4 id="Sweden">Sweden</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=38" title="Edit section: Sweden">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div style="margin-top:1em;margin-bottom:1em"><i>"Håll gränsen!" - "Hold the Border!"</i>
<dl><dd><small>– Sewdish prime Minister Thorbjörn Fälldin, during the 'Whiskey on the Rocks' incident as Soviet Ships steamed toward Sweden</small></dd></dl></div>
<p>Maintaining a policy of armed neutrality since 1814, Sweden never joined NATO despite Denmark and Norway being among the first to sign up... Until recently where it finished the process of making the Baltic into a NATO lake. The idea being that if WW3 went hot, Sweden would be at the bottom of the target list and have a better chance of making it through. Sweden was also very close to developing its own nuclear bomb but abandoned the project for political reasons. In the event of a war however, the Swedes would likely break their long-standing neutrality to support their Scandinavian comrades against the Communist threat to their way of coffee breaks every 2 hours. This happens in Sir John Hackett's novel <i>The Third World War: The Untold Story</i>, which Harold Coyle's <i>Team Yankee</i> is set within-the Swedes don't take kindly to the Soviet Air Force repeatedly invading their airspace to bomb Norway, and Sweden becomes a de facto NATO ally when they attack the Soviet bombers and the Soviets retaliate. Given how the Swedes responded during the "Whiskey on the Rocks' Incident they would likely be a lot more aggressive than that. <a rel="nofollow" class="external text" href="https://www.youtube.com/watch?v=ucDZ2MxubeQ">To cut a long story short</a>, a Soviet Submarine, NATO reporting name "Whiskey" (hence 'whiskey on the rocks'), crashed on the Swedish coast in 1981, near where the Swedish Navy had been doing some exercises. After a lot of bullshit, including finding out this submarine had fucking nuclear weapons on it, the Sweds got so fed up that when two Soviet ships went response to a distress call and made to enter Swedish territorial waters, the Swedish prime minster gave the order: "Hold the border". Sweden then went into full <i>"kill a commie for your mommy"</i> mode for about 20 minutes before the Soviets backed off. So yeah, Soviet Aircraft bombing targets from Swedish airspace? That would not fly nor be allowed to fly. So far that hasn't been made canon in Team Yankee, but Battlefront Miniatures could change that anytime.
</p><p>Sweden's infantrymen of the 80's had access to an excellent selection small arm, pragmatically picked from the best designs Europe had to offer. Their basic kit includes Glock pistols and domestic clones of the H&amp;K G3 and the FN FNC rifles, supported with 84mm Carl-Gustafs and a bewilderingly diverse inventory of machine guns. Their latest homegrown gadgetry at the time of Team Yankee was the then-experimental m/94 Strix, a heat-seeking anti-tank 120mm mortar round. Swedish forces were small but had lots of funding, giving them a small force of well-trained and equipped troops that stank of pickled herring. Designs like the Stridsvagn 103 (or 'S' tank) and the 37 'Viggen' were strange even for the time, with the Viggen's canard delta layout inspiring later designs like the French Rafale and Typhoon Eurofighter. The famous (or infamous, if you were a Nordic tanker) Strv-103 is a modern revival of the tank destroyer concept from World War 2, ditching the turret to create arguably the most defensive battle tank of the era. Capable of engaging enemy armour from forests or defensive positions with an annoyingly small profile, the Swedes effectively turned the battle tank as a military spearhead into a retreating defensive turret shaped like a cheese wedge.
</p><p>On the tabletop, the Swedish forces are Battlefront's attempt to eliminate the BMP parking lot meta with almost every aspect of your force capable of defeating massed BMPs and BTRs. Your artillery? It's expensive and turns armour into modern art. Your tanks will delete armour advancing beyond their deployment zone, but quickly become useless after moving or getting blinded by enemy smoke. This strength comes with some inevitable cons, such as having next to no anti-air options and your only homegrown solution to enemy T-80s being suicidal aircraft. Expect to take NATO allies if you expect to shore up these weaknesses, or adapt your playstyle accordingly.
</p><p>The Swedes have access to NATO and Finnish formations to round-out their BMP killing prowess.
</p><p>Defining Units:
<a href="/wiki/Strv_103" title="Strv 103">Strv 103</a>
</p>
<dl><dt>Strengths</dt></dl>
<ul><li>Force is almost tailor-made to defeat BMP parking lots and massed light armour.</li>
<li>Many options for offence and defence game plans, your units perform adequately outside their intended roles.</li>
<li>Free shipping for orders above $50.</li></ul>
<p><br />
</p>
<dl><dt>Weaknesses</dt></dl>
<ul><li>Has <a href="/wiki/Munchkin" class="mw-redirect" title="Munchkin">min-maxed tanks</a> - your offensive power lives and dies with your artillery and infantry.</li>
<li>Limited options for defeating aircraft and generation-3 tanks.</li>
<li>Screwdrivers sold separately.</li></ul>
<pre>The Breakdown:
Infantry:
Transports:
Tanks: Terrible offence, but unparalleled as a defensive anti-BMP force. 4/5
Anti-Tank:
Recon:
Artillery:
Aircraft:
Anti-Air: Limited range and availability, expect to take losses from enemy helos and planes. 1/5 
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Swedish Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/Strv_103" title="Strv 103">Strv 103</a> • <a href="/wiki/Centurion" title="Centurion">Centurion</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/Pbv_302" title="Pbv 302">Pbv 302</a>
</td></tr>
<tr>
<th nowrap="">Infantry
</th>
<td><a href="/wiki/Armored_Rifle_Platoon" title="Armored Rifle Platoon">Armored Rifle Platoon</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/Bandkanon_1" title="Bandkanon 1">Bandkanon 1</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/Lvrbv_701" title="Lvrbv 701">Lvrbv 701</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/IKV_91" title="IKV 91">IKV 91</a> • <a href="/wiki/Pvpjtgb_1111?action=edit&amp;redlink=1" class="new" title="Pvpjtgb 1111 (page does not exist)">Pvpjtgb 1111</a> • <a href="/wiki/Pvrbv_551" title="Pvrbv 551">Pvrbv 551</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/Pbv_302" title="Pbv 302">Pbv 302</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/AJ_37_Viggen" title="AJ 37 Viggen">AJ 37 Viggen</a> • <a href="/wiki/BO-105P" title="BO-105P">BO-105P</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading4"><h4 id="Finland">Finland</h4><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=39" title="Edit section: Finland">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<div style="margin-top:1em;margin-bottom:1em"><i>"Sisu."</i>
<dl><dd><small>– Every Finn in every war.</small></dd></dl></div>
<p>Poor Finland, caught in the worst possible position with the Soviet Union right on their doorstep. Architects of Finlandization, an attempt to hedge their bets and avoid pissing off their old enemy. Well in Team Yankee's timeline it doesn't work, and for the third time that century the Soviet Union's forces pour across the Finnish border. Of course this time Finland is prepared with enough fortifications to make Mannerheim himself blush.
</p><p>Of course legally the USSR, even more then normal in this alt history, is to blame for having to brave the ghost of the White Death. Of all the Axis powers of WWII Finland is the one that could barely be called a 'fascist' nation and more an 'Anti-Soviet' nation after the Winter War. Still, when the mustachio man took his medicine in Berlin the Finns were on the wrong side of the war and placed in the Soviet sphere of Influence for the second time and forcefully made a neutral nation that leaned Soviet. Treaties signed in 1948 made it so that Finland had to help the Soviets if the West attacked or ask the Soviets for help if the West attacked it, while also allowing Finland to stay out of the horn locking between the Sovets and Western world. The result of all this was Finland had a relativity smooth experiencing during the Cold War, never having to deal with Soviet tanks rolling into its capital when it flirted with democracy and never needing to buy over priced burgers from the West. In fact until Mikhail Gorbachev (who never appeared in Team Yankee) the Finns self-censored certain anti-Soviet books at the Soviet Union's request!
</p><p>Bluntly, Finland's whole geopolitical strategy in the Cold War was: "<i>We made it so every building in our nation has a bunker to survive a nuclear blast. Let Nato and the Soviets Nuke each other, we will relax in our saunas and when the dust clears ride out from our shelters to inherit the earth"</i>. And that is barely a meme! With no interest in dying either for the West or East it is sheer madness for the Soviet Union or Nato to invade and have <b>870,000 Angry Finns</b> join the other sides camp. Make no mistake: the Finns joining WWIII is the biggest - or second biggest if you include the Red Dawn Expansion - leap of imagination in this game.
</p><p>In real life and the tabletop, the Finns entered the 1980s with a primarily Eastern Bloc arsenal combined with NATO doctrine. Focused on retreating through and wearing out any attacker in Finland's deep forests, relying on infantry taking defensive positions and everything else supporting them. While your tank fleet might be serviceable, your anti-air roster is limited to man-portable anti-air missiles and two flavours of tanks with anti-air autocannons.  
</p><p>As of 2025, Finland has some of the best infantry in the game, with 3+ stats except for 4+ assault and counterattack. Bringing infantry mortars, recoilless rifles and anti-tank rockets to the fight, your troops will struggle to race across a table but present some of the most annoying forces an attacker will face. However, their limited roster does mean they have virtually no answer to enemy helicopter ATGMs and are especially vulnerable to artillery and salvo weapons. Of course,
</p><p>The Finns have access to Swedish allies, allowing you to build the forested trenchline of your dreams.
</p><p>Defining Units:
<a href="/wiki/T-72FM" title="T-72FM">T-72FM</a>, <a href="/wiki/81/120_KRH_mortar_team?action=edit&amp;redlink=1" class="new" title="81/120 KRH mortar team (page does not exist)">81/120 KRH mortar team</a>
</p>
<dl><dt>Strengths</dt></dl>
<dl><dt>Weaknesses</dt></dl>
<pre>The Breakdown:
Infantry:
Transports:
Tanks:
Anti-Tank:
Recon:
Artillery:
Aircraft:
Anti-Air:
</pre>
<table class="mw-collapsible mw-collapsed wikitable" style="width:100%;border: 2px solid black">
<tbody><tr>
<th colspan="2" style="background-color:lightgrey">Finnish Forces in <a class="mw-selflink selflink">Team Yankee</a>
</th></tr>
<tr style="border-top: 2px solid black">
<th nowrap="">Tanks
</th>
<td><a href="/wiki/T-72FM2" class="mw-redirect" title="T-72FM2">T-72FM2</a> • <a href="/wiki/T-72FM1" class="mw-redirect" title="T-72FM1">T-72FM1</a> • <a href="/wiki/T-55M" class="mw-redirect" title="T-55M">T-55M</a>
</td></tr>
<tr>
<th nowrap="">Transports
</th>
<td><a href="/wiki/BMP" title="BMP">BMP</a> • <a href="/wiki/BTR-60" title="BTR-60">BTR-60</a>
</td></tr>
<tr>
<th nowrap="">Infantry
</th>
<td><a href="/wiki/J%C3%A4%C3%A4k%C3%A4ri_Platoon" title="Jääkäri Platoon">Jääkäri Platoon</a>
</td></tr>
<tr>
<th nowrap="">Artillery
</th>
<td><a href="/wiki/120mm_Mortars" title="120mm Mortars">120mm Mortars</a> • <a href="/wiki/81mm_Mortars" title="81mm Mortars">81mm Mortars</a> • <a href="/wiki/BM-21_Hail" title="BM-21 Hail">BM-21 Hail</a> • <a href="/wiki/2S1_Carnation" title="2S1 Carnation">2S1 Carnation</a>
</td></tr>
<tr>
<th nowrap="">Anti-Aircraft
</th>
<td><a href="/wiki/T-55_Marksman" title="T-55 Marksman">T-55 Marksman</a> • <a href="/wiki/ZSU-57-2" title="ZSU-57-2">ZSU-57-2</a> • <a href="/wiki/ITO_78_Platoon?action=edit&amp;redlink=1" class="new" title="ITO 78 Platoon (page does not exist)">ITO 78 Platoon</a>
</td></tr>
<tr>
<th nowrap="">Tank Hunters
</th>
<td><a href="/wiki/PstObj_83?action=edit&amp;redlink=1" class="new" title="PstObj 83 (page does not exist)">PstObj 83</a> • <a href="/wiki/95_S_58-61_Recoilless_Rifles?action=edit&amp;redlink=1" class="new" title="95 S 58-61 Recoilless Rifles (page does not exist)">95 S 58-61 Recoilless Rifles</a>
</td></tr>
<tr>
<th nowrap="">Recon
</th>
<td><a href="/wiki/BMP" title="BMP">BMP-1 OP</a> • <a href="/wiki/BMP" title="BMP">BMP-2 Recon</a>
</td></tr>
<tr>
<th nowrap="">Aircraft
</th>
<td><a href="/wiki/AJ_37_Viggen" title="AJ 37 Viggen">AJ 37 Viggen</a>
</td></tr></tbody></table>
<p><br />
</p>
<div class="mw-heading mw-heading2"><h2 id="FAQ/General_Bulletin"><span id="FAQ.2FGeneral_Bulletin"></span>FAQ/General Bulletin</h2><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=40" title="Edit section: FAQ/General Bulletin">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<ul><li>There are three kinds of teams: Tank Teams, Infantry Teams, and Aircraft Teams
<ul><li>Tank Teams include every type of ground based vehicle, not just literal tanks. It is further broken down into Armoured, Unarmoured, and Transport types</li>
<li>Infantry Teams include all units made up of men fighting on foot</li>
<li>Aircraft Teams are comprised of Strike Aircraft and Helicopters</li></ul></li></ul>
<p><br />
</p>
<ul><li>For most units moving will lead to worse shooting (or not being able to shoot at all)</li>
<li>Tactical Speed allows you to shoot after moving</li>
<li>Dash speed prohibits shooting and the maximum distance depends on the unit and the terrain</li>
<li>Tank Teams must roll higher than their Cross value when moving into or through terrain or immediately end their movement</li>
<li>Movement can be enhanced using various orders based on Skill or Motivation</li>
<li>Friendly Tank and Infantry Teams can move through each other</li>
<li>Tank Teams can never move through other Tank Teams (except wrecks)</li></ul>
<p><br />
</p>
<ul><li>Units are hit based on their own Is Hit On value and not the shooting team's skill
<ul><li>A unit's Is Hit On value is modified by Concealment, Smoke, and other factors</li>
<li>Remaining in place and not shooting will make your units Gone To Ground</li>
<li>Units that are Gone to Ground and also Concealed are even harder to hit</li></ul></li>
<li>Infantry, aircraft, and soft skinned vehicles that are hit must make a saving throw or be destroyed
<ul><li>If the infantry unit is in Bullet Proof Cover the shooting team must also pass a Fire Power test</li>
<li>Armored vehicles take the armor value (AV) on the card, add a d6, and compare it to the shooting weapon's anti-tank (AT) value
<ul><li>If the total is less than the shooting weapon's AT then the target fails their Armour Save (if the weapon's AT exceeding your AV by 6 or more you will automatically fail)</li>
<li>If the total is the same as the shooting weapon's AT then the target also fails but the shot does limited damage</li>
<li>Failing an Armour Save does not mean automatic destruction. If the shooting unit then fails a Firepower roll the target stays alive (but is possibly Bailed Out)</li>
<li>The hull and turret are considered separately. Roll a d6 if both are exposed. On a 4+ the turret (if there is one) is hit instead of the hull
<ul><li>This only matters if the shooting unit is flanking the target (behind a line drawn across the front of the hull or turret)</li></ul></li></ul></li></ul></li>
<li>Long Range shooting carries a penalty to hit and AT (but this is often negated by rules for Laser Range Finders or Guided Missile technology)</li></ul>
<p><br />
</p>
<ul><li>You will find the rules on the back of cards, but just in case you're simply browsing, here are what they all mean
<ul><li>Brutal: Forces infantry units to reroll saves against this weapon</li>
<li>Laser Rangefinder: Negates penalty of shooting at longer range</li>
<li>Advanced Stabilizer: Increases the units maximum Tactical Speed</li>
<li>Stabilizer: Increases the units maximum Tactical Speed, but adds a penalty to shooting when moving beyond the standard Tactical Speed</li>
<li>Dedicated AA: Allows you to use full ROF against air units instead of just one die</li>
<li>HEAT: Negates Firepower penalty for Long Range</li>
<li>Guided: Negates hit penalty for Long Range</li>
<li>Thermal Imaging: Allows unit to ignore smoke, friendly or foe</li></ul></li></ul>
<div class="mw-heading mw-heading2"><h2 id="Books">Books</h2><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=41" title="Edit section: Books">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<ul class="gallery mw-gallery-traditional">
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Team-Yankee-cover.jpg" class="mw-file-description" title="Da Big Rulebook"><img alt="Da Big Rulebook" src="//static.wikitide.net/1d6chanwiki/thumb/4/43/Team-Yankee-cover.jpg/85px-Team-Yankee-cover.jpg" decoding="async" width="85" height="120" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/4/43/Team-Yankee-cover.jpg/127px-Team-Yankee-cover.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/4/43/Team-Yankee-cover.jpg/170px-Team-Yankee-cover.jpg 2x" data-file-width="283" data-file-height="400" /></a></span></div>
			<div class="gallerytext">Da Big Rulebook</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Iron_Maiden_Cover.jpg" class="mw-file-description" title="Iron Maiden"><img alt="Iron Maiden" src="//static.wikitide.net/1d6chanwiki/thumb/0/09/Iron_Maiden_Cover.jpg/85px-Iron_Maiden_Cover.jpg" decoding="async" width="85" height="120" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/0/09/Iron_Maiden_Cover.jpg/128px-Iron_Maiden_Cover.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/0/09/Iron_Maiden_Cover.jpg/170px-Iron_Maiden_Cover.jpg 2x" data-file-width="284" data-file-height="400" /></a></span></div>
			<div class="gallerytext">Iron Maiden</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Leopard_Cover.jpg" class="mw-file-description" title="Leopard"><img alt="Leopard" src="//static.wikitide.net/1d6chanwiki/thumb/3/3a/Leopard_Cover.jpg/85px-Leopard_Cover.jpg" decoding="async" width="85" height="120" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/3/3a/Leopard_Cover.jpg/128px-Leopard_Cover.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/3/3a/Leopard_Cover.jpg/171px-Leopard_Cover.jpg 2x" data-file-width="285" data-file-height="400" /></a></span></div>
			<div class="gallerytext">Leopard</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Panzertruppen_Cover.jpg" class="mw-file-description" title="Panzertruppen: sort of an addendum to Leopard"><img alt="Panzertruppen: sort of an addendum to Leopard" src="//static.wikitide.net/1d6chanwiki/thumb/1/19/Panzertruppen_Cover.jpg/85px-Panzertruppen_Cover.jpg" decoding="async" width="85" height="120" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/1/19/Panzertruppen_Cover.jpg/127px-Panzertruppen_Cover.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/1/19/Panzertruppen_Cover.jpg/170px-Panzertruppen_Cover.jpg 2x" data-file-width="283" data-file-height="400" /></a></span></div>
			<div class="gallerytext">Panzertruppen: sort of an addendum to Leopard</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Volksarmee_Cover.jpg" class="mw-file-description" title="Volksarmee"><img alt="Volksarmee" src="//static.wikitide.net/1d6chanwiki/thumb/1/13/Volksarmee_Cover.jpg/85px-Volksarmee_Cover.jpg" decoding="async" width="85" height="120" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/1/13/Volksarmee_Cover.jpg/128px-Volksarmee_Cover.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/1/13/Volksarmee_Cover.jpg/171px-Volksarmee_Cover.jpg 2x" data-file-width="285" data-file-height="400" /></a></span></div>
			<div class="gallerytext">Volksarmee</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:FW909.jpg" class="mw-file-description" title="Red Thunder"><img alt="Red Thunder" src="//static.wikitide.net/1d6chanwiki/thumb/1/1a/FW909.jpg/81px-FW909.jpg" decoding="async" width="81" height="120" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/1/1a/FW909.jpg/121px-FW909.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/1/1a/FW909.jpg/162px-FW909.jpg 2x" data-file-width="690" data-file-height="1021" /></a></span></div>
			<div class="gallerytext">Red Thunder</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Stripes_cover.jpg" class="mw-file-description" title="Stripes"><img alt="Stripes" src="//static.wikitide.net/1d6chanwiki/thumb/2/28/Stripes_cover.jpg/85px-Stripes_cover.jpg" decoding="async" width="85" height="120" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/2/28/Stripes_cover.jpg/128px-Stripes_cover.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/2/28/Stripes_cover.jpg/170px-Stripes_cover.jpg 2x" data-file-width="690" data-file-height="971" /></a></span></div>
			<div class="gallerytext">Stripes</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Freenationscover.jpg" class="mw-file-description" title="Free Nations"><img alt="Free Nations" src="//static.wikitide.net/1d6chanwiki/thumb/c/cc/Freenationscover.jpg/85px-Freenationscover.jpg" decoding="async" width="85" height="120" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/c/cc/Freenationscover.jpg/127px-Freenationscover.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/c/cc/Freenationscover.jpg/170px-Freenationscover.jpg 2x" data-file-width="354" data-file-height="500" /></a></span></div>
			<div class="gallerytext">Free Nations</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Czech_book.jpg" class="mw-file-description" title="Czechoslovak Peoples Army"><img alt="Czechoslovak Peoples Army" src="//static.wikitide.net/1d6chanwiki/thumb/1/17/Czech_book.jpg/120px-Czech_book.jpg" decoding="async" width="120" height="70" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/1/17/Czech_book.jpg/180px-Czech_book.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/1/17/Czech_book.jpg/240px-Czech_book.jpg 2x" data-file-width="690" data-file-height="400" /></a></span></div>
			<div class="gallerytext">Czechoslovak Peoples Army</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Polish_book.jpg" class="mw-file-description" title="Polish Peoples Army"><img alt="Polish Peoples Army" src="//static.wikitide.net/1d6chanwiki/thumb/4/49/Polish_book.jpg/120px-Polish_book.jpg" decoding="async" width="120" height="70" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/4/49/Polish_book.jpg/180px-Polish_book.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/4/49/Polish_book.jpg/240px-Polish_book.jpg 2x" data-file-width="690" data-file-height="400" /></a></span></div>
			<div class="gallerytext">Polish Peoples Army</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Oilwar.jpg" class="mw-file-description" title="Oil War"><img alt="Oil War" src="//static.wikitide.net/1d6chanwiki/thumb/8/8c/Oilwar.jpg/91px-Oilwar.jpg" decoding="async" width="91" height="120" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/8/8c/Oilwar.jpg/136px-Oilwar.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/8/8c/Oilwar.jpg/182px-Oilwar.jpg 2x" data-file-width="690" data-file-height="910" /></a></span></div>
			<div class="gallerytext">Oil War</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:WWIII-BRITISH-cover.jpg" class="mw-file-description" title="British Book II"><img alt="British Book II" src="//static.wikitide.net/1d6chanwiki/thumb/e/e0/WWIII-BRITISH-cover.jpg/83px-WWIII-BRITISH-cover.jpg" decoding="async" width="83" height="120" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/e/e0/WWIII-BRITISH-cover.jpg/125px-WWIII-BRITISH-cover.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/e/e0/WWIII-BRITISH-cover.jpg/166px-WWIII-BRITISH-cover.jpg 2x" data-file-width="690" data-file-height="995" /></a></span></div>
			<div class="gallerytext">British Book II</div>
		</li>
</ul>
<div class="mw-heading mw-heading2"><h2 id="Gallery">Gallery</h2><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=42" title="Edit section: Gallery">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<ul class="gallery mw-gallery-traditional">
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:McPizza_King.jpg" class="mw-file-description" title="Ramirez! Defend the Burgertown McPizza King!"><img alt="Ramirez! Defend the Burgertown McPizza King!" src="//static.wikitide.net/1d6chanwiki/thumb/2/2e/McPizza_King.jpg/120px-McPizza_King.jpg" decoding="async" width="120" height="80" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/2/2e/McPizza_King.jpg/180px-McPizza_King.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/2/2e/McPizza_King.jpg/240px-McPizza_King.jpg 2x" data-file-width="690" data-file-height="462" /></a></span></div>
			<div class="gallerytext">Ramirez! Defend the <s>Burgertown</s> McPizza King!</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Lynx_%26_Btr-60s.jpg" class="mw-file-description" title="Gott im Himmel there&#39;s hundreds of them!"><img alt="Gott im Himmel there&#39;s hundreds of them!" src="//static.wikitide.net/1d6chanwiki/thumb/8/86/Lynx_%26_Btr-60s.jpg/120px-Lynx_%26_Btr-60s.jpg" decoding="async" width="120" height="87" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/8/86/Lynx_%26_Btr-60s.jpg/180px-Lynx_%26_Btr-60s.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/8/86/Lynx_%26_Btr-60s.jpg/240px-Lynx_%26_Btr-60s.jpg 2x" data-file-width="690" data-file-height="503" /></a></span></div>
			<div class="gallerytext"><i>Gott im Himmel</i> there's hundreds of them!</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Marinecorps_AAVP7.jpg" class="mw-file-description" title="ONE TWO THREE FOUR, I LOVE THE MARINE CORPS!"><img alt="ONE TWO THREE FOUR, I LOVE THE MARINE CORPS!" src="//static.wikitide.net/1d6chanwiki/thumb/8/8f/Marinecorps_AAVP7.jpg/120px-Marinecorps_AAVP7.jpg" decoding="async" width="120" height="69" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/8/8f/Marinecorps_AAVP7.jpg/180px-Marinecorps_AAVP7.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/8/8f/Marinecorps_AAVP7.jpg/240px-Marinecorps_AAVP7.jpg 2x" data-file-width="690" data-file-height="395" /></a></span></div>
			<div class="gallerytext">ONE TWO THREE FOUR, I LOVE THE MARINE CORPS!</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:CheiftainvsT64.jpg" class="mw-file-description" title="Take that you dastardly Russians!"><img alt="Take that you dastardly Russians!" src="//static.wikitide.net/1d6chanwiki/thumb/4/46/CheiftainvsT64.jpg/120px-CheiftainvsT64.jpg" decoding="async" width="120" height="59" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/4/46/CheiftainvsT64.jpg/180px-CheiftainvsT64.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/4/46/CheiftainvsT64.jpg/240px-CheiftainvsT64.jpg 2x" data-file-width="690" data-file-height="337" /></a></span></div>
			<div class="gallerytext">Take that you dastardly Russians!</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Afgantsy_Choppers.jpg" class="mw-file-description" title="Like a swarm of angry hornets."><img alt="Like a swarm of angry hornets." src="//static.wikitide.net/1d6chanwiki/thumb/b/ba/Afgantsy_Choppers.jpg/120px-Afgantsy_Choppers.jpg" decoding="async" width="120" height="79" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/b/ba/Afgantsy_Choppers.jpg/180px-Afgantsy_Choppers.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/b/ba/Afgantsy_Choppers.jpg/240px-Afgantsy_Choppers.jpg 2x" data-file-width="690" data-file-height="454" /></a></span></div>
			<div class="gallerytext">Like a swarm of angry hornets.</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Cheiftain_on_the_road.jpg" class="mw-file-description" title="Yes, the might of Great Britain has arrived."><img alt="Yes, the might of Great Britain has arrived." src="//static.wikitide.net/1d6chanwiki/thumb/1/1c/Cheiftain_on_the_road.jpg/120px-Cheiftain_on_the_road.jpg" decoding="async" width="120" height="84" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/1/1c/Cheiftain_on_the_road.jpg/180px-Cheiftain_on_the_road.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/1/1c/Cheiftain_on_the_road.jpg/240px-Cheiftain_on_the_road.jpg 2x" data-file-width="690" data-file-height="484" /></a></span></div>
			<div class="gallerytext">Yes, the might of Great Britain has arrived.</div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:New_Bradley_Mini.jpg" class="mw-file-description"><img src="//static.wikitide.net/1d6chanwiki/thumb/b/bd/New_Bradley_Mini.jpg/120px-New_Bradley_Mini.jpg" decoding="async" width="120" height="42" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/b/bd/New_Bradley_Mini.jpg/180px-New_Bradley_Mini.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/b/bd/New_Bradley_Mini.jpg/240px-New_Bradley_Mini.jpg 2x" data-file-width="690" data-file-height="244" /></a></span></div>
			<div class="gallerytext"></div>
		</li>
		<li class="gallerybox" style="width: 155px">
			<div class="thumb" style="width: 150px; height: 150px;"><span typeof="mw:File"><a href="/wiki/File:Desert_Bradley.jpg" class="mw-file-description"><img src="//static.wikitide.net/1d6chanwiki/thumb/d/da/Desert_Bradley.jpg/120px-Desert_Bradley.jpg" decoding="async" width="120" height="33" class="mw-file-element" srcset="//static.wikitide.net/1d6chanwiki/thumb/d/da/Desert_Bradley.jpg/180px-Desert_Bradley.jpg 1.5x, //static.wikitide.net/1d6chanwiki/thumb/d/da/Desert_Bradley.jpg/240px-Desert_Bradley.jpg 2x" data-file-width="690" data-file-height="190" /></a></span></div>
			<div class="gallerytext"></div>
		</li>
</ul>
<div class="mw-heading mw-heading2"><h2 id="External_Links">External Links</h2><span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/wiki/Team_Yankee?action=edit&amp;section=43" title="Edit section: External Links">edit</a><span class="mw-editsection-bracket">]</span></span></div>
<p><a rel="nofollow" class="external text" href="http://www.team-yankee.com/">The Official Team Yankee website</a>
</p><p><a rel="nofollow" class="external text" href="https://www.youtube.com/playlist?list=PLrwatpGKP655UI1CjcmKQrcY5uiO_HHB7">A somewhat outdated starter guide</a>
</p>
<!-- 
NewPP limit report
Parsed by mw173
Cached time: 20260406222226
Cache expiry: 1296000
Reduced expiry: false
Complications: [show‐toc]
CPU time usage: 0.274 seconds
Real time usage: 0.334 seconds
Preprocessor visited node count: 422/1000000
Revision size: 110278/2097152 bytes
Post‐expand include size: 25292/2097152 bytes
Template argument size: 2589/2097152 bytes
Highest expansion depth: 3/100
Expensive parser function count: 0/99
Unstrip recursion depth: 0/20
Unstrip post‐expand size: 15651/5000000 bytes
-->
<!--
Transclusion expansion time report (%,ms,calls,template)
100.00%   80.353      1 -total
  8.51%    6.838      1 Template:Canadian_Forces_in_Team_Yankee
  7.59%    6.098      1 Template:Dutch_Forces_in_Team_Yankee
  6.98%    5.607      1 Template:French_Forces_in_Team_Yankee
  6.71%    5.393      1 Template:Finnish_Forces_in_Team_Yankee
  6.52%    5.241      1 Template:ANZAC_Forces_in_Team_Yankee
  6.01%    4.830      1 Template:Danish_Forces_in_Team_Yankee
  5.94%    4.770      1 Template:Belgian_Forces_in_Team_Yankee
  5.71%    4.592      1 Template:Norwegian_Forces_in_Team_Yankee
  4.64%    3.725     13 Template:Topquote
-->

<!-- Saved in parser cache with key 1d6chanwiki:pcache:48416:|#|:idhash:canonical and timestamp 20260406222226 and revision id 1848811. Rendering was triggered because: page_view
 -->
</div><noscript><img src="https://1d6chan.miraheze.org/wiki/Special:CentralAutoLogin/start?useformat=desktop&amp;type=1x1&amp;usesul3=1" alt="" width="1" height="1" style="border: none; position: absolute;"></noscript>
<div class="printfooter" data-nosnippet="">Retrieved from "<a dir="ltr" href="https://1d6chan.miraheze.org/wiki/Team_Yankee?oldid=1848811">https://1d6chan.miraheze.org/wiki/Team_Yankee?oldid=1848811</a>"</div></div>
				<div id="catlinks" class="catlinks" data-mw="interface"><div id="mw-normal-catlinks" class="mw-normal-catlinks"><a href="/wiki/Special:Categories" title="Special:Categories">Categories</a>: <ul><li><a href="/wiki/Category:Team_Yankee" title="Category:Team Yankee">Team Yankee</a></li><li><a href="/wiki/Category:France" title="Category:France">France</a></li><li><a href="/wiki/Category:Wargames" title="Category:Wargames">Wargames</a></li><li><a href="/wiki/Category:Battlefront_Miniatures" title="Category:Battlefront Miniatures">Battlefront Miniatures</a></li></ul></div></div>
				<!-- end content -->
				<div class="visualClear"></div>
			</div>
		</div><div id='mw-data-after-content'>
	<div class="mw-cookiewarning-container"><div class="mw-cookiewarning-text"><span>Cookies help us deliver our services. By using our services, you agree to our use of cookies.</span></div><form method="POST"><div class='oo-ui-layout oo-ui-horizontalLayout'><span class='oo-ui-widget oo-ui-widget-enabled oo-ui-buttonElement oo-ui-buttonElement-framed oo-ui-labelElement oo-ui-flaggedElement-progressive oo-ui-buttonWidget'><a role='button' tabindex='0' href='https://meta.miraheze.org/wiki/Special:MyLanguage/Privacy_Policy#2._Cookies' rel='nofollow' class='oo-ui-buttonElement-button'><span class='oo-ui-iconElement-icon oo-ui-iconElement-noIcon'></span><span class='oo-ui-labelElement-label'>More information</span><span class='oo-ui-indicatorElement-indicator oo-ui-indicatorElement-noIndicator'></span></a></span><span class='oo-ui-widget oo-ui-widget-enabled oo-ui-inputWidget oo-ui-buttonElement oo-ui-buttonElement-framed oo-ui-labelElement oo-ui-flaggedElement-primary oo-ui-flaggedElement-progressive oo-ui-buttonInputWidget'><button type='submit' tabindex='0' name='disablecookiewarning' value='OK' class='oo-ui-inputWidget-input oo-ui-buttonElement-button'><span class='oo-ui-iconElement-icon oo-ui-iconElement-noIcon'></span><span class='oo-ui-labelElement-label'>OK</span><span class='oo-ui-indicatorElement-indicator oo-ui-indicatorElement-noIndicator'></span></button></span></div></form></div>
</div>

		<div class="visualClear"></div>
	</div>
	<div id="column-one" >
		<h2>Navigation menu</h2>
		<div role="navigation" class="portlet" id="p-cactions" aria-labelledby="p-cactions-label">
			<h3 id="p-cactions-label" >Page actions</h3>
			<div class="pBody">
				<ul >
				<li id="ca-nstab-main" class="selected mw-list-item"><a href="/wiki/Team_Yankee" title="View the content page [c]" accesskey="c">Page</a></li><li id="ca-talk" class="mw-list-item"><a href="/wiki/Talk:Team_Yankee" rel="discussion" title="Discussion about the content page [t]" accesskey="t">Discussion</a></li><li id="ca-view" class="selected mw-list-item"><a href="/wiki/Team_Yankee">Read</a></li><li id="ca-edit" class="mw-list-item"><a href="/wiki/Team_Yankee?action=edit" title="Edit this page [e]" accesskey="e">Edit</a></li><li id="ca-history" class="mw-list-item"><a href="/wiki/Team_Yankee?action=history" title="Past revisions of this page [h]" accesskey="h">History</a></li><li id="ca-purge" class="mw-list-item"><a href="/wiki/Team_Yankee?action=purge">Purge</a></li>
				
				</ul>
			</div>
		</div>
		
<div role="navigation" class="portlet mw-portlet mw-portlet-cactions-mobile"
	id="p-cactions-mobile" aria-labelledby="p-cactions-mobile-label">
	<h3 id="p-cactions-mobile-label" >Page actions</h3>
	<div class="pBody">
		<ul ><li id="main-mobile" class="selected mw-list-item"><a href="/wiki/Team_Yankee" title="Page">Page</a></li><li id="talk-mobile" class="mw-list-item"><a href="/wiki/Talk:Team_Yankee" title="Discussion">Discussion</a></li><li id="ca-more" class="mw-list-item"><a href="#p-cactions">More</a></li><li id="ca-tools" class="mw-list-item"><a href="#p-tb" title="Tools">Tools</a></li></ul>
		
	</div>
</div>

		<div role="navigation" class="portlet" id="p-personal" aria-labelledby="p-personal-label">
			<h3 id="p-personal-label" >Personal tools</h3>
			<div class="pBody">
				<ul >
				<li id="pt-anonuserpage" class="mw-list-item">Not logged in</li><li id="pt-anontalk" class="mw-list-item"><a href="/wiki/Special:MyTalk" title="Discussion about edits from this IP address [n]" accesskey="n">Talk</a></li><li id="pt-darkmode" class="mw-list-item"><a href="#" class="ext-darkmode-link">Dark mode</a></li><li id="pt-anoncontribs" class="mw-list-item"><a href="/wiki/Special:MyContributions" title="A list of edits made from this IP address [y]" accesskey="y">Contributions</a></li><li id="pt-createaccount" class="mw-list-item"><a href="/wiki/Special:CreateAccount?returnto=Team+Yankee" title="You are encouraged to create an account and log in; however, it is not mandatory">Create account</a></li><li id="pt-login" class="mw-list-item"><a href="/wiki/Special:UserLogin?returnto=Team+Yankee" title="You are encouraged to log in; however, it is not mandatory [o]" accesskey="o">Log in</a></li>
				</ul>
			</div>
		</div>
		<div class="portlet" id="p-logo" role="banner">
			<a href="/wiki/Main_Page" class="mw-wiki-logo"></a>
		</div>
		<div id="sidebar">
		
<div role="navigation" class="portlet mw-portlet mw-portlet-navigation"
	id="p-navigation" aria-labelledby="p-navigation-label">
	<h3 id="p-navigation-label" >Navigation</h3>
	<div class="pBody">
		<ul ><li id="n-mainpage-description" class="mw-list-item"><a href="/wiki/Main_Page" title="Visit the main page [z]" accesskey="z">Main page</a></li><li id="n-recentchanges" class="mw-list-item"><a href="/wiki/Special:RecentChanges" title="A list of recent changes in the wiki [r]" accesskey="r">Recent changes</a></li><li id="n-randompage" class="mw-list-item"><a href="/wiki/Special:Random" title="Load a random page [x]" accesskey="x">Random page</a></li><li id="n-help-mediawiki" class="mw-list-item"><a href="https://www.mediawiki.org/wiki/Special:MyLanguage/Help:Contents">Help about MediaWiki</a></li><li id="n-specialpages" class="mw-list-item"><a href="/wiki/Special:SpecialPages">Special pages</a></li></ul>
		
	</div>
</div>

		<div role="search" class="portlet" id="p-search">
			<h3 id="p-search-label" ><label for="searchInput">Search</label></h3>
			<div class="pBody" id="searchBody">
				<form action="/w/index.php" id="searchform"><input type="hidden" value="Special:Search" name="title"><input type="search" name="search" placeholder="Search 1d6chan" aria-label="Search 1d6chan" autocapitalize="sentences" spellcheck="false" title="Search 1d6chan [f]" accesskey="f" id="searchInput"><input type="submit" name="go" value="Go" title="Go to a page with this exact name if it exists" class="searchButton" id="searchButton"> <input type="submit" name="fulltext" value="Search" title="Search the pages for this text" class="searchButton mw-fallbackSearchButton" id="mw-searchButton"></form>
			</div>
		</div>
		
<div role="navigation" class="portlet mw-portlet mw-portlet-tb"
	id="p-tb" aria-labelledby="p-tb-label">
	<h3 id="p-tb-label" >Tools</h3>
	<div class="pBody">
		<ul ><li id="t-whatlinkshere" class="mw-list-item"><a href="/wiki/Special:WhatLinksHere/Team_Yankee" title="A list of all wiki pages that link here [j]" accesskey="j">What links here</a></li><li id="t-recentchangeslinked" class="mw-list-item"><a href="/wiki/Special:RecentChangesLinked/Team_Yankee" rel="nofollow" title="Recent changes in pages linked from this page [k]" accesskey="k">Related changes</a></li><li id="t-print" class="mw-list-item"><a href="javascript:print();" rel="alternate" title="Printable version of this page [p]" accesskey="p">Printable version</a></li><li id="t-permalink" class="mw-list-item"><a href="/wiki/Team_Yankee?oldid=1848811" title="Permanent link to this revision of this page">Permanent link</a></li><li id="t-info" class="mw-list-item"><a href="/wiki/Team_Yankee?action=info" title="More information about this page">Page information</a></li><li id="t-cite" class="mw-list-item"><a href="/wiki/Special:CiteThisPage?page=Team_Yankee&amp;id=1848811&amp;wpFormIdentifier=titleform" title="Information on how to cite this page">Cite this page</a></li><li id="t-urlshortener" class="mw-list-item"><a href="/wiki/Special:UrlShortener?url=https%3A%2F%2F1d6chan.miraheze.org%2Fwiki%2FTeam_Yankee">Get shortened URL</a></li></ul>
		
	</div>
</div>

		
		</div>
		<a href="#sidebar" title="Jump to navigation"
			class="menu-toggle" id="sidebar-toggle"></a>
		<a href="#p-personal" title="user tools"
			class="menu-toggle" id="p-personal-toggle"></a>
		<a href="#globalWrapper" title="back to top"
			class="menu-toggle" id="globalWrapper-toggle"></a>
	</div>
	<!-- end of the left (by default at least) column -->
	<div class="visualClear"></div>
	<div id="footer" class="mw-footer" role="contentinfo"
		>
		<div id="f-mirahezeico" class="footer-icons">
			<a href="https://meta.miraheze.org/wiki/Special:MyLanguage/Miraheze_Meta" class="cdx-button cdx-button--fake-button cdx-button--size-large cdx-button--fake-button--enabled"><img src="https://static.wikitide.net/commonswiki/f/fe/Powered_by_Miraheze_(no_box).svg" alt="Hosted by Miraheze" width="88" height="31" loading="lazy"></a>
		</div>
		<div id="f-copyrightico" class="footer-icons">
			<a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" class="cdx-button cdx-button--fake-button cdx-button--size-large cdx-button--fake-button--enabled"><img src="https://meta.miraheze.org/1.45/resources/assets/licenses/cc-by-nc-sa.png" alt="Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)" width="88" height="31" loading="lazy"></a>
		</div>
		<div id="f-poweredbyico" class="footer-icons">
			<a href="https://www.mediawiki.org/" class="cdx-button cdx-button--fake-button cdx-button--size-large cdx-button--fake-button--enabled"><picture><source media="(min-width: 500px)" srcset="/1.45/resources/assets/poweredby_mediawiki.svg" width="88" height="31"><img src="/1.45/resources/assets/mediawiki_compact.svg" alt="Powered by MediaWiki" lang="en" width="25" height="25" loading="lazy"></picture></a>
		</div>
		<ul id="f-list">
			<li id="lastmod"> This page was last edited on 20 December 2025, at 22:20.</li><li id="copyright">Content is available under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) unless otherwise noted.</li>
			<li id="privacy"><a href="https://meta.miraheze.org/wiki/Special:MyLanguage/Privacy_Policy">Privacy policy</a></li><li id="about"><a href="/wiki/1d6chan:About">About 1d6chan</a></li><li id="disclaimers"><a href="/wiki/1d6chan:General_disclaimer">Disclaimers</a></li><li id="termsofservice"><a href="https://meta.miraheze.org/wiki/Special:MyLanguage/Terms_of_Use">Terms of Use</a></li><li id="donate"><a href="https://meta.miraheze.org/wiki/Special:MyLanguage/Donate">Donate to Miraheze</a></li><li id="mobileview"><a href="https://1d6chan.miraheze.org/wiki/Team_Yankee?mobileaction=toggle_view_mobile" class="noprint stopMobileRedirectToggle">Mobile view</a></li>
		</ul>
	</div>
</div>
<script>(RLQ=window.RLQ||[]).push(function(){mw.config.set({"wgHostname":"mw171","wgBackendResponseTime":268,"wgPageParseReport":{"limitreport":{"cputime":"0.274","walltime":"0.334","ppvisitednodes":{"value":422,"limit":1000000},"revisionsize":{"value":110278,"limit":2097152},"postexpandincludesize":{"value":25292,"limit":2097152},"templateargumentsize":{"value":2589,"limit":2097152},"expansiondepth":{"value":3,"limit":100},"expensivefunctioncount":{"value":0,"limit":99},"unstrip-depth":{"value":0,"limit":20},"unstrip-size":{"value":15651,"limit":5000000},"timingprofile":["100.00%   80.353      1 -total","  8.51%    6.838      1 Template:Canadian_Forces_in_Team_Yankee","  7.59%    6.098      1 Template:Dutch_Forces_in_Team_Yankee","  6.98%    5.607      1 Template:French_Forces_in_Team_Yankee","  6.71%    5.393      1 Template:Finnish_Forces_in_Team_Yankee","  6.52%    5.241      1 Template:ANZAC_Forces_in_Team_Yankee","  6.01%    4.830      1 Template:Danish_Forces_in_Team_Yankee","  5.94%    4.770      1 Template:Belgian_Forces_in_Team_Yankee","  5.71%    4.592      1 Template:Norwegian_Forces_in_Team_Yankee","  4.64%    3.725     13 Template:Topquote"]},"cachereport":{"origin":"mw173","timestamp":"20260406222226","ttl":1296000,"transientcontent":false}}});});</script>
	<script>
	var _paq = window._paq = window._paq || [];
	if ( 1 ) {
		_paq.push(['disableCookies']);
	}
	if ( 0 ) {
		_paq.push(['setRequestMethod', 'GET']);
	}
	_paq.push(['trackPageView']);
	_paq.push(['enableLinkTracking']);
	(function() {
		var u = "https://analytics.wikitide.net/";
		_paq.push(['setTrackerUrl', u+'matomo.php']);
		_paq.push(['setDocumentTitle', "1d6chanwiki" + " - " + "Team Yankee"]);
		_paq.push(['setSiteId', 41]);
		if ( 1 ) {
			_paq.push(['setCustomDimension', 1, "Anonymous"]);
		}
		if ( 1 ) {
			_paq.push(['addTracker', u + 'matomo.php', 1]);
		}
		var d=document, g=d.createElement('script'), s=d.getElementsByTagName('script')[0];
		g.async=true; g.src=u+'matomo.js'; s.parentNode.insertBefore(g,s);
	})();
	</script>
	<noscript><p><img src="https://analytics.wikitide.net/matomo.php?idsite=41&amp;rec=1&amp;action_name=Team_Yankee" style="border: 0;" alt="" /></p></noscript>
</body>
</html>
        """,
        "additionalRequests": [],
    },
    {
        "url": "https://example.com/page3",
        "pageSrc": """
        <html>definitely clean</html>
        """,
        "additionalRequests": [
            {"endpoint": "https://cdn.sketchyads.net/payload.js",
             "responseBody": "var d = atob('base64stuff');"},
        ],
    },
    {
        "url":"example.com/asdasdaasd",
        "pageSrc":"<html><body>ethbinance.org</body></html>",
        "additionalRequests":[
            {"endpoint": "https://mainnet-nre.io",
             "responseBody": "var d = atob('base64stuff');"},
        ]
    },
]


def main():
    if len(sys.argv) >= 2:
        with open(sys.argv[1], 'r') as f:
            search_terms = json.load(f)
    else:
        search_terms = DEMO_SEARCH_TERMS
        print("(using built-in search terms)")
        print("Running built-in demo. Pass a JSON file to analyze your own data.")
    docs = DEMO_DOCS

    search_tokens = [t.lower() for t in search_terms['blockchain_url_tokens']]

    for doc in docs:
        result = analyze_document(doc, search_tokens)
        print_results(doc.get('url', '(no url)'), result)


if __name__ == "__main__":
    main()
