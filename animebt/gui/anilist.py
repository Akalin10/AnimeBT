"""AniList fallback metadata; negative internal IDs never address Bangumi."""
from datetime import date
from urllib.parse import urlsplit

URL = "https://graphql.anilist.co"
QUERY = """query ($search:String!, $page:Int!) {
 Page(page:$page, perPage:20) {
  pageInfo { hasNextPage }
  media(search:$search, type:ANIME, isAdult:false, sort:SEARCH_MATCH) {
   id title { romaji english native } synonyms format episodes
   startDate { year month day } coverImage { extraLarge large }
  }
 }
}"""

def read_page(data):
    if data.get('errors'):
        raise ValueError('AniList returned GraphQL errors')
    page=data['data']['Page']
    if not isinstance(page['media'],list):raise ValueError('Invalid AniList results')
    results={}
    for row in page['media']:
        if not isinstance(row,dict) or type(row.get('id')) is not int or row['id']<=0:continue
        title=row.get('title') or {}
        names=list(dict.fromkeys(name.strip() for name in [title.get('native'),title.get('romaji'),title.get('english'),*(row.get('synonyms') or [])] if isinstance(name,str) and name.strip()))
        if not names:continue
        cn=next((name for name in names if any('\u3400'<=c<='\u9fff' for c in name) and not any('\u3040'<=c<='\u30ff' for c in name)),None)
        original=title.get('native') or title.get('romaji') or names[0]
        aired=row.get('startDate') or {};year=aired.get('year');month=aired.get('month')
        stamp='';season=''
        if type(year) is int and type(month) is int and 1<=month<=12:
            try:stamp=date(year,month,aired.get('day') or 1).isoformat()
            except ValueError:pass
            season=f'{year} 年 {(month-1)//3*3+1} 月番'
        covers=[]
        for candidate in (row.get('coverImage') or {}).values():
            if isinstance(candidate,str) and urlsplit(candidate).scheme=='https' and urlsplit(candidate).hostname=='s4.anilist.co' and candidate not in covers:covers.append(candidate)
        entry={'id':-row['id'],'provider':'anilist','providerId':row['id'],'title':cn or original,'original':original if original!=(cn or original) else '',
               'aliases':names,'aliasLanguages':{},'season':season,'date':stamp,'episodes':row.get('episodes') or 0,
               'platform':{'TV_SHORT':'tv','SPECIAL':'sp'}.get(row.get('format'),(row.get('format') or '').lower()),
               'cover':covers[0] if covers else '', 'coverAlternatives':covers[1:]}
        results.setdefault(entry['id'],entry)
    return list(results.values()), bool((page.get('pageInfo') or {}).get('hasNextPage'))
