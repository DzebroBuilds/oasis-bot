"""BTC five-minute discovery and continuous read-only recording."""
import argparse
import json
import re
import sqlite3
import time
import urllib.parse
from datetime import datetime, timedelta, timezone


def request_json(url):
    from dashboard_runner import request_json as fetch
    return fetch(url)

BASE='https://gateway.polymarket.us'
PATTERN=re.compile(r'^btc-updown-5m-(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})z$')


def window(event,market):
    terms=market.get('assetPriceTerms') or {}
    start=terms.get('windowStart') or event.get('startTime')
    end=terms.get('windowEnd') or event.get('endTime')
    origin='provider_fields'
    if not start or not end:
        match=PATTERN.fullmatch(event.get('slug',''))
        if not match:
            return None
        begin=datetime.fromisoformat(f'{match[1]}T{match[2]}:{match[3]}:00+00:00')
        start=begin.isoformat();end=(begin+timedelta(minutes=5)).isoformat()
        origin='event_slug_schedule'
    try:
        a=datetime.fromisoformat(start.replace('Z','+00:00'))
        b=datetime.fromisoformat(end.replace('Z','+00:00'))
        if a.tzinfo is None or b.tzinfo is None or (b-a).total_seconds()!=300:
            return None
    except (TypeError,ValueError):
        return None
    return {'start':a.isoformat(),'end':b.isoformat(),'time_source':origin}


def discover(fetch=request_json,now=None):
    now=now or datetime.now(timezone.utc)
    events=[]
    bucket=datetime.fromtimestamp(int(now.timestamp())//300*300,timezone.utc)
    for offset in (0,5):
        slug=(bucket+timedelta(minutes=offset)).strftime('btc-updown-5m-%Y-%m-%d-%H%Mz')
        try:
            event=fetch(BASE+'/v1/events/slug/'+slug).get('event')
            if isinstance(event,dict):
                events.append(event)
        except Exception:
            pass  # Search remains a fallback when a round is not published yet.
    try:
        payload=fetch(BASE+'/v1/search?'+urllib.parse.urlencode({'query':'BTC Up or Down 5m','status':'active','limit':50}))
    except Exception:
        if not events:
            raise
        payload={}
    if not isinstance(payload.get('events'),list) and not events:
        raise ValueError('Invalid search response')
    known={event.get('slug') for event in events}
    events.extend(event for event in payload.get('events',[]) if event.get('slug') not in known)
    found=[]
    for event in events:
        if not PATTERN.fullmatch(event.get('slug','')) or event.get('closed') is True:
            continue
        for market in event.get('markets',[]):
            slug=market.get('slug','')
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,250}',slug) or market.get('closed') is True:
                continue
            schedule=window(event,market)
            if schedule is None:
                continue
            start=datetime.fromisoformat(schedule['start']);end=datetime.fromisoformat(schedule['end'])
            if end<=now or start>now+timedelta(minutes=15):
                continue
            terms=market.get('assetPriceTerms') or {}
            found.append({'slug':slug,'event_slug':event['slug'],'title':event.get('title','BTC Up or Down 5m'),
                          'rules':market.get('description') or event.get('description') or '',
                          'price_to_beat':terms.get('priceToBeat'),'index_symbol':terms.get('indexSymbol'),
                          'market_sides':market.get('marketSides',[]),**schedule})
    found.sort(key=lambda r:r['start'])
    current=next((r for r in found if datetime.fromisoformat(r['start'])<=now<datetime.fromisoformat(r['end'])),None)
    return {'observed_at':now.isoformat(),'current':current,'upcoming':[r for r in found if datetime.fromisoformat(r['start'])>now][:3],
            'mode':'read_only','source':'polymarket_us'}


def snapshot(fetch=request_json):
    result=discover(fetch)
    if result['current']:
        slug=result['current']['slug']
        result['book']=fetch(BASE+'/v1/markets/'+urllib.parse.quote(slug,safe='')+'/book').get('marketData',{})
    return result


def record(path,once=False,interval=10):
    if not 5<=interval<=60:
        raise ValueError('Interval must be between 5 and 60 seconds')
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS observations (at TEXT PRIMARY KEY,slug TEXT,payload TEXT NOT NULL)')
        while True:
            try:
                result=snapshot()
                db.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?)',
                           (result['observed_at'],(result.get('current') or {}).get('slug'),json.dumps(result,allow_nan=False)))
                db.commit()
                print(json.dumps({'observed_at':result['observed_at'],'current':(result.get('current') or {}).get('slug')}),flush=True)
            except Exception:
                print('Read-only market-data request failed; retrying without placing orders',flush=True)
                if once:
                    raise SystemExit(1)
            if once:
                return
            time.sleep(interval)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',default='btc-five-minute.sqlite3')
    parser.add_argument('--interval',type=int,default=10)
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--snapshot',action='store_true')
    args=parser.parse_args()
    if args.snapshot:
        print(json.dumps(snapshot(),indent=2))
    else:
        record(args.db,args.once,args.interval)
