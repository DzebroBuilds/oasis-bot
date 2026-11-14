"""Public Polymarket US market data only. No credentials or order operations."""
import re
import urllib.parse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING

BASE = 'https://gateway.polymarket.us'


def amount(value):
    if not isinstance(value,dict) or value.get('currency')!='USD':
        return None
    try:
        price=Decimal(str(value['value']))*100
        return int(price.to_integral_value(rounding=ROUND_CEILING)) if price.is_finite() and 0<price<100 else None
    except (InvalidOperation,KeyError,TypeError,ValueError):
        return None


def opposite_ask(value):
    if not isinstance(value,dict) or value.get('currency')!='USD':
        return None
    try:
        return amount({'value':str(Decimal(1)-Decimal(str(value['value']))),'currency':'USD'})
    except (InvalidOperation,KeyError,TypeError,ValueError):
        return None


def scan_polymarket(fetch):
    response=fetch(BASE+'/v1/markets?'+urllib.parse.urlencode({'limit':50,'active':'true','closed':'false'}))
    if not isinstance(response,dict) or not isinstance(response.get('markets'),list):
        raise ValueError('Invalid Polymarket US response')
    observed=datetime.now(timezone.utc).isoformat()
    rows=[]
    seen=set()
    for market in response['markets'][:50]:
        slug=market.get('slug')
        if not isinstance(slug,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,250}',slug) or slug in seen:
            continue
        if market.get('active') is not True or market.get('closed') is not False or market.get('archived') is True:
            continue
        seen.add(slug)
        long_side=next((side for side in market.get('marketSides',[]) if side.get('long') is True),{})
        row={'ticker':'PMUS:'+slug,'slug':slug,'source':'polymarket_us',
             'event':'PMUS:'+str(market.get('eventSlug') or slug),
             'title':str(market.get('question') or market.get('title') or slug)[:500],
             'category':str(market.get('category') or 'Other')[:80],
             'rules':str(market.get('description') or '')[:5000],
             'quoted_at':observed,'closes_at':market.get('endDate'),
             'yes_ask_cents':amount(market.get('bestAskQuote')),
             'no_ask_cents':opposite_ask(market.get('bestBidQuote')),
             'yes_ask_size':0,'no_ask_size':0,'volume':None,'status':'active',
             'outcome_label':str(long_side.get('description') or market.get('outcome') or 'Long outcome')[:250],
             'comparison_status':'unreviewed','read_only':True}
        # Bound enrichment to ten books; missing quotes are never invented from last prices.
        if len(rows)<10:
            try:
                result=fetch(BASE+'/v1/markets/'+urllib.parse.quote(slug,safe='')+'/bbo').get('marketData',{})
                row['yes_ask_cents']=amount(result.get('bestAsk'))
                row['no_ask_cents']=opposite_ask(result.get('bestBid'))
                row['quoted_at']=datetime.now(timezone.utc).isoformat()
                row['quote_status']='bbo'
                count=Decimal(str(result.get('sharesTraded')))
                if count.is_finite() and count>=0:
                    row['volume']=int(count)
            except Exception:
                row['quote_status']='listing_only'
        rows.append(row)
    return rows
